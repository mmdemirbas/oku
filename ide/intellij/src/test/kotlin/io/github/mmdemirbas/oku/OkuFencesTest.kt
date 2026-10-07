package io.github.mmdemirbas.oku

import com.intellij.json.JsonLanguage
import com.intellij.lang.injection.InjectedLanguageManager
import com.intellij.openapi.components.service
import kotlin.io.path.Path

class OkuFencesTest : OkuFixtureTestCase() {

    private fun page(fence: String, body: String) = "---\ntitle: A\nsummary: a\n---\n\n## A {#a}\n\n```$fence\n$body\n```\n"

    /** What a real editor has by the time an author types: a session that greeted. */
    private fun open(text: String) {
        val file = tree("a.md" to text).getValue("a.md")
        service<OkuPreviewService>().check(Path(file.path), text).getOrThrow()
        fixture.openFileInEditor(file)
    }

    fun `test an oku fence is JSON`() {
        open(page("oku-table", """{"headers": ["x"]}"""))
        val at = fixture.editor.document.text.indexOf("headers")
        val inside = InjectedLanguageManager.getInstance(fixture.project).findInjectedElementAt(fixture.file, at)
        assertEquals(JsonLanguage.INSTANCE, inside?.containingFile?.language)
    }

    fun `test a fence body completes from the schema oku names for it`() {
        open(page("oku-chart", """{"type": "bar", "<caret>"}""").replace("<caret>", ""))
        val text = fixture.editor.document.text
        fixture.editor.caretModel.moveToOffset(text.indexOf("\"bar\", \"") + "\"bar\", \"".length)
        fixture.completeBasic()
        val offered = fixture.lookupElementStrings.orEmpty()
        assertTrue(offered.toString(), "rows" in offered && "title" in offered)
        assertFalse(offered.toString(), "headers" in offered) // a table's key, not a chart's
    }

    fun `test the fence tags are offered after the backticks`() {
        open(page("oku-chart", """{"type": "bar"}""") + "\n```oku-ta\n```\n")
        val text = fixture.editor.document.text
        fixture.editor.caretModel.moveToOffset(text.lastIndexOf("oku-ta") + "oku-ta".length)
        fixture.completeBasic()
        val offered = fixture.lookupElementStrings
        // One candidate is inserted at once and leaves no list behind.
        if (offered == null) assertTrue(fixture.editor.document.text.contains("```oku-table\n")) else assertTrue(offered.toString(), "oku-table" in offered)
    }
}
