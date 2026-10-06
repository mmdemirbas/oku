package io.github.mmdemirbas.oku

import com.intellij.openapi.fileEditor.FileEditor
import com.intellij.openapi.fileEditor.FileEditorPolicy
import com.intellij.openapi.fileEditor.FileEditorProvider
import com.intellij.openapi.fileEditor.TextEditor
import com.intellij.openapi.fileEditor.TextEditorWithPreview
import com.intellij.openapi.fileEditor.impl.text.TextEditorProvider
import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.ui.jcef.JBCefApp

/**
 * Opens an oku page as text + the kit's own rendering, side by side.
 *
 * Only files that are oku pages are taken; every other markdown file keeps
 * the bundled Markdown editor. Taking them all would hand a README to a
 * renderer it was not written for.
 */
class OkuPreviewEditorProvider : FileEditorProvider, DumbAware {

    override fun accept(project: Project, file: VirtualFile): Boolean =
        JBCefApp.isSupported() && OkuPages.isOkuPage(file)

    override fun createEditor(project: Project, file: VirtualFile): FileEditor {
        val text = TextEditorProvider.getInstance().createEditor(project, file) as TextEditor
        val preview = OkuPreviewFileEditor(project, file)
        return TextEditorWithPreview(text, preview, "oku", TextEditorWithPreview.Layout.SHOW_EDITOR_AND_PREVIEW)
    }

    override fun getEditorTypeId(): String = "oku-preview-editor"

    // The bundled Markdown plugin registers its own split editor for every
    // .md; for an oku page that one is the wrong rendering, so it goes.
    override fun getPolicy(): FileEditorPolicy = FileEditorPolicy.HIDE_OTHER_EDITORS
}
