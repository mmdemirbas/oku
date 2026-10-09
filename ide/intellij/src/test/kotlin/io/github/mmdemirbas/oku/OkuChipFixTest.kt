package io.github.mmdemirbas.oku

class OkuChipFixTest : OkuFixtureTestCase() {

    private val page = """
        ---
        title: A
        summary: a
        ---

        ## A {#a}

        Read `src/x.py` first, then `src/x.py:2`.

        A later paragraph that the fix does not touch.
    """.trimIndent() + "\n"

    fun `test a path in a code span becomes a file chip, and only the spans change`() {
        fixture.tempDirFixture.createFile("proj/src/x.py", "a = 1\nb = 2\n")
        fixture.openFileInEditor(tree("a.md" to page).getValue("a.md"))
        val document = fixture.editor.document
        val later = "A later paragraph"
        val marker = document.createRangeMarker(page.indexOf(later), page.indexOf(later) + later.length)
        fixture.editor.caretModel.moveToOffset(page.indexOf("`src/x.py`") + 2)

        val found = fixture.doHighlighting().filter { "path-in-code-span" in (it.description ?: "") }
        assertFalse(found.isEmpty())
        fixture.launchAction(fixture.findSingleIntention("Turn the paths in code spans into file chips"))

        val text = document.text
        assertTrue(text, "Read [`src/x.py`](#f/src/x.py) first, then [`src/x.py:2`](#f/src/x.py:2)." in text)
        // Written as the changes, not as a new text: a marker past them still holds its words.
        assertTrue(marker.isValid)
        assertEquals(later, text.substring(marker.startOffset, marker.endOffset))
        // And the check has nothing left to say about it.
        assertTrue(fixture.doHighlighting().none { "path-in-code-span" in (it.description ?: "") })
    }
}
