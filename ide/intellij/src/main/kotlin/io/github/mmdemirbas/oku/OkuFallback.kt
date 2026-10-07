package io.github.mmdemirbas.oku

import com.intellij.notification.NotificationAction
import com.intellij.notification.NotificationGroupManager
import com.intellij.notification.NotificationType
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.fileEditor.FileEditorManagerListener
import com.intellij.openapi.options.ShowSettingsUtil
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.ui.jcef.JBCefApp
import org.jetbrains.annotations.TestOnly
import java.util.concurrent.atomic.AtomicBoolean

/*
 * An oku page the preview cannot draw opens in the Markdown editor, and
 * says why once.
 */

/**
 * The first oku page that opens in the Markdown editor because the preview
 * cannot be drawn says why, once per IDE session: every oku page after it
 * has the same cause, and a balloon per file would be the reader's whole
 * screen.
 */
class OkuFallbackNotifier : FileEditorManagerListener {
    override fun fileOpened(source: FileEditorManager, file: VirtualFile) {
        if (told.get() || !OkuPages.isOkuPage(file)) return
        val why = whyPreviewUnavailable() ?: return
        if (!told.compareAndSet(false, true)) return
        val project = source.project
        NotificationGroupManager.getInstance().getNotificationGroup("oku")
            .createNotification(
                "oku pages open as plain markdown",
                "${file.name} is an oku page, shown in the Markdown editor because $why.",
                NotificationType.WARNING,
            )
            .addAction(
                NotificationAction.createSimpleExpiring("Settings…") {
                    ShowSettingsUtil.getInstance().showSettingsDialog(project, OkuConfigurable::class.java)
                },
            )
            .notify(project)
    }

    companion object {
        private val told = AtomicBoolean(false)

        @TestOnly
        fun forget() = told.set(false)
    }
}

/** Why an oku page cannot be drawn by oku here, or null when it can. */
fun whyPreviewUnavailable(): String? = when (val launch = OkuLauncher.find()) {
    is OkuLaunch.Missing -> launch.reason
    is OkuLaunch.Found -> if (JBCefApp.isSupported()) null else "this IDE runs without JCEF, the browser the preview draws in"
}
