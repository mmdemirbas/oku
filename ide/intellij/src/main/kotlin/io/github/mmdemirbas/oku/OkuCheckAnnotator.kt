package io.github.mmdemirbas.oku

import com.intellij.lang.annotation.AnnotationHolder
import com.intellij.lang.annotation.ExternalAnnotator
import com.intellij.lang.annotation.HighlightSeverity
import com.intellij.openapi.components.service
import com.intellij.openapi.diagnostic.logger
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.util.TextRange
import com.intellij.psi.PsiFile
import java.nio.file.Path
import kotlin.io.path.Path

/**
 * `oku check`'s findings for an oku page, on the lines they are about, while
 * the page is being typed. The unsaved buffer is checked inside its tree by
 * the service's check session — a link's anchor lives on another page — so
 * what shows here is what `oku check` reports once the file is saved.
 *
 * Errors and warnings only. `oku check` prints an info note as one summary
 * line and the note itself only under --verbose; drawn on every line it is
 * about (an HTML island, every one), it would be a squiggle authors learn
 * to look past, and then they look past the warnings too.
 *
 * A check that did not run says so at the top of the file: an empty margin
 * is how a clean page looks, so silence would tell the author the page is
 * fine. Except when there is no oku at all — the page then opens in the
 * Markdown editor and [OkuFallbackNotifier] has said why.
 *
 * A finding `oku check --fix` answers carries that fix ([OkuChipFix]).
 */
class OkuCheckAnnotator : ExternalAnnotator<OkuCheckAnnotator.Input, OkuCheckAnnotator.Outcome>() {

    class Input(val path: Path, val text: String)

    /** What the check found, or why it could not look. */
    class Outcome(val issues: List<Issue>, val failure: String?)

    private val log = logger<OkuCheckAnnotator>()

    @Volatile
    private var lastFailure: String? = null

    override fun collectInformation(file: PsiFile, editor: Editor, hasErrors: Boolean): Input? = collectInformation(file)

    override fun collectInformation(file: PsiFile): Input? {
        val virtual = file.viewProvider.virtualFile
        if (!virtual.isInLocalFileSystem || !OkuPages.isOkuPage(virtual)) return null
        val text = file.viewProvider.document?.text ?: return null
        return Input(Path(virtual.path), text)
    }

    override fun doAnnotate(input: Input): Outcome? {
        if (OkuLauncher.find() is OkuLaunch.Missing) return null
        return service<OkuPreviewService>().check(input.path, input.text).fold(
            onSuccess = { Outcome(it, failure = null) },
            onFailure = {
                // Logged once per distinct cause: this runs on every pause in typing.
                val said = it.message ?: it.toString()
                if (said != lastFailure) log.warn("oku check failed for ${input.path}: $said")
                lastFailure = said
                Outcome(emptyList(), failure = said)
            },
        )
    }

    override fun apply(file: PsiFile, outcome: Outcome, holder: AnnotationHolder) {
        val document = file.viewProvider.document ?: return
        outcome.failure?.let {
            holder.newAnnotation(HighlightSeverity.WARNING, "oku check did not run: ${it.lineSequence().first()}")
                .fileLevel()
                .create()
        }
        for (issue in outcome.issues) {
            val severity = when (issue.severity) {
                "error" -> HighlightSeverity.ERROR
                "warning" -> HighlightSeverity.WARNING
                else -> continue
            }
            val builder = holder.newAnnotation(severity, "${issue.message} [oku ${issue.code}]")
            if (issue.code == "path-in-code-span") builder.withFix(OkuChipFix)
            val line = issue.line
            if (line != null && line in 1..document.lineCount) {
                val range = lineText(document, line - 1)
                builder.range(range)
                if (range.isEmpty) builder.afterEndOfLine()
            } else {
                builder.fileLevel()
            }
            builder.create()
        }
    }

    /** The line's text without its indentation, so the mark sits under what is written. */
    private fun lineText(document: Document, line: Int): TextRange {
        val start = document.getLineStartOffset(line)
        val end = document.getLineEndOffset(line)
        val chars = document.charsSequence
        var from = start
        while (from < end && chars[from].isWhitespace()) from++
        return TextRange(from, end)
    }
}
