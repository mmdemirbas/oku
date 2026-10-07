package io.github.mmdemirbas.oku

import com.intellij.lang.annotation.HighlightSeverity
import com.intellij.openapi.command.WriteCommandAction

class OkuCheckAnnotatorTest : OkuFixtureTestCase() {

    private val other = "---\ntitle: B\nsummary: b\n---\n\n## B {#b}\n\nthe other page\n"

    private val page = """
        ---
        title: A
        summary: a
        ---

        ## A {#a}

        A link to [an anchor b.md lacks](b.md#nowhere).

        ```oku-table
        {"headers": ["x"], "rows": 3}
        ```
    """.trimIndent() + "\n"

    private fun findings(): List<Triple<HighlightSeverity, Int, String>> {
        val document = fixture.editor.document
        return fixture.doHighlighting()
            .filter { "[oku " in (it.description ?: "") }
            .map { Triple(it.severity, document.getLineNumber(it.startOffset) + 1, it.description) }
    }

    fun `test the page shows what oku check says, on the lines it says it about`() {
        val files = tree("a.md" to page, "b.md" to other)
        fixture.openFileInEditor(files.getValue("a.md"))
        val got = findings()
        // A finding about another page: the anchor b.md does not have.
        assertTrue(got.toString(), got.any { (sev, line, text) ->
            sev == HighlightSeverity.WARNING && line == 8 && "#nowhere" in text && "unresolved-anchor" in text
        })
        // The schema names the field, at the fence.
        assertTrue(got.toString(), got.any { (sev, line, text) ->
            sev == HighlightSeverity.ERROR && line == 10 && "rows: 3 is not of type 'array'" in text
        })
    }

    fun `test an unsaved edit is checked, not the file on disk`() {
        val files = tree("a.md" to page, "b.md" to other)
        fixture.openFileInEditor(files.getValue("a.md"))
        val document = fixture.editor.document
        WriteCommandAction.runWriteCommandAction(fixture.project) {
            document.insertString(document.textLength, "\nAnd [one more](#also-nowhere).\n")
        }
        val got = findings()
        assertTrue(got.toString(), got.any { (_, line, text) -> line == document.lineCount - 1 && "#also-nowhere" in text })
    }

    fun `test a page that is not an oku page gets nothing`() {
        fixture.tempDirFixture.findOrCreateDir("plain/.git")
        val readme = fixture.tempDirFixture.createFile("plain/README.md", "# Readme\n\n[x](#nowhere)\n")
        fixture.openFileInEditor(readme)
        assertEmpty(findings())
    }
}
