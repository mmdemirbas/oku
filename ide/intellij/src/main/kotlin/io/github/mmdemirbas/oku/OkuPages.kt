package io.github.mmdemirbas.oku

import com.intellij.openapi.vfs.VirtualFile

/** Which markdown files are oku pages. */
object OkuPages {

    private const val MAX_SNIFF_BYTES = 2 * 1024 * 1024

    /**
     * A tree that declares itself (a kit.json, or the `_oku` link `oku init`
     * leaves beside the pages) or a file that uses a typed fence. Front-matter
     * alone is not a signal — Jekyll and Hugo pages carry it too. With the
     * plugin switched off in the settings, nothing is.
     */
    fun isOkuPage(file: VirtualFile): Boolean {
        if (!OkuSettings.get().state.enabled) return false
        if (file.isDirectory || !file.name.endsWith(".md", ignoreCase = true)) return false
        if (inDeclaredTree(file)) return true
        if (file.length > MAX_SNIFF_BYTES) return false
        val text = runCatching { String(file.contentsToByteArray(), Charsets.UTF_8) }.getOrNull() ?: return false
        return text.contains("```oku-")
    }

    private fun inDeclaredTree(file: VirtualFile): Boolean {
        var dir = file.parent
        while (dir != null) {
            if (dir.findChild("kit.json") != null || dir.findChild("_oku") != null) return true
            if (dir.findChild(".git") != null) return false
            dir = dir.parent
        }
        return false
    }
}
