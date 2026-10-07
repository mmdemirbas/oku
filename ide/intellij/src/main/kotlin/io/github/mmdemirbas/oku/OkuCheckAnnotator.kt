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
 */
class OkuCheckAnnotator : ExternalAnnotator<OkuCheckAnnotator.Input, List<Issue>>() {

    class Input(val path: Path, val text: String)

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

    override fun doAnnotate(input: Input): List<Issue>? =
        service<OkuPreviewService>().check(input.path, input.text).getOrElse {
            // Once per distinct cause: this runs on every pause in typing.
            val said = it.message ?: it.toString()
            if (said != lastFailure) log.warn("oku check failed for ${input.path}: $said")
            lastFailure = said
            null
        }

    override fun apply(file: PsiFile, issues: List<Issue>, holder: AnnotationHolder) {
        val document = file.viewProvider.document ?: return
        for (issue in issues) {
            val severity = when (issue.severity) {
                "error" -> HighlightSeverity.ERROR
                "warning" -> HighlightSeverity.WARNING
                else -> continue
            }
            val builder = holder.newAnnotation(severity, "${issue.message} [oku ${issue.code}]")
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
