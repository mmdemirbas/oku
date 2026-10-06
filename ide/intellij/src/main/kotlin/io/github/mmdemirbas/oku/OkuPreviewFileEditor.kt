package io.github.mmdemirbas.oku

import com.intellij.ide.BrowserUtil
import com.intellij.ide.ui.LafManagerListener
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.runReadActionBlocking
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
 * Every edit re-renders through the installed oku tool, and the page is
 * reloaded; the page itself puts the reader back where they were. Links
 * leave the panel: another page or a `#f/` file opens in the IDE, a web
 * address opens in the system browser.
 */
class OkuPreviewFileEditor(
    private val project: Project,
    private val file: VirtualFile,
) : UserDataHolderBase(), FileEditor {

    private val log = logger<OkuPreviewFileEditor>()
    private val browser = JBCefBrowser()
    private val alarm = Alarm(Alarm.ThreadToUse.POOLED_THREAD, this)
    private val document = FileDocumentManager.getInstance().getDocument(file)

    @Volatile
    private var current: Rendered? = null

    private val generation = AtomicInteger()

    init {
        Disposer.register(this, browser)
        document?.addDocumentListener(object : DocumentListener {
            override fun documentChanged(event: DocumentEvent) = schedule(EDIT_DELAY_MS)
        }, this)
        ApplicationManager.getApplication().messageBus.connect(this)
            .subscribe(LafManagerListener.TOPIC, LafManagerListener { schedule(0) })
        installNavigation()
        schedule(0)
    }

    private fun schedule(delayMs: Int) {
        alarm.cancelAllRequests()
        alarm.addRequest(::render, delayMs)
    }

    private fun render() {
        val text = runReadActionBlocking { document?.text ?: VfsUtilCore.loadText(file) }
        val theme = if (JBColor.isBright()) "light" else "dark"
        OkuTool.render(Path(file.path), text, theme)
            .onSuccess {
                current = it
                // A new query per render: JBCefBrowserBase skips a load of
                // the URL it last requested ("URL already requested,
                // skipping"), so a re-render of the same page never reached
                // the panel.
                browser.loadURL("${it.html.toUri()}?r=${generation.incrementAndGet()}")
            }
            .onFailure {
                log.warn("oku preview failed for ${file.path}", it)
                showError(it.message ?: it.toString())
            }
    }

    private fun showError(message: String) {
        val page = OkuTool.outBase.resolve("error.html")
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
        if (target.startsWith(OkuTool.outBase) && rendered == null) return false
        // A page of the same tree: the preview has `x.html`, the IDE wants `x.md`.
        val source = if (rendered != null && target.startsWith(rendered.out)) {
            val rel = rendered.out.relativize(target)
            val asMd = rendered.root.resolve(rel).resolveSibling(rel.fileName.pathString.removeSuffix(".html") + ".md")
            if (target.extension == "html" && asMd.exists()) asMd else rendered.root.resolve(rel)
        } else target
        if (source.startsWith(OkuTool.outBase)) return false // error page and the like
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
    override fun addPropertyChangeListener(listener: PropertyChangeListener) = Unit
    override fun removePropertyChangeListener(listener: PropertyChangeListener) = Unit
    override fun dispose() = Unit

    private companion object {
        const val EDIT_DELAY_MS = 300
    }
}
