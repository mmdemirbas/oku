package io.github.mmdemirbas.oku

import com.intellij.openapi.fileEditor.FileEditor
import com.intellij.openapi.fileEditor.FileEditorPolicy
import com.intellij.openapi.fileEditor.FileEditorProvider
import com.intellij.openapi.fileEditor.TextEditor
import com.intellij.openapi.fileEditor.TextEditorWithPreview
import com.intellij.openapi.fileEditor.TextEditorWithPreviewProvider
import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile

/**
 * Opens an oku page as text + the kit's own rendering, side by side.
 *
 * Only files that are oku pages are taken, unless the reader chose every
 * markdown file in the settings ([OkuPages.opensInPreview]); every other
 * markdown file keeps the bundled Markdown editor. Taking them all by
 * default would hand a README to a renderer it was not written for. A
 * file the preview cannot draw —
 * no oku, no embedded browser — is not taken either, so it opens in the
 * Markdown editor rather than in a panel that can only say what is wrong
 * ([OkuFallbackNotifier] says it once instead).
 *
 * The platform builds the text half off the UI thread and keeps the split
 * layout the reader picked between sessions; this class only names the
 * pair and hands the preview the editor it follows.
 */
class OkuPreviewEditorProvider : TextEditorWithPreviewProvider(OkuPreviewProvider()) {

    override fun getEditorTypeId(): String = "oku-preview-editor"

    // The bundled Markdown plugin registers its own split editor for every
    // .md; for an oku page that one is the wrong rendering, so it goes.
    override fun getPolicy(): FileEditorPolicy = FileEditorPolicy.HIDE_OTHER_EDITORS

    override fun createSplitEditor(firstEditor: TextEditor, secondEditor: FileEditor): FileEditor {
        (secondEditor as? OkuPreviewFileEditor)?.follow(firstEditor.editor)
        return TextEditorWithPreview(firstEditor, secondEditor, "oku", TextEditorWithPreview.Layout.SHOW_EDITOR_AND_PREVIEW)
    }
}

/** The rendering half. Not registered on its own: it exists as the split's second editor. */
class OkuPreviewProvider : FileEditorProvider, DumbAware {
    override fun accept(project: Project, file: VirtualFile): Boolean =
        OkuPages.opensInPreview(file) && whyPreviewUnavailable() == null

    override fun createEditor(project: Project, file: VirtualFile): FileEditor = OkuPreviewFileEditor(project, file)

    override fun getEditorTypeId(): String = "oku-preview"

    override fun getPolicy(): FileEditorPolicy = FileEditorPolicy.PLACE_AFTER_DEFAULT_EDITOR
}

/**
 * A tree's `index.html` — the shell `oku init` writes — or a page's own stub,
 * drawn the way the runtime fills it ([OkuPages.isShell]): the page beside it,
 * or the tree's front door. It used to open as 470 bytes of markup and a
 * manifest on one line, the one file in the tree a reader opens first.
 *
 * Before the text editor, which stays a tab away: the shell's markup is what
 * `oku init` keeps up to date, not something to read first.
 */
class OkuShellEditorProvider : FileEditorProvider, DumbAware {
    override fun accept(project: Project, file: VirtualFile): Boolean =
        OkuPages.isShell(file) && whyPreviewUnavailable() == null

    override fun createEditor(project: Project, file: VirtualFile): FileEditor = OkuPreviewFileEditor(project, file)

    override fun getEditorTypeId(): String = "oku-shell"

    override fun getPolicy(): FileEditorPolicy = FileEditorPolicy.PLACE_BEFORE_DEFAULT_EDITOR
}
