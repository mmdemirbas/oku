package io.github.mmdemirbas.oku

import com.intellij.codeInsight.lookup.Lookup
import com.intellij.codeInsight.lookup.LookupElementPresentation
import com.intellij.codeInsight.lookup.impl.LookupImpl

class OkuWritingTest : OkuFixtureTestCase() {

    private val head = "---\ntitle: A\nsummary: a\n---\n\n## A {#a}\n\n"

    private fun openAt(text: String) {
        fixture.openFileInEditor(tree("a.md" to text.replace("<caret>", "")).getValue("a.md"))
        fixture.editor.caretModel.moveToOffset(text.indexOf("<caret>"))
    }

    fun `test an alert completes the types the kit draws, with what each is for`() {
        openAt("$head> [!<caret>\n> The body.\n")
        fixture.completeBasic()
        val items = fixture.lookupElements.orEmpty()
        val types = items.map { it.lookupString }
        // Exactly the greeting's, which oku holds against the renderer.
        assertEquals(service().greeting.admonitions.keys.sorted(), types.sorted())
        val tip = LookupElementPresentation.renderElement(items.single { it.lookupString == "TIP" }).tailText.orEmpty()
        assertTrue(tip, "better way" in tip)
    }

    fun `test a type typed in lower case is written in capitals and closed`() {
        openAt("$head> [!wa<caret>\n> The body.\n")
        fixture.completeBasic()
        (fixture.lookup as LookupImpl).currentItem = fixture.lookupElements.orEmpty().single { it.lookupString == "WARNING" }
        fixture.finishLookup(Lookup.NORMAL_SELECT_CHAR)
        assertTrue(fixture.editor.document.text, "> [!WARNING]\n> The body." in fixture.editor.document.text)
    }

    fun `test a bracket that is already closed is not closed twice`() {
        openAt("$head> [!TL<caret>]\n> The page in one line.\n")
        fixture.completeBasic()
        assertTrue(fixture.editor.document.text, "> [!TLDR]\n" in fixture.editor.document.text)
        assertEquals(fixture.editor.document.text.indexOf("]") + 1, fixture.editor.caretModel.offset)
    }

    fun `test a bracket outside a blockquote is not an alert`() {
        openAt("${head}A [!<caret> in a sentence.\n")
        fixture.completeBasic()
        assertFalse(fixture.lookupElementStrings.orEmpty().toString(), "NOTE" in fixture.lookupElementStrings.orEmpty())
    }

    private fun service() = com.intellij.openapi.components.service<OkuPreviewService>()
}
