package io.github.mmdemirbas.oku

import com.intellij.codeInsight.hint.HintManager
import com.intellij.codeInsight.intention.IntentionAction
import com.intellij.codeInsight.intention.preview.IntentionPreviewInfo
import com.intellij.diff.comparison.ComparisonManager
import com.intellij.diff.comparison.ComparisonPolicy
import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.components.service
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.progress.DumbProgressIndicator
import com.intellij.openapi.progress.ProcessCanceledException
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.util.ProgressIndicatorUtils
import com.intellij.openapi.project.Project
import com.intellij.psi.PsiFile
import java.nio.file.Path
import kotlin.io.path.Path

/**
 * `oku check --fix` on the unsaved page: every code span naming a file the
 * check reports becomes a file chip. oku does the rewriting (the service's
 * `fix`, the same rule `--fix` applies to a saved file), so the editor and
 * the command line cannot disagree about which spans qualify.
 *
 * The page as a whole, as `--fix` does it, and written as the changes it
 * makes rather than as a new text: the caret, folds and markers outside the
 * rewritten spans stay where they were. Asked of oku under a progress
 * indicator rather than in a write action, because it is a round trip.
 */
object OkuChipFix : IntentionAction {
    override fun getText(): String = "Turn the paths in code spans into file chips (oku check --fix)"

    override fun getFamilyName(): String = "oku check --fix"

    override fun isAvailable(project: Project, editor: Editor?, file: PsiFile?): Boolean {
        val page = file?.viewProvider?.virtualFile ?: return false
        return page.isInLocalFileSystem && OkuPages.isOkuPage(page)
    }

    override fun startInWriteAction(): Boolean = false

    // A round trip to oku is not something to run on every preview.
    override fun generatePreview(project: Project, editor: Editor, file: PsiFile): IntentionPreviewInfo = IntentionPreviewInfo.EMPTY

    override fun invoke(project: Project, editor: Editor?, file: PsiFile?) {
        val document = editor?.document ?: return
        val page = file?.viewProvider?.virtualFile ?: return
        val before = document.text
        val fixed = try {
            ProgressManager.getInstance().runProcessWithProgressSynchronously<Result<Fixed>, RuntimeException>(
                { ask(Path(page.path), before) },
                "oku check --fix",
                true,
                project,
            )
        } catch (_: ProcessCanceledException) {
            return // cancelled: the page stays as it was
        }
        val after = fixed.getOrElse {
            HintManager.getInstance().showErrorHint(editor, "oku check --fix did not run: ${it.message?.lineSequence()?.first()}")
            return
        }.text
        if (after == before || document.text != before) return
        WriteCommandAction.runWriteCommandAction(project, text, null, { applyChanges(document, before, after) }, file)
    }

    /** The fix for [text], asked of oku off the calling thread so a cancelled progress stops the wait; oku finishes the fix unread. */
    internal fun ask(page: Path, text: String): Result<Fixed> {
        val asked = ApplicationManager.getApplication().executeOnPooledThread<Result<Fixed>> { service<OkuPreviewService>().fix(page, text) }
        return ProgressIndicatorUtils.awaitWithCheckCanceled(asked)
    }

    /** [after] written into [document] (holding [before]) as the fragments that differ, last first. */
    internal fun applyChanges(document: Document, before: String, after: String) {
        val fragments = ComparisonManager.getInstance().compareChars(before, after, ComparisonPolicy.DEFAULT, DumbProgressIndicator.INSTANCE)
        for (f in fragments.asReversed()) {
            document.replaceString(f.startOffset1, f.endOffset1, after.substring(f.startOffset2, f.endOffset2))
        }
    }
}
