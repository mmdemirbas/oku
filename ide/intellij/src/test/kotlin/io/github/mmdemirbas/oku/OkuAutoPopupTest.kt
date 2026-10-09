package io.github.mmdemirbas.oku

import com.intellij.openapi.application.WriteAction
import com.intellij.openapi.vfs.VfsUtil
import com.intellij.testFramework.EdtTestUtil
import com.intellij.testFramework.fixtures.CompletionAutoPopupTester

/**
 * What typing opens by itself. The platform opens the completion list on a
 * letter; the `!` of an alert and the `/` of an oku link are not letters,
 * so before [OkuAutoPopup] the list was there and nothing showed it.
 *
 * Off the EDT, as the platform's autopopup tester requires: it types on the
 * EDT and waits for the list from here.
 */
class OkuAutoPopupTest : OkuFixtureTestCase() {

    override fun runInDispatchThread(): Boolean = false

    private val head = "---\ntitle: A\nsummary: a\n---\n\n## A {#a}\n\n"

    /** What the list holds after [typed] is typed where `<caret>` is, in a tree whose kit.json is [kit]. */
    private fun shownAfterTyping(text: String, typed: String, kit: String? = null): List<String> {
        EdtTestUtil.runInEdtAndWait<Throwable> {
            val page = tree("a.md" to text.replace("<caret>", "")).getValue("a.md")
            if (kit != null) {
                WriteAction.run<Throwable> { VfsUtil.saveText(requireNotNull(page.parent.findChild("kit.json")), kit) }
            }
            fixture.openFileInEditor(page)
            fixture.editor.caretModel.moveToOffset(text.indexOf("<caret>"))
        }
        val tester = CompletionAutoPopupTester(fixture)
        var shown = emptyList<String>()
        tester.runWithAutoPopupEnabled {
            tester.typeWithPauses(typed)
            shown = EdtTestUtil.runInEdtAndGet<List<String>, Throwable> { tester.lookup?.items?.map { it.lookupString }.orEmpty() }
        }
        return shown
    }

    fun `test typing the bang of an alert opens its types`() {
        val shown = shownAfterTyping("$head> [<caret>\n", "!")
        assertTrue(shown.toString(), "NOTE" in shown && "TLDR" in shown)
    }

    fun `test typing the slash of a glossary link opens the terms`() {
        val kit = """{"name": "t", "domains": ["web"], "glossary": {"web": {"OurInternalTerm": {"en": {"def": "Ours."}}}}}"""
        val shown = shownAfterTyping("${head}See [t](#g<caret>).\n", "/", kit)
        assertTrue(shown.toString(), "OurInternalTerm" in shown && "Custom Elements" in shown)
    }

    fun `test a bang in a sentence opens nothing`() {
        assertEmpty(shownAfterTyping("${head}A sentence with [<caret>\n", "!"))
    }
}
