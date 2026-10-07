package io.github.mmdemirbas.oku

import com.intellij.notification.Notification
import com.intellij.notification.Notifications
import com.intellij.openapi.components.service
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.testFramework.PlatformTestUtil

/**
 * What the settings decide: which oku runs, whether oku pages are oku pages
 * at all, and what an oku page does when no oku can draw it.
 */
class OkuSettingsTest : OkuFixtureTestCase() {

    private val page = "---\ntitle: A\nsummary: a\n---\n\n## A {#a}\n\nA link to [nowhere](#nowhere).\n"

    /** The checkout's oku the tests run, which `-Doku.executable` names. */
    private val checkout: String = System.getProperty("oku.executable")

    override fun tearDown() {
        try {
            System.setProperty("oku.executable", checkout)
            OkuSettings.get().loadState(OkuSettings.Options())
            OkuFallbackNotifier.forget()
            service<OkuPreviewService>().restart()
        } catch (e: Throwable) {
            addSuppressedException(e)
        } finally {
            super.tearDown()
        }
    }

    /** As the IDE runs for a reader: no `-Doku.executable`, the settings say which oku. */
    private fun chooseOku(path: String?) {
        System.clearProperty("oku.executable")
        OkuSettings.get().state.executable = path
        service<OkuPreviewService>().restart()
    }

    fun `test the oku set in the settings is the one that runs, and one that does not run is said, not passed over`() {
        chooseOku(checkout)
        assertEquals(OkuLaunch.Found(kotlin.io.path.Path(checkout)), OkuLauncher.find())
        chooseOku("/no/such/oku")
        val missing = OkuLauncher.find()
        assertTrue(missing.toString(), missing is OkuLaunch.Missing && "/no/such/oku" in missing.reason)
    }

    fun `test switched off, no markdown file is an oku page and nothing of oku runs`() {
        val files = tree("a.md" to page)
        assertTrue(OkuPages.isOkuPage(files.getValue("a.md")))
        OkuSettings.get().state.enabled = false
        assertFalse(OkuPages.isOkuPage(files.getValue("a.md")))
        assertNull(OkuFenceLanguageProvider().getLanguageByInfoString("oku-chart"))
        fixture.openFileInEditor(files.getValue("a.md"))
        assertEmpty(fixture.doHighlighting().filter { "oku" in (it.description ?: "") })
    }

    fun `test without oku an oku page is not taken, and the first one says why, once`() {
        val files = tree("a.md" to page, "b.md" to page)
        chooseOku("/no/such/oku")
        assertFalse(OkuPreviewProvider().accept(fixture.project, files.getValue("a.md")))
        assertFalse(OkuPreviewEditorProvider().accept(fixture.project, files.getValue("a.md")))

        val said = mutableListOf<Notification>()
        fixture.project.messageBus.connect(fixture.testRootDisposable)
            .subscribe(Notifications.TOPIC, object : Notifications {
                override fun notify(notification: Notification) {
                    said += notification
                }
            })
        val editors = FileEditorManager.getInstance(fixture.project)
        editors.openFile(files.getValue("a.md"), true)
        editors.openFile(files.getValue("b.md"), true)
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
        val ours = said.filter { it.groupId == "oku" }
        assertEquals(said.toString(), 1, ours.size)
        assertTrue(ours.single().content, "a.md" in ours.single().content && "/no/such/oku" in ours.single().content)
    }

    fun `test a check that did not run says so at the top of the page`() {
        val files = tree("a.md" to page)
        // A program that runs and is not oku: the session never greets.
        chooseOku("/usr/bin/true")
        fixture.openFileInEditor(files.getValue("a.md"))
        val banner = fixture.doHighlighting().filter { (it.description ?: "").startsWith("oku check did not run") }
        assertEquals(banner.toString(), 1, banner.size)
        assertTrue(banner.single().isFileLevelAnnotation)
    }

    fun `test without any oku the page gets no banner, the notification has said it`() {
        val files = tree("a.md" to page)
        chooseOku("/no/such/oku")
        fixture.openFileInEditor(files.getValue("a.md"))
        assertEmpty(fixture.doHighlighting().filter { "oku" in (it.description ?: "") })
    }
}
