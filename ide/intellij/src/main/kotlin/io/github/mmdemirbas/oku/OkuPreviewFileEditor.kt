package io.github.mmdemirbas.oku

import com.intellij.ide.BrowserUtil
import com.intellij.ide.ui.LafManagerListener
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.runReadActionBlocking
import com.intellij.openapi.components.service
import com.intellij.openapi.diagnostic.logger
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
import com.intellij.ui.JBColor
import com.intellij.ui.jcef.JBCefBrowser
import com.intellij.util.Alarm
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
import java.util.concurrent.atomic.AtomicInteger
import javax.swing.JComponent
import kotlin.io.path.Path
import kotlin.io.path.exists
import kotlin.io.path.extension
import kotlin.io.path.pathString

/**
 * The kit's own rendering of one oku page, in the IDE's embedded Chromium.
 *
 * Every edit re-renders through `oku preview --serve`. When only the page
 * changed, the new page is handed to the one on screen (`OkuRenderer.update`
 * in the kit), which keeps every block the edit did not touch and the
 * reader's place; anything else reloads. Links leave the panel: another
 * page or a `#f/` file opens in the IDE, a web address opens in the system
 * browser.
 */
class OkuPreviewFileEditor(
    private val project: Project,
    private val file: VirtualFile,
) : UserDataHolderBase(), FileEditor {

    private val log = logger<OkuPreviewFileEditor>()
    private val browser = JBCefBrowser()
    private val alarm = Alarm(Alarm.ThreadToUse.POOLED_THREAD, this)
    private val document = FileDocumentManager.getInstance().getDocument(file)
    private val previews = service<OkuPreviewService>()

    @Volatile
    private var current: Rendered? = null

    private val generation = AtomicInteger()

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
        document?.addDocumentListener(object : DocumentListener {
            override fun documentChanged(event: DocumentEvent) = schedule(EDIT_DELAY_MS)
        }, this)
        ApplicationManager.getApplication().messageBus.connect(this)
            .subscribe(LafManagerListener.TOPIC, LafManagerListener { schedule(0) })
        installNavigation()
        browser.jbCefClient.addLoadHandler(object : CefLoadHandlerAdapter() {
            override fun onLoadingStateChange(
                browser: CefBrowser?, isLoading: Boolean, canGoBack: Boolean, canGoForward: Boolean,
            ) {
                if (!isLoading) loading = false
            }
        }, browser.cefBrowser)
        schedule(0)
    }

    private fun schedule(delayMs: Int) {
        alarm.cancelAllRequests()
        alarm.addRequest(::render, delayMs)
    }

    private fun render() {
        val text = runReadActionBlocking { document?.text ?: VfsUtilCore.loadText(file) }
        val theme = if (JBColor.isBright()) "light" else "dark"
        previews.render(Path(file.path), text, theme)
            .onSuccess {
                current = it
                failed = false
                val before = shown
                shown = it
                if (!loading && before != null && before.html == it.html && before.shell == it.shell) {
                    update(it)
                } else {
                    load(it)
                }
            }
            .onFailure {
                failed = true
                log.warn("oku preview failed for ${file.path}", it)
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
    private fun update(rendered: Rendered) {
        val page = Files.readString(rendered.page)
        val script = "(function (p) {" +
            "try { if (window.__okuRendered && window.OkuRenderer && OkuRenderer.prototype.update" +
            " && new OkuRenderer({}).update(p)) return; }" +
            " catch (e) { console.error('[oku preview] update failed, reloading', e); }" +
            " location.reload(); })($page);"
        browser.cefBrowser.executeJavaScript(script, rendered.html.toUri().toString(), 0)
    }

    private fun showError(message: String) {
        shown = null
        val page = previews.outBase.resolve("error.html")
        val escaped = message.replace("&", "&amp;").replace("<", "&lt;")
        Files.writeString(page, "<!doctype html><meta charset=utf-8><body style=\"font:13px system-ui;padding:16px\"><h3>oku preview</h3><pre style=\"white-space:pre-wrap\">$escaped</pre>")
        browser.loadURL(page.toUri().toString())
    }

    // ---- links ------------------------------------------------------------

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
        val source = if (rendered != null && target.startsWith(rendered.out)) {
            val rel = rendered.out.relativize(target)
            val asMd = rendered.root.resolve(rel).resolveSibling(rel.fileName.pathString.removeSuffix(".html") + ".md")
            if (target.extension == "html" && asMd.exists()) asMd else rendered.root.resolve(rel)
        } else target
        if (source.startsWith(previews.outBase)) return false // error page and the like
        open(source, line = 0)
        return true
    }

    private fun openIdeaLink(uri: URI) {
        val query = uri.rawQuery ?: return
        val params = query.split("&").mapNotNull {
            val (k, v) = it.split("=", limit = 2).takeIf { p -> p.size == 2 } ?: return@mapNotNull null
            k to URLDecoder.decode(v, Charsets.UTF_8)
        }.toMap()
        val path = params["file"] ?: return
        open(Path(path), line = (params["line"]?.toIntOrNull() ?: 1) - 1)
    }

    private fun open(path: Path, line: Int) {
        ApplicationManager.getApplication().invokeLater {
            val target = LocalFileSystem.getInstance().refreshAndFindFileByNioFile(path)
            if (target == null) {
                log.info("oku preview: no file at $path")
                return@invokeLater
            }
            OpenFileDescriptor(project, target, line.coerceAtLeast(0), 0).navigate(true)
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
    override fun dispose() = Unit

    private companion object {
        const val EDIT_DELAY_MS = 300
    }
}
