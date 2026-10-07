package io.github.mmdemirbas.oku

import com.intellij.openapi.components.service
import kotlin.io.path.Path

/**
 * A link to `other.md#setup` followed from the preview opens the page at
 * that heading. The line comes from oku, which knows its own ids.
 */
class OkuAnchorTest : OkuFixtureTestCase() {

    private val page = """
        ---
        title: A
        ---

        ## Setup {#setup}

        text

        ## Özet
    """.trimIndent() + "\n"

    fun `test a heading id is answered with the line it is on, from the buffer when there is one`() {
        val files = tree("a.md" to page)
        val path = Path(files.getValue("a.md").path)
        val previews = service<OkuPreviewService>()
        assertEquals(5, previews.anchorLine(path, "setup", null).getOrThrow())
        assertEquals(9, previews.anchorLine(path, "özet", null).getOrThrow())
        assertNull(previews.anchorLine(path, "nowhere", null).getOrThrow())
        // Two lines typed above it and not saved: the buffer's line, not the file's.
        assertEquals(7, previews.anchorLine(path, "setup", page.replace("---\n\n", "---\n\nnew\n\n")).getOrThrow())
    }
}
