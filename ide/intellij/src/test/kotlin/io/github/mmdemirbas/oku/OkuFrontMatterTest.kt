package io.github.mmdemirbas.oku

/**
 * The front matter of an oku page completes from oku's front-matter schema
 * (the greeting's `front_matter`), and `parent:` from the pages of the tree.
 * Before this the Markdown plugin's generic schema answered: Jekyll's keys,
 * and nothing for `summary`, `order` or `parent`.
 */
class OkuFrontMatterTest : OkuFixtureTestCase() {

    private val body = "\n## A {#a}\n\nfirst\n"

    /** Complete where `<caret>` is written in the page [name] of a tree holding [pages]. */
    private fun offered(name: String, vararg pages: Pair<String, String>): List<String> {
        val files = tree(*pages.map { (n, t) -> n to t.replace("<caret>", "") }.toTypedArray())
        val text = pages.toMap().getValue(name)
        fixture.openFileInEditor(files.getValue(name))
        fixture.editor.caretModel.moveToOffset(text.indexOf("<caret>"))
        fixture.completeBasic()
        return fixture.lookupElementStrings.orEmpty()
    }

    fun `test a key completes from oku's front-matter schema`() {
        val keys = offered("a.md", "a.md" to "---\ntitle: A\n<caret>\n---\n$body")
        for (key in listOf("summary", "order", "parent", "accent", "read_time", "documents_history")) {
            assertTrue("$key not in $keys", key in keys)
        }
    }

    fun `test an accent completes the kit's colours`() {
        val values = offered("a.md", "a.md" to "---\ntitle: A\naccent: <caret>\n---\n$body")
        assertTrue(values.toString(), values.containsAll(listOf("teal", "amber", "indigo")))
    }

    fun `test a parent completes from the tree's pages, and not the page itself`() {
        val ids = offered(
            "guide/intro.md",
            "index.md" to "---\ntitle: Home\n---\n$body",
            "guide.md" to "---\ntitle: The guide\n---\n$body",
            "guide/intro.md" to "---\ntitle: Intro\nparent: <caret>\n---\n$body",
            "intro.md" to "---\ntitle: Root intro\n---\n$body",
        )
        assertTrue(ids.toString(), ids.containsAll(listOf("index", "guide", "intro")))
        // Its own id is the longest one its path ends with; `intro`, a page
        // at the root, is another page.
        assertFalse(ids.toString(), "guide/intro" in ids)
    }

    fun `test a markdown file that is not an oku page keeps the Markdown plugin's front matter`() {
        fixture.tempDirFixture.findOrCreateDir("plain/.git")
        val text = "---\ntitle: A\n<caret>\n---\n\nplain\n"
        val readme = fixture.tempDirFixture.createFile("plain/README.md", text.replace("<caret>", ""))
        fixture.openFileInEditor(readme)
        fixture.editor.caretModel.moveToOffset(text.indexOf("<caret>"))
        fixture.completeBasic()
        val keys = fixture.lookupElementStrings.orEmpty()
        assertFalse(keys.toString(), "documents_history" in keys || "read_time" in keys)
    }
}
