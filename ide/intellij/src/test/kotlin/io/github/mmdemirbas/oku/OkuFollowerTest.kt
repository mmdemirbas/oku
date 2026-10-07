package io.github.mmdemirbas.oku

import com.intellij.openapi.editor.LogicalPosition
import com.intellij.testFramework.EditorTestUtil
import com.intellij.testFramework.PlatformTestUtil
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlin.math.abs
import kotlin.math.floor

/**
 * The page follows the editor, through the real path: an editor scrolled in
 * code, its visible-area listener, the frame-limited flow on the EDT, and
 * the lines the page would have been sent. In the IDE this is measured by
 * pressing keys in a sandbox, which needs the sandbox in front; this needs
 * nothing.
 */
class OkuFollowerTest : OkuFixtureTestCase() {

    private val sent = mutableListOf<Double>()
    private var pageReady = true
    private lateinit var scope: CoroutineScope
    private lateinit var follower: OkuFollower

    override fun setUp() {
        super.setUp()
        fixture.configureByText("a.txt", (1..400).joinToString("\n") { "line $it" })
        EditorTestUtil.setEditorVisibleSize(fixture.editor, 80, 30)
        fixture.editor.scrollingModel.disableAnimation()
        scope = CoroutineScope(SupervisorJob())
        follower = OkuFollower(
            fixture.editor, scope, fixture.testRootDisposable,
            ready = { force -> pageReady || force },
            send = { sent += it },
        )
    }

    override fun tearDown() {
        try {
            scope.cancel()
        } catch (e: Throwable) {
            addSuppressedException(e)
        } finally {
            super.tearDown()
        }
    }

    /** One pixel of a line, as a share of it: how close a line read off pixels can be. */
    private val onePixel get() = 1.0 / fixture.editor.lineHeight

    private fun scrollTo(line: Double) {
        val editor = fixture.editor
        val start = editor.logicalPositionToXY(LogicalPosition(floor(line).toInt() - 1, 0)).y
        editor.scrollingModel.scrollVertically(start + ((line - floor(line)) * editor.lineHeight).toInt())
    }

    private fun assertSentLast(line: Double) {
        PlatformTestUtil.waitWithEventsDispatching(
            { "the page was not sent line $line; it was sent $sent" },
            { sent.isNotEmpty() && abs(sent.last() - line) <= onePixel },
            5,
        )
    }

    /** Long enough for anything queued to have run: several frames, pumped. */
    private fun settle() {
        repeat(10) {
            PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
            Thread.sleep(OkuFollower.FRAME_MS)
        }
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
    }

    fun `test the page is sent the line at the editor's top as the editor scrolls`() {
        scrollTo(100.0)
        assertSentLast(100.0)
        scrollTo(250.5)
        assertSentLast(250.5)
    }

    fun `test a scroll made while the page waits out a frame still reaches the page`() {
        scrollTo(40.0)
        // The follow for 40 runs here, and its frame's wait begins. The wait
        // can only end on the EDT, which this test holds until it asks.
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
        scrollTo(41.0)
        scrollTo(300.0)
        assertSentLast(300.0)
    }

    fun `test a page that cannot take a line gets it when forced, and an unmoved line is not sent twice`() {
        pageReady = false
        scrollTo(50.0)
        settle()
        assertEmpty(sent)
        follower.follow(force = true)
        assertSentLast(50.0)
        pageReady = true
        follower.follow(force = false)
        settle()
        assertEquals(sent.toString(), 1, sent.size)
    }

    fun `test a double-click on a line just under the editor's top leaves the editor where the page is`() {
        // The clicked heading sits 0.81 of a line under the page's top. The
        // editor's scroll offset wants the caret a full line from the edge,
        // and scrolling the caret into view to honour that moved the editor
        // a third of its height: measured in the sandbox, editor top 164.59
        // against page top 177.19.
        assertEquals(1, fixture.editor.settings.verticalScrollOffset)
        val after = follower.reveal(line = 178, top = 177.19)!!
        assertTrue("page top 177.19, editor top $after", abs(after - 177.19) <= onePixel)
        assertEquals(177, fixture.editor.caretModel.logicalPosition.line)
    }

    fun `test a double-click puts the editor where the page is, and that is not sent back`() {
        val after = follower.reveal(line = 160, top = 150.25)!!
        assertTrue("editor top $after, page top 150.25", abs(after - 150.25) <= onePixel)
        assertEquals(159, fixture.editor.caretModel.logicalPosition.line)
        assertEquals(after, follower.topLine())
        // The caret off the page's screen: the editor scrolls on to show it.
        val further = follower.reveal(line = 380, top = 10.0)!!
        assertTrue("editor top $further should show line 380", further > 10.0 && further <= 380.0)
        settle()
        assertEmpty(sent)
    }
}
