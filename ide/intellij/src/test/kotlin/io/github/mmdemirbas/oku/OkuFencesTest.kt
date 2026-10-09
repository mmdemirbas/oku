package io.github.mmdemirbas.oku

import com.google.gson.JsonParser
import com.intellij.codeInsight.lookup.Lookup
import com.intellij.codeInsight.lookup.impl.LookupImpl
import com.intellij.json.JsonLanguage
import com.intellij.lang.injection.InjectedLanguageManager
import com.intellij.openapi.components.service
import com.jetbrains.jsonSchema.impl.inspections.JsonSchemaComplianceInspection
import kotlin.io.path.Path

class OkuFencesTest : OkuFixtureTestCase() {

    private fun page(fence: String, body: String) = "---\ntitle: A\nsummary: a\n---\n\n## A {#a}\n\n```$fence\n$body\n```\n"

    /** What a real editor has by the time an author types: a session that greeted. */
    private fun open(text: String): com.intellij.openapi.vfs.VirtualFile {
        val file = tree("a.md" to text).getValue("a.md")
        service<OkuPreviewService>().check(Path(file.path), text).getOrThrow()
        fixture.openFileInEditor(file)
        return file
    }

    /** Complete at the end of the last [typed], and pick the item named [name]. */
    private fun pick(typed: String, name: String) {
        val text = fixture.editor.document.text
        fixture.editor.caretModel.moveToOffset(text.lastIndexOf(typed) + typed.length)
        fixture.completeBasic()
        val items = fixture.lookupElements ?: return // the one candidate was inserted at once
        (fixture.lookup as LookupImpl).currentItem = items.single { it.lookupString == name }
        fixture.finishLookup(Lookup.NORMAL_SELECT_CHAR)
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

    fun `test a fence body that breaks its schema is marked on the value that breaks it`() {
        // The schema oku names for a fence does more than complete keys: the
        // JSON support checks the fragment against it, and only inside the
        // project's content, as a page is in the IDE (see the fixture).
        fixture.enableInspections(JsonSchemaComplianceInspection::class.java)
        open(page("oku-chart", """{"type": "bar", "rows": 3}"""))
        val at = fixture.editor.document.text.indexOf("\"rows\": 3") + "\"rows\": ".length
        val marked = fixture.doHighlighting().filter {
            it.startOffset <= at && at < it.endOffset && "Incompatible types" in (it.description ?: "")
        }
        assertEquals(fixture.doHighlighting().map { "${it.startOffset}:${it.description}" }.toString(), 1, marked.size)
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

    fun `test picking a chart type writes the whole component, and the page checks clean`() {
        val file = open(page("oku-table", "{\"headers\": [\"x\"], \"rows\": [[\"1\"]]}") + "\n```oku-\n")
        pick("```oku-", "oku-chart sankey")
        val text = fixture.editor.document.text
        val fence = text.substring(text.lastIndexOf("```oku-chart\n"))
        // Closed, since nothing closed it, and holding oku's own sankey.
        assertTrue(fence, fence.trimEnd().endsWith("\n```") && fence.trimEnd() != "```oku-chart\n```")
        val body = fence.removePrefix("```oku-chart\n").trimEnd().removeSuffix("```")
        val snippet = service<OkuPreviewService>().greeting.snippets.single { it.type == "sankey" }
        assertEquals(JsonParser.parseString(snippet.body), JsonParser.parseString(body))
        val issues = service<OkuPreviewService>().check(Path(file.path), text).getOrThrow()
        assertEmpty(issues.filter { it.severity == "error" }.toString(), issues.filter { it.severity == "error" })
    }

    fun `test a fence that already has a body only gets its tag`() {
        open(page("oku-ta", "{\"headers\": [\"x\"]}"))
        pick("```oku-ta", "oku-table")
        val text = fixture.editor.document.text
        assertTrue(text, "```oku-table\n{\"headers\": [\"x\"]}\n```" in text)
        assertEquals(text, 1, Regex("\"headers\"").findAll(text).count())
    }
}
