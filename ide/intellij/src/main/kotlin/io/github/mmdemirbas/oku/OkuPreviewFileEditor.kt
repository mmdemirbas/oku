package io.github.mmdemirbas.oku

import com.google.gson.Gson
import com.google.gson.JsonParser
import com.intellij.ide.BrowserUtil
import com.intellij.ide.ui.LafManagerListener
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.ApplicationNamesInfo
import com.intellij.openapi.application.EDT
import com.intellij.openapi.application.readAction
import com.intellij.openapi.components.service
import com.intellij.openapi.diagnostic.logger
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.editor.event.DocumentEvent
import com.intellij.openapi.editor.event.DocumentListener
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.fileEditor.FileEditor
import com.intellij.openapi.fileEditor.FileEditorState
import com.intellij.openapi.fileEditor.OpenFileDescriptor
import com.intellij.openapi.project.Project
import com.intellij.openapi.util.Disposer
import com.intellij.openapi.util.UserDataHolderBase
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VfsUtilCore
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.openapi.vfs.VirtualFileManager
import com.intellij.openapi.vfs.newvfs.BulkFileListener
import com.intellij.openapi.vfs.newvfs.events.VFileEvent
import com.intellij.openapi.wm.IdeFocusManager
import com.intellij.ui.JBColor
import com.intellij.ui.jcef.JBCefBrowser
import com.intellij.ui.jcef.JBCefBrowserBase
import com.intellij.ui.jcef.JBCefJSQuery
import com.intellij.platform.util.coroutines.childScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.cef.browser.CefBrowser
import org.cef.browser.CefFrame
import org.cef.handler.CefLifeSpanHandlerAdapter
import org.cef.handler.CefLoadHandlerAdapter
import org.cef.handler.CefRequestHandlerAdapter
import org.cef.network.CefRequest
import java.beans.PropertyChangeListener
import java.net.URI
import java.net.URLDecoder
import java.nio.file.Files
import java.nio.file.Path
import java.util.UUID
import java.util.concurrent.atomic.AtomicInteger
import javax.swing.JComponent
import kotlin.io.path.Path

/**
 * The kit's own rendering of one oku page, in the IDE's embedded Chromium.
 *
 * Every edit re-renders through `oku preview --serve`. When only the page
 * changed, the new page is handed to the one on screen (`OkuRenderer.update`
 * in the kit), which keeps every block the edit did not touch and the
 * reader's place; anything else reloads. Links leave the panel: another
 * page or a `#f/` file opens in the IDE, a web address opens in the system
 * browser. The page is told it has a host (`window.__okuHost` in the kit),
 * so a file chip opens its file here, on the line it names, rather than
 * in the kit's own viewer inside the panel.
 *
 * The page follows the text editor beside it ([follow], [OkuFollower]): the
 * source line at the editor's top is put at the page's top
 * (`OkuRenderer.scrollToLine`, which needs the line of every block — `oku
 * preview` writes them). A double-click on the page goes the other way,
 * through the host's `revealLine`: the caret moves to that line, and the
 * editor is scrolled to where the page is, so neither pane jumps. And the
 * reader scrolling the page moves the editor with it, through the host's
 * `pageTop`: the kit reports only the reader's scrolls, never one the
 * editor made, so the two panes do not chase each other.
 *
 * [file] may also be a shell ([OkuPages.isShell]), the `index.html` a tree
 * is entered by. Then the page drawn is the `.md` beside it ([source]), with
 * no editor to follow: a double-click opens that `.md` on the line. With no
 * `.md` beside it, the shell is the tree's front door, which lists the
 * tree's pages and is drawn again when one of them is saved, added or
 * removed.
 */
