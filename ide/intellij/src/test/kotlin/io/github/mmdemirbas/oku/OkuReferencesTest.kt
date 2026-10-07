package io.github.mmdemirbas.oku

import com.intellij.codeInspection.InspectionManager
import com.intellij.codeInspection.LocalInspectionTool
import com.intellij.codeInspection.ex.InspectionToolRegistrar
import com.intellij.openapi.progress.EmptyProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.psi.PsiFile
import com.intellij.psi.PsiReference
import org.intellij.plugins.markdown.lang.psi.impl.MarkdownLinkDestination

class OkuReferencesTest : OkuFixtureTestCase() {

    private val links = listOf("#f/src/x.py", "#f/../src/x.py", "#f/src/x.py:2", "#g/term", "#x/ref", "#nowhere")

    private val page = "---\ntitle: A\nsummary: a\n---\n\n## A {#a}\n\n" +
        links.joinToString(" ") { "[l]($it)" } + "\n"

    private fun open(text: String = page) {
        fixture.tempDirFixture.createFile("proj/src/x.py", "a = 1\nb = 2\nc = 3\n")
        fixture.openFileInEditor(tree("a.md" to text).getValue("a.md"))
    }

    private fun destination(link: String): MarkdownLinkDestination {
        val at = fixture.editor.document.text.indexOf("($link)") + 2
        return requireNotNull(fixture.file.findElementAt(at)?.parent as? MarkdownLinkDestination) { link }
    }

    /**
     * The file following the link reaches. The Markdown plugin's own anchor
     * reference resolves to the page itself, which is not a target.
     */
    private fun target(link: String): PsiFile? =
        destination(link).references.firstNotNullOfOrNull { ref ->
            ((ref as PsiReference).resolve() as? PsiFile)?.takeIf { it != fixture.file }
        }

    fun `test a file reference reaches the file from the project root, beside the page, and with a line`() {
        open()
        for (link in listOf("#f/src/x.py", "#f/../src/x.py", "#f/src/x.py:2")) {
            assertEquals(link, "x.py", target(link)?.name)
        }
        assertNull(target("#g/term"))
    }

    fun `test the path completes segment by segment`() {
        open("---\ntitle: A\nsummary: a\n---\n\nSee [x](#f/sr).\n")
        fixture.editor.caretModel.moveToOffset(fixture.editor.document.text.indexOf("#f/sr") + "#f/sr".length)
        fixture.completeBasic()
        val offered = fixture.lookupElementStrings
        if (offered == null) assertTrue(fixture.editor.document.text.contains("#f/src")) else assertTrue(offered.toString(), "src" in offered)
    }

    /**
     * The Markdown plugin reads every `#…` link as a heading id and reports
     * the ones it cannot find — every oku link included. Its report stands
     * for a real missing heading.
     */
    fun `test an oku link is not reported as a heading the page lacks`() {
        open()
        fun reportedBy(tool: LocalInspectionTool): List<String> = ProgressManager.getInstance().runProcess<List<String>>({
            tool.processFile(fixture.file, InspectionManager.getInstance(fixture.project)).map { it.psiElement.text }
        }, EmptyProgressIndicator())
        // The premise, from an instance built from the class: it names itself
        // after the class, an id no suppressor is asked about, so this is what
        // the inspection finds. (The #f/ links resolve as files and are not.)
        @Suppress("UNCHECKED_CAST")
        val bare = (Class.forName(
            "org.intellij.plugins.markdown.model.psi.headers.UnresolvedHeaderReferenceInspection",
        ) as Class<out LocalInspectionTool>).getDeclaredConstructor().newInstance()
        assertEquals(listOf("#g/term", "#x/ref", "#nowhere"), reportedBy(bare))
        // As the IDE holds it, built from its registration — which is where
        // the id the suppressor answers to comes from.
        val registered = InspectionToolRegistrar.getInstance().createTools()
            .first { it.shortName == "MarkdownUnresolvedHeaderReference" }.tool as LocalInspectionTool
        assertEquals(listOf("#nowhere"), reportedBy(registered))
        assertEquals(listOf("#nowhere"), listOf("#g/term", "#x/ref", "#nowhere").filter { !registered.isSuppressedFor(destination(it)) })
    }

    fun `test a markdown file that is not an oku page is left alone`() {
        fixture.tempDirFixture.findOrCreateDir("plain/.git")
        fixture.tempDirFixture.createFile("plain/src/x.py", "a = 1\n")
        fixture.openFileInEditor(fixture.tempDirFixture.createFile("plain/README.md", "# R\n\n[l](#f/src/x.py)\n"))
        assertNull(target("#f/src/x.py"))
    }
}
