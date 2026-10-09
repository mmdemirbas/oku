package io.github.mmdemirbas.oku

import com.intellij.openapi.components.service
import com.intellij.openapi.vfs.VfsUtilCore
import com.intellij.openapi.vfs.VirtualFile
import java.io.File
import java.nio.file.Path
import java.util.concurrent.TimeUnit
import kotlin.io.path.Path
import kotlin.io.path.readText

/**
 * A tree's `index.html` — the shell `oku init` writes — opens as the page it
 * is the door to: the `.md` beside it, or with none the tree's front door,
 * whose rows open the pages' sources. It used to open as markup.
 */
class OkuShellTest : OkuFixtureTestCase() {

    private val page = "---\ntitle: A\nsummary: a\n---\n\n## A {#a}\n\nfirst\n"

    /** The shell the oku under test writes, so the sniff is held against the real one. */
    private fun init(dir: VirtualFile): VirtualFile {
        val run = ProcessBuilder(System.getProperty("oku.executable"), "init")
            .directory(File(dir.path))
            .redirectErrorStream(true)
            .start()
        val said = run.inputStream.readAllBytes().toString(Charsets.UTF_8)
        assertTrue(said, run.waitFor(60, TimeUnit.SECONDS) && run.exitValue() == 0)
        dir.refresh(false, true)
        return requireNotNull(dir.findChild("index.html")) { said }
    }

    private fun real(file: VirtualFile): Path = Path(file.path).toRealPath()

    fun `test a tree's index html is a shell, and markup with a body of its own is not`() {
        val files = tree("a.md" to page)
        val index = init(files.getValue("a.md").parent)
        val shell = VfsUtilCore.loadText(index)
        assertTrue(OkuPages.isShell(index))
        assertNull(OkuPages.pageOf(index))
        // A page's own stub shows the page beside it.
        val stub = fixture.tempDirFixture.createFile("proj/docs/a.html", shell)
        assertTrue(OkuPages.isShell(stub))
        assertEquals(files.getValue("a.md"), OkuPages.pageOf(stub))
        // A stub with no page beside it has nothing to show.
        assertFalse(OkuPages.isShell(fixture.tempDirFixture.createFile("proj/docs/orphan.html", shell)))
        // A page that uses the kit for its chrome writes its own body.
        val own = shell.replace(Regex("<body></body>"), "<body><main><h1>Own</h1></main></body>")
        assertFalse(OkuPages.isShell(fixture.tempDirFixture.createFile("proj/docs/sub/index.html", own)))
        // Outside a tree that declares itself, the same markup is not oku's.
        assertFalse(OkuPages.isShell(fixture.tempDirFixture.createFile("elsewhere/index.html", shell)))
        OkuSettings.get().state.enabled = false
        try {
            assertFalse(OkuPages.isShell(index))
        } finally {
            OkuSettings.get().loadState(OkuSettings.Options())
        }
    }

    fun `test the front door renders with no page, and its rows open the pages' sources`() {
        val files = tree("a.md" to page, "b.md" to page.replace("title: A", "title: B"))
        val index = init(files.getValue("a.md").parent)
        val previews = service<OkuPreviewService>()
        val front = previews.render(Path(index.path), null, "light").getOrThrow()
        assertNull(front.page)
        assertFalse("id=\"__oku_page__\"" in front.html.readText())
        assertEquals(real(files.getValue("a.md")), front.sourceOf(front.out.resolve("a.html")).toRealPath())
        // A link to the front door is a link to its shell, which opens as this.
        assertEquals(real(index), front.sourceOf(front.html).toRealPath())

        // With an index.md beside it, the shell is that page's door.
        val home = fixture.tempDirFixture.createFile("proj/docs/index.md", "---\ntitle: Home\n---\n\nhome\n")
        assertEquals(home, OkuPages.pageOf(index))
        val rendered = previews.render(Path(home.path), VfsUtilCore.loadText(home), "light").getOrThrow()
        assertNotNull(rendered.page)
        assertEquals(rendered.html, front.html)
        assertEquals(real(home), rendered.sourceOf(rendered.html).toRealPath())
    }
}
