package io.github.mmdemirbas.oku

import com.intellij.testFramework.UsefulTestCase
import java.net.URI
import java.nio.file.Files
import kotlin.io.path.Path
import kotlin.io.path.exists
import kotlin.io.path.readText

/** The page a preview shows when it could not render, which a test can read without a browser. */
class OkuErrorPageTest : UsefulTestCase() {

    fun `test each preview has its own error page, and a new reason is a new URL`() {
        // XI.1: every preview wrote one error.html and loaded it by one URL.
        // Two previews failing at once showed each other's reason, and a
        // second failure in the same preview loaded the URL it last asked
        // for, which the browser skips, so the first reason stayed up.
        val dir = Files.createTempDirectory("oku-error-page")
        try {
            assertOwnPages(dir)
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    private fun assertOwnPages(dir: java.nio.file.Path) {
        val a = OkuErrorPage(dir)
        val b = OkuErrorPage(dir)
        val first = a.show("first reason")
        val other = b.show("the other preview's reason")
        val second = a.show("second reason")
        assertFalse("a second reason loads the URL the browser just loaded", first == second)
        val shown = Path(URI(second).path)
        assertTrue(shown.readText().contains("second reason"))
        assertFalse("two previews share one error page", shown == Path(URI(other).path))
        a.close()
        assertFalse("a closed preview leaves its error page behind", shown.exists())
    }
}
