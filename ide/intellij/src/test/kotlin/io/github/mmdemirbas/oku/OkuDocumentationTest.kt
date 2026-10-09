package io.github.mmdemirbas.oku

import com.intellij.lang.documentation.ide.IdeDocumentationTargetProvider
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.WriteAction
import com.intellij.openapi.vfs.VfsUtil
import com.intellij.platform.backend.documentation.impl.computeDocumentationBlocking
import java.util.concurrent.Callable
import java.util.concurrent.TimeUnit

/** What hovering a name on an oku page shows: what its reader will see, or why there is nothing. */
class OkuDocumentationTest : OkuFixtureTestCase() {

    private val head = "---\ntitle: A\nsummary: a\n---\n\n## A {#a}\n\n"

    private val kit = """{"name": "t", "domains": ["web"], "glossary": {"web": {"OurInternalTerm": {"en": {"def": "Ours, and <b>nobody</b> else's."}}}}}"""

    /** Every documentation the IDE has for the place just inside [at] — through the IDE's own lookup, so the registration is held too. */
    private fun hover(text: String, at: String): String {
        val page = tree("a.md" to text).getValue("a.md")
        WriteAction.runAndWait<Throwable> { VfsUtil.saveText(requireNotNull(page.parent.findChild("kit.json")), kit) }
        fixture.openFileInEditor(page)
        val offset = text.indexOf(at) + 1
        val targets = IdeDocumentationTargetProvider.getInstance(fixture.project).documentationTargets(fixture.editor, fixture.file, offset)
        val pointers = targets.map { it.createPointer() }
        // Off the EDT, as the IDE computes it: a registry name is a round trip to oku.
        return ApplicationManager.getApplication().executeOnPooledThread(Callable {
            pointers.joinToString("\n") { computeDocumentationBlocking(it)?.html.orEmpty() }
        }).get(60, TimeUnit.SECONDS)
    }

    fun `test a glossary term shows the definition its reader sees`() {
        val html = hover("${head}See [t](#g/OurInternalTerm).\n", "#g/OurInternalTerm")
        assertTrue(html, "Ours, and nobody else" in html && "web" in html)
    }

    fun `test a term the tree cannot name says the check reports it`() {
        val html = hover("${head}See [t](#g/Nowhere).\n", "#g/Nowhere")
        assertTrue(html, "Nowhere" in html && "oku check" in html)
    }

    fun `test a fence tag shows what the component is, its keys and oku's example`() {
        val html = hover("$head```oku-table\n{\"headers\": [\"x\"], \"rows\": [[\"1\"]]}\n```\n", "oku-table")
        assertTrue(html, "Sortable" in html && "headers" in html && "<pre>" in html)
    }

    fun `test an alert shows what its type is for`() {
        val html = hover("$head> [!TIP]\n> Use the other way.\n", "TIP")
        assertTrue(html, "better way" in html)
    }
}
