package io.github.mmdemirbas.oku

import com.intellij.openapi.vfs.VirtualFile

/** Which markdown files are oku pages, which open in oku's preview, and which `.html` files are a page's shell. */
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

    /**
     * Opens in oku's preview: every oku page, and with "every markdown file"
     * chosen in the settings, any `.md` (oku previews no other suffix). Only
     * the preview widens: a file that is not an oku page is not checked, and
     * its fences and links stay the Markdown plugin's, because `oku check`
     * on a README reports rules the README was never written to.
     */
    fun opensInPreview(file: VirtualFile): Boolean {
        val options = OkuSettings.get().state
        if (!options.enabled) return false
        if (isOkuPage(file)) return true
        return options.everyMarkdown && !file.isDirectory && file.name.endsWith(".md", ignoreCase = true)
    }

    /**
     * The `.html` a tree is entered by: the `index.html` `oku init` writes, or
     * a page's own stub. It loads the kit and holds nothing; the runtime fills
     * it from the `.md` beside it ([pageOf]), and an `index.html` with none is
     * the tree's front door, drawn from the manifest. A page that uses the kit
     * for its chrome has a body of its own and is not one, and neither is a
     * stub with no page to show.
     */
    fun isShell(file: VirtualFile): Boolean {
        if (!OkuSettings.get().state.enabled) return false
        if (file.isDirectory || !file.name.endsWith(".html", ignoreCase = true)) return false
        if (pageOf(file) == null && file.name != "index.html") return false
        if (file.length > MAX_SNIFF_BYTES || !inDeclaredTree(file)) return false
        val text = runCatching { String(file.contentsToByteArray(), Charsets.UTF_8) }.getOrNull() ?: return false
        return "_oku/renderer.js" in text && EMPTY_BODY.containsMatchIn(text)
    }

    /** The page a shell shows: the `.md` beside it, as oku names it (`index.tr.html` → `index.tr.md`). */
    fun pageOf(shell: VirtualFile): VirtualFile? = shell.parent?.findChild(shell.nameWithoutExtension + ".md")

    private val EMPTY_BODY = Regex("<body[^>]*>\\s*</body>", RegexOption.IGNORE_CASE)

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
