package io.github.mmdemirbas.oku

import com.intellij.codeInsight.AutoPopupController
import com.intellij.codeInsight.completion.CompletionContributor
import com.intellij.codeInsight.completion.CompletionParameters
import com.intellij.codeInsight.completion.CompletionProvider
import com.intellij.codeInsight.completion.CompletionResultSet
import com.intellij.codeInsight.completion.CompletionType
import com.intellij.codeInsight.completion.InsertHandler
import com.intellij.codeInsight.completion.InsertionContext
import com.intellij.codeInsight.editorActions.TypedHandlerDelegate
import com.intellij.codeInsight.lookup.LookupElement
import com.intellij.codeInsight.lookup.LookupElementBuilder
import com.intellij.openapi.components.service
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.patterns.PlatformPatterns
import com.intellij.psi.PsiFile
import com.intellij.util.ProcessingContext

/*
 * What an author types by hand on an oku page, offered as it is typed: the
 * type of a `> [!TYPE]` alert, and the list behind `#g/`, `#x/` and `#f/`
 * the moment the slash is typed.
 */

/** The text of [offset]'s line before it. */
internal fun lineBefore(document: Document, offset: Int): String =
    document.charsSequence.subSequence(document.getLineStartOffset(document.getLineNumber(offset)), offset).toString()

private fun isLocalOkuPage(file: VirtualFile?): Boolean = file != null && file.isInLocalFileSystem && OkuPages.isOkuPage(file)

/**
 * `> [!` completes the alert types the kit draws (the greeting's
 * `admonitions`, held against the renderer's `ADM_CLASS` in oku), each
 * with what it is for. Typed in any case and written in capitals, as the
 * kit's own pages write them; the `]` is added when nothing closes it.
 */
class OkuAlertCompletion : CompletionContributor() {
    init {
        extend(CompletionType.BASIC, PlatformPatterns.psiElement(), object : CompletionProvider<CompletionParameters>() {
            override fun addCompletions(parameters: CompletionParameters, context: ProcessingContext, result: CompletionResultSet) {
                if (!isLocalOkuPage(parameters.originalFile.viewProvider.virtualFile)) return
                val typed = ALERT.matchEntire(lineBefore(parameters.editor.document, parameters.offset))?.groupValues?.get(1) ?: return
                val types = service<OkuPreviewService>().greeting.admonitions
                if (types.isEmpty()) return
                val matching = result.withPrefixMatcher(typed)
                for ((type, what) in types) {
                    matching.addElement(
                        LookupElementBuilder.create(type)
                            .withCaseSensitivity(false)
                            .withBoldness(true)
                            .withTailText("  $what", true)
                            .withInsertHandler(CloseAlert),
                    )
                }
                // Not prose, so no other contributor has anything to add.
                result.stopHere()
            }
        })
    }

    private object CloseAlert : InsertHandler<LookupElement> {
        override fun handleInsert(context: InsertionContext, item: LookupElement) {
            val document = context.document
            // In capitals however it was typed: the lookup writes a name
            // matched without case in the case the author typed.
            document.replaceString(context.startOffset, context.tailOffset, item.lookupString)
            val at = context.startOffset + item.lookupString.length
            if (at >= document.textLength || document.charsSequence[at] != ']') document.insertString(at, "]")
            context.editor.caretModel.moveToOffset(at + 1)
        }
    }

    internal companion object {
        /** A blockquote line up to the caret, inside `[!`, and the letters typed after it. */
        val ALERT = Regex("""^\s*>\s?\[!([A-Za-z]*)$""")
    }
}

/**
 * Opens the completion list when the character just typed is where a list
 * starts: the `!` of `> [!`, and the `/` of `(#g/`, `(#x/` and `(#f/`.
 * The platform opens it on letters only, so without this a list that
 * exists is one the author has to know to ask for. The Markdown plugin does
 * the same for `#` in a link.
 *
 * Registered first: in a link destination a handler ahead of it ended the
 * chain, and typing `/` in `(#g` opened nothing.
 */
class OkuAutoPopup : TypedHandlerDelegate() {
    override fun checkAutoPopup(charTyped: Char, project: Project, editor: Editor, file: PsiFile): Result {
        if (charTyped != '!' && charTyped != '/') return Result.CONTINUE
        if (!isLocalOkuPage(file.viewProvider.virtualFile)) return Result.CONTINUE
        val before = lineBefore(editor.document, editor.caretModel.offset)
        val opens = when (charTyped) {
            '!' -> ALERT_BRACKET.matches(before)
            else -> service<OkuPreviewService>().greeting.inline.values.any { before.endsWith("(" + it.removeSuffix("/")) }
        }
        if (!opens) return Result.CONTINUE
        AutoPopupController.getInstance(project).scheduleAutoPopup(editor)
        return Result.STOP
    }

    private companion object {
        val ALERT_BRACKET = Regex("""^\s*>\s?\[$""")
    }
}