@OptIn(FlowPreview::class)
class OkuPreviewFileEditor(
    private val project: Project,
    private val file: VirtualFile,
) : UserDataHolderBase(), FileEditor {

    private val log = logger<OkuPreviewFileEditor>()
    private val browser = JBCefBrowser()
    /** The page drawn: [file], or for a shell the `.md` beside it, or the shell itself for a front door. */
    private val source: VirtualFile =
        if (file.extension.equals("html", ignoreCase = true)) OkuPages.pageOf(file) ?: file else file

    private val frontDoor = source.extension.equals("html", ignoreCase = true)

    private val document = if (frontDoor) null else FileDocumentManager.getInstance().getDocument(source)
    private val previews = service<OkuPreviewService>()

    /** This preview's work; cancelled with it. */
    private val cs = previews.scope.childScope("oku preview of ${file.name}")

    /**
     * A render request, as the wait before it: the render runs that long
     * after the last request, and a request arriving meanwhile replaces the
     * one waiting. One collector, so two renders never run at once.
     */
    private val renders = MutableSharedFlow<Long>(replay = 1, onBufferOverflow = BufferOverflow.DROP_OLDEST)

    /**
     * The text editor the page follows, once the split has paired them.
     * Set on the EDT; read from the page's thread too, where a stale null
     * only drops one report.
     */
    @Volatile
    private var follower: OkuFollower? = null

    // Created before the browser loads anything: a query made after the
    // native browser exists needs a slot from a pool sized in advance.
    private val hostQuery = JBCefJSQuery.create(browser as JBCefBrowserBase)

    @Volatile
    private var current: Rendered? = null

    private val generation = AtomicInteger()

    private val errorPage = OkuErrorPage(previews.outBase)

    /** The last render failed, so the panel is showing why and not the page. */
    @Volatile
    private var failed = false

    /** The render the panel holds, or null while it holds something else. */
    @Volatile
    private var shown: Rendered? = null

    /** Set when a load is asked for, cleared when Chromium says it finished. */
    @Volatile
    private var loading = false

    init {
        Disposer.register(this, browser)
        Disposer.register(this, hostQuery)
        hostQuery.addHandler { request ->
            fromPage(request)
            null
        }
        document?.addDocumentListener(object : DocumentListener {
            override fun documentChanged(event: DocumentEvent) = schedule(EDIT_DELAY_MS)
        }, this)
        ApplicationManager.getApplication().messageBus.connect(this)
            .subscribe(LafManagerListener.TOPIC, LafManagerListener { schedule(0) })
        if (frontDoor) watchTree()
        installNavigation()
        browser.jbCefClient.addLoadHandler(object : CefLoadHandlerAdapter() {
            override fun onLoadingStateChange(
                browser: CefBrowser?, isLoading: Boolean, canGoBack: Boolean, canGoForward: Boolean,
            ) {
                if (!isLoading) loading = false
            }

            // Every load is a new window object, so the host is told again,
            // and a new page starts at its top wherever the editor is.
            override fun onLoadEnd(browser: CefBrowser?, frame: CefFrame?, httpStatusCode: Int) {
                if (frame?.isMain != true) return
                browser?.executeJavaScript(hostScript, frame.url, 0)
                ApplicationManager.getApplication().invokeLater { follower?.follow(force = true) }
            }
        }, browser.cefBrowser)
        cs.launch(Dispatchers.IO) { renders.debounce { it }.collect { render() } }
        schedule(0)
    }

    /** Pair with the text editor beside this preview; the page follows it from now on. */
    fun follow(editor: Editor) {
        follower = OkuFollower(editor, cs, this, ready = { force -> shown != null && (!loading || force) }, send = ::scrollPageTo)
    }

    private fun schedule(delayMs: Long) {
        renders.tryEmit(delayMs)
    }

    private suspend fun render() {
        val text = if (frontDoor) null else readAction { document?.text ?: VfsUtilCore.loadText(source) }
        val theme = if (JBColor.isBright()) "light" else "dark"
        val result = previews.render(Path(source.path), text, theme)
        // A render already sent finishes (cutting it short would leave its
        // reply to be read as the next one's), but a closed preview shows nothing.
        cs.ensureActive()
        result
            .onSuccess {
                current = it
                failed = false
                val before = shown
                shown = it
                val page = it.page
                if (page != null && !loading && before != null && before.html == it.html && before.shell == it.shell) {
                    update(it, page)
                } else {
                    load(it)
                }
            }
            .onFailure {
                failed = true
                log.warn("oku preview failed for ${source.path}", it)
                showError(it.message ?: it.toString())
            }
    }

    private fun load(rendered: Rendered) {
        loading = true
        // A new query per load: JBCefBrowserBase skips a load of the URL it
        // last requested ("URL already requested, skipping"), so a
        // re-render of the same page never reached the panel.
        browser.loadURL("${rendered.html.toUri()}?r=${generation.incrementAndGet()}")
    }

    /**
     * Hand the new page to the one on screen. Anything that keeps that from
     * working — the kit not finished starting, a kit without `update`, a
     * throw — reloads instead, and the file on disk is already the new
     * version, so the reload shows it.
     */
    private fun update(rendered: Rendered, pageJson: Path) {
        val page = Files.readString(pageJson)
        val script = "(function (p) {" +
            "try { if (window.__okuRendered && window.OkuRenderer && OkuRenderer.prototype.update" +
            " && new OkuRenderer({}).update(p)) return; }" +
            " catch (e) { console.error('[oku preview] update failed, reloading', e); }" +
            " location.reload(); })($page);"
        browser.cefBrowser.executeJavaScript(script, rendered.html.toUri().toString(), 0)
    }

    private fun showError(message: String) {
        shown = null
        browser.loadURL(errorPage.show(message))
    }

    // ---- following the editor ---------------------------------------------

    /**
     * Put source line [top] at the page's top. Before the kit has drawn the
     * page the line is held for its `oku:rendered`, and only the latest one
     * is: a load answers with wherever the editor is by then.
     */
    private fun scrollPageTo(top: Double) {
        val script = "(function (l) { window.__okuFollow = l;" +
            " var go = function () { if (window.OkuRenderer && OkuRenderer.scrollToLine) OkuRenderer.scrollToLine(window.__okuFollow); };" +
            " if (window.__okuRendered) go();" +
            " else if (!window.__okuFollowWaits) { window.__okuFollowWaits = true; window.addEventListener('oku:rendered', go, { once: true }); }" +
            " })($top);"
        browser.cefBrowser.executeJavaScript(script, browser.cefBrowser.url, 0)
    }

    /**
     * The page's double-click, handed to [OkuFollower.reveal]; the editor then
     * takes the keyboard. A shell has no editor beside it, so its `.md` opens
     * on the line instead.
     */
    private fun reveal(line: Int, top: Double?) {
        ApplicationManager.getApplication().invokeLater {
            val follower = follower ?: run {
                if (!frontDoor && source != file) open(Path(source.path), line = line - 1, anchor = null)
                return@invokeLater
            }
            val after = follower.reveal(line, top) ?: return@invokeLater
            log.info("oku preview: reveal line $line, page top $top, editor top $after")
            IdeFocusManager.getInstance(project).requestFocus(follower.editor.contentComponent, true)
        }
    }

    /**
     * A front door lists the tree's pages, so it is drawn again when a page is
     * saved (its title or summary may have changed), added, removed or
     * renamed, or when the tree's kit.json changes. Unsaved edits do not move
     * it: the list is of the pages as the build would find them.
     */
    private fun watchTree() {
        project.messageBus.connect(this).subscribe(VirtualFileManager.VFS_CHANGES, object : BulkFileListener {
            override fun after(events: List<VFileEvent>) {
                val root = current?.root ?: return
                val touched = events.any { e ->
                    val path = e.path
                    (path.endsWith(".md", ignoreCase = true) || path.endsWith("/kit.json")) && Path(path).startsWith(root)
                }
                if (touched) schedule(EDIT_DELAY_MS)
            }
        })
    }

    // ---- links ------------------------------------------------------------

    /**
     * The kit's `window.__okuHost`. It asks `openFile` before opening a file
     * itself, and calls `revealLine` on a double-click; the page's own top
     * line goes with it so the editor can be put at the same place. It
     * calls `pageTop` with the line at the page's top as the reader scrolls.
     */
    private val hostScript: String by lazy {
        val name = Gson().toJson(ApplicationNamesInfo.getInstance().fullProductName)
        val open = hostQuery.inject("JSON.stringify({ path: String(path), line: line || 0, anchor: anchor || null })")
        val reveal = hostQuery.inject(
            "JSON.stringify({ reveal: line, top: window.OkuRenderer && OkuRenderer.lineAt ? OkuRenderer.lineAt(0) : null })",
        )
        val pageTop = hostQuery.inject("JSON.stringify({ pageTop: line })")
        "window.__okuHost = { name: $name," +
            " openFile: function (path, line, anchor) { $open; return true; }," +
            " revealLine: function (line) { $reveal; }," +
            " pageTop: function (line) { $pageTop; } };"
    }

    private fun fromPage(request: String) {
        val message = runCatching { JsonParser.parseString(request).asJsonObject }.getOrNull() ?: return
        val pageTop = message.get("pageTop")?.takeIf { it.isJsonPrimitive }?.asDouble
        if (pageTop != null) {
            follower?.pageScrolled(pageTop)
            return
        }
        val reveal = message.get("reveal")?.takeIf { it.isJsonPrimitive }?.asInt
        if (reveal != null) {
            val top = message.get("top")?.takeIf { it.isJsonPrimitive }?.asDouble
            reveal(reveal, top)
            return
        }
        val path = message.get("path")?.takeIf { it.isJsonPrimitive }?.asString ?: return
        val line = message.get("line")?.takeIf { it.isJsonPrimitive }?.asInt ?: 0
        val anchor = message.get("anchor")?.takeIf { it.isJsonPrimitive }?.asString
        log.info("oku preview: the page opens $path line $line anchor $anchor")
        open(Path(path), line = line - 1, anchor = anchor)
    }

    private fun installNavigation() {
        browser.jbCefClient.addRequestHandler(object : CefRequestHandlerAdapter() {
            override fun onBeforeBrowse(
                browser: CefBrowser?, frame: CefFrame?, request: CefRequest?, userGesture: Boolean, isRedirect: Boolean,
            ): Boolean = request?.url?.let(::leavesPanel) ?: false
        }, browser.cefBrowser)
        browser.jbCefClient.addLifeSpanHandler(object : CefLifeSpanHandlerAdapter() {
            override fun onBeforePopup(
                browser: CefBrowser?, frame: CefFrame?, targetUrl: String?, targetFrameName: String?,
            ): Boolean {
                targetUrl?.let(::leavesPanel)
                return true // never a second Chromium window
            }
        }, browser.cefBrowser)
    }

    /** True when the navigation was handed to the IDE and the panel stays put. */
    private fun leavesPanel(url: String): Boolean {
        val uri = runCatching { URI(url) }.getOrNull() ?: return false
        return when (uri.scheme?.lowercase()) {
            "http", "https", "mailto" -> { BrowserUtil.browse(url); true }
            // The kit's "open in editor" row on macOS: idea://open?file=…&line=…
            "idea" -> { openIdeaLink(uri); true }
            "file" -> openLocal(uri)
            else -> false
        }
    }

    private fun openLocal(uri: URI): Boolean {
        val target = Path(uri.path)
        val rendered = current
        if (rendered != null && target == rendered.html) return false // our own (re)load
        if (target.startsWith(previews.outBase) && rendered == null) return false
        // A page of the same tree: the preview has `x.html`, the IDE wants `x.md`.
        val opened = rendered?.sourceOf(target) ?: target
        if (opened.startsWith(previews.outBase)) return false // error page and the like
        // `other.html#setup`: the reader asked for that heading, not for the
        // top of the file. URI.fragment is decoded, as heading ids are.
        open(opened, line = 0, anchor = uri.fragment?.takeIf { it.isNotEmpty() })
        return true
    }

    private fun openIdeaLink(uri: URI) {
        val query = uri.rawQuery ?: return
        val params = query.split("&").mapNotNull {
            val (k, v) = it.split("=", limit = 2).takeIf { p -> p.size == 2 } ?: return@mapNotNull null
            k to URLDecoder.decode(v, Charsets.UTF_8)
        }.toMap()
        val path = params["file"] ?: return
        open(Path(path), line = (params["line"]?.toIntOrNull() ?: 1) - 1, anchor = null)
    }

    /**
     * Open [path] at 0-based [line], or at the heading whose id is [anchor]
     * when oku finds one on that page (the id is oku's, so the line comes
     * from oku, not from a second copy of its slug rule here).
     *
     * Finding a file the IDE has not seen yet is a VFS refresh, which is not
     * UI-thread work: a chip naming a file outside the project, opened from
     * the page, tripped SlowOperations on the EDT. Only the opening is.
     */
    private fun open(path: Path, line: Int, anchor: String?) {
        cs.launch(Dispatchers.IO) {
            val target = LocalFileSystem.getInstance().refreshAndFindFileByNioFile(path)
            if (target == null) {
                log.info("oku preview: no file at $path")
                return@launch
            }
            val at = anchor?.takeIf { target.extension.equals("md", ignoreCase = true) }?.let { id ->
                // The open buffer, when there is one: the heading may have moved since the save.
                val text = readAction { FileDocumentManager.getInstance().getCachedDocument(target)?.text }
                previews.anchorLine(path, id, text)
                    .onFailure { log.info("oku preview: no line for #$id in $path: ${it.message}") }
                    .getOrNull()
                    ?.let { it - 1 }
            } ?: line
            log.info("oku preview: opens $path at line ${at + 1}" + (anchor?.let { " for #$it" } ?: ""))
            withContext(Dispatchers.EDT) {
                OpenFileDescriptor(project, target, at.coerceAtLeast(0), 0).navigate(true)
            }
        }
    }

    // ---- FileEditor -------------------------------------------------------

    override fun getComponent(): JComponent = browser.component
    override fun getPreferredFocusedComponent(): JComponent = browser.component
    override fun getName(): String = "oku"
    override fun getFile(): VirtualFile = file
    override fun setState(state: FileEditorState) = Unit
    override fun isModified(): Boolean = false
    override fun isValid(): Boolean = file.isValid

    // A failed render is otherwise retried only by the next edit, so a tab
    // the reader did not touch kept its error after the cause was fixed
    // (oku updated, a kit.json repaired). Coming back to the tab retries.
    override fun selectNotify() {
        if (failed) schedule(0)
    }
    override fun addPropertyChangeListener(listener: PropertyChangeListener) = Unit
    override fun removePropertyChangeListener(listener: PropertyChangeListener) = Unit
    override fun dispose() {
        cs.cancel()
        errorPage.close()
    }

    private companion object {
        const val EDIT_DELAY_MS = 300L
    }
}

/**
 * The page a preview shows in place of one it could not render, saying
 * why. One file per preview, so two failing previews do not show each
 * other's reason, and a new URL per failure: the browser skips a load of
 * the URL it last asked for, and a second reason would never reach it.
 */
internal class OkuErrorPage(dir: Path) {
    val file: Path = dir.resolve("error-${UUID.randomUUID()}.html")
    private val shown = AtomicInteger()

    /** [message] written into the page; the URL that loads it. */
    fun show(message: String): String {
        val escaped = message.replace("&", "&amp;").replace("<", "&lt;")
        Files.writeString(file, "<!doctype html><meta charset=utf-8><body style=\"font:13px system-ui;padding:16px\"><h3>oku preview</h3><pre style=\"white-space:pre-wrap\">$escaped</pre>")
        return "${file.toUri()}?r=${shown.incrementAndGet()}"
    }

    /** The preview is gone, and so is its page. */
    fun close() {
        Files.deleteIfExists(file)
    }
}
