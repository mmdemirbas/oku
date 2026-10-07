package io.github.mmdemirbas.oku

import com.intellij.openapi.Disposable
import com.intellij.openapi.application.EDT
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.editor.LogicalPosition
import com.intellij.openapi.editor.ScrollType
import com.intellij.openapi.editor.event.VisibleAreaListener
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.launch
import java.awt.Point
import kotlin.math.abs
import kotlin.math.floor

/**
 * The two directions between a text editor and the page beside it, kept
 * apart from the browser so a test can scroll an editor and read what the
 * page would have been sent.
 *
 * Editor to page: every scroll of [editor] sends its top line ([topLine]) to
 * [send] — on the leading edge, then at most once a frame, because a scroll
 * fires for every pixel and the page needs the latest position, not each
 * one. [ready] says whether the page can take a line now; `force` asks
 * whether it should even when the line has not moved (a page that just
 * loaded starts at its top, wherever the editor is).
 *
 * Page to editor: [reveal] puts the editor where the page is and the caret
 * on a line, and records that position as sent, so it does not come back.
 */
internal class OkuFollower(
    val editor: Editor,
    scope: CoroutineScope,
    parent: Disposable,
    private val ready: (force: Boolean) -> Boolean,
    private val send: (line: Double) -> Unit,
) {
    private val scrolls = MutableSharedFlow<Unit>(extraBufferCapacity = 1, onBufferOverflow = BufferOverflow.DROP_OLDEST)

    /** The editor's top line the page was last put at; EDT only. */
    private var followed = Double.NaN

    init {
        editor.scrollingModel.addVisibleAreaListener(VisibleAreaListener { scrolls.tryEmit(Unit) }, parent)
        scope.launch(Dispatchers.EDT, start = CoroutineStart.UNDISPATCHED) {
            scrolls.collect {
                follow(force = false)
                delay(FRAME_MS)
            }
        }
    }

    /** Send the editor's top line to the page, unless it is already there. EDT only. */
    fun follow(force: Boolean) {
        if (editor.isDisposed || !ready(force)) return
        val top = topLine() ?: return
        if (!force && abs(top - followed) < 1e-6) return
        followed = top
        send(top)
    }

    /**
     * The page's double-click: the caret goes to [line], and the editor is
     * scrolled so its top is the page's top ([top]), which leaves what the
     * reader clicked where it was on the page. Only if that would hide the
     * caret does the editor scroll further. Returns the editor's top after.
     * EDT only.
     */
    fun reveal(line: Int, top: Double?): Double? {
        val lines = editor.document.lineCount
        if (editor.isDisposed || lines == 0) return null
        val scrolling = editor.scrollingModel
        scrolling.disableAnimation()
        try {
            if (top != null && top.isFinite()) {
                val at = (floor(top).toInt() - 1).coerceIn(0, lines - 1)
                val (start, end) = lineSpan(at)
                scrolling.scrollVertically(start + ((top - floor(top)) * (end - start)).toInt())
            }
            editor.caretModel.moveToLogicalPosition(LogicalPosition((line - 1).coerceIn(0, lines - 1), 0))
            // Not on every reveal: the clicked line is often less than a line
            // under the top, inside the editor's scroll offset, and making the
            // caret "visible" there moves the editor a third of its height.
            if (!caretShown()) scrolling.scrollToCaret(ScrollType.MAKE_VISIBLE)
        } finally {
            scrolling.enableAnimation()
        }
        // The scroll just made is the page's own position: not one to send back.
        followed = topLine() ?: Double.NaN
        return followed
    }

    /** The caret's whole row is inside the editor's visible area. */
    private fun caretShown(): Boolean {
        val area = editor.scrollingModel.visibleArea
        val y = editor.visualPositionToXY(editor.caretModel.visualPosition).y
        return y >= area.y && y + editor.lineHeight <= area.y + area.height
    }

    /** The 1-based source line at the editor's top, with the part of it scrolled past. */
    fun topLine(): Double? {
        val lines = editor.document.lineCount
        if (lines == 0) return null
        val y = editor.scrollingModel.visibleArea.y
        val line = editor.xyToLogicalPosition(Point(0, y)).line.coerceIn(0, lines - 1)
        val (start, end) = lineSpan(line)
        val part = if (end > start) ((y - start).toDouble() / (end - start)).coerceIn(0.0, 1.0) else 0.0
        return line + 1 + part
    }

    /** Where 0-based logical [line] starts and ends in the editor, soft wraps and folds included. */
    private fun lineSpan(line: Int): Pair<Int, Int> {
        val start = editor.logicalPositionToXY(LogicalPosition(line, 0)).y
        val end = if (line + 1 < editor.document.lineCount) {
            editor.logicalPositionToXY(LogicalPosition(line + 1, 0)).y
        } else {
            start + editor.lineHeight
        }
        return start to end
    }

    companion object {
        /** About one frame at 60 Hz. */
        const val FRAME_MS = 16L
    }
}
