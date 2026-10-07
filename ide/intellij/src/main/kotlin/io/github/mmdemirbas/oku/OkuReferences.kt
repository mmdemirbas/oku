package io.github.mmdemirbas.oku

import com.intellij.codeInsight.daemon.DaemonCodeAnalyzer
import com.intellij.codeInspection.InspectionSuppressor
import com.intellij.codeInspection.SuppressQuickFix
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.service
import com.intellij.openapi.project.ProjectManager
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.patterns.PlatformPatterns
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiFileSystemItem
import com.intellij.psi.PsiManager
import com.intellij.psi.PsiReference
import com.intellij.psi.PsiReferenceContributor
import com.intellij.psi.PsiReferenceProvider
import com.intellij.psi.PsiReferenceRegistrar
import com.intellij.psi.impl.source.resolve.reference.impl.providers.FileReferenceSet
import com.intellij.psi.util.PsiTreeUtil
import com.intellij.util.ProcessingContext
import org.intellij.plugins.markdown.lang.psi.impl.MarkdownLinkDestination

/*
 * oku links that are not heading anchors: `#f/` names a file, `#g/` a
 * glossary term, `#x/` an external reference (the greeting's `inline`,
 * oku's _INLINE_KINDS). The Markdown plugin reads every `#…` destination as
 * a heading id, so without this each of them is a link it cannot follow and
 * a warning that it cannot find the heading.
 */

/** The link destination [element] is, or sits in, when it is on an oku page. */
private fun okuDestination(element: PsiElement): MarkdownLinkDestination? {
    val destination = element as? MarkdownLinkDestination
        ?: PsiTreeUtil.getParentOfType(element, MarkdownLinkDestination::class.java)
        ?: return null
    val file = destination.containingFile?.originalFile?.viewProvider?.virtualFile ?: return null
    return destination.takeIf { file.isInLocalFileSystem && OkuPages.isOkuPage(file) }
}

/**
 * `#f/src/x.py` is a file reference: the IDE follows it, completes it
 * segment by segment, and says when it names nothing. Resolved the way oku
 * resolves it ([OkuFileRefs]).
 */
class OkuFileReferenceContributor : PsiReferenceContributor() {
    override fun registerReferenceProviders(registrar: PsiReferenceRegistrar) {
        registrar.registerReferenceProvider(
            PlatformPatterns.psiElement(MarkdownLinkDestination::class.java),
            object : PsiReferenceProvider() {
                override fun getReferencesByElement(element: PsiElement, context: ProcessingContext): Array<PsiReference> {
                    val prefix = service<OkuPreviewService>().greeting.inline["filepath"] ?: return PsiReference.EMPTY_ARRAY
                    val text = element.text
                    if (!text.startsWith(prefix) || okuDestination(element) == null) return PsiReference.EMPTY_ARRAY
                    val page = element.containingFile.originalFile.viewProvider.virtualFile
                    val bases = OkuFileRefs.bases(page)
                    val path = OkuFileRefs.pathOf(text.substring(prefix.length), bases)
                    val set = object : FileReferenceSet(path, element, prefix.length, this, true) {
                        override fun computeDefaultContexts(): Collection<PsiFileSystemItem> =
                            bases.mapNotNull { PsiManager.getInstance(element.project).findDirectory(it) }

                        override fun isAbsolutePathReference(): Boolean = false
                    }
                    @Suppress("UNCHECKED_CAST")
                    return set.allReferences as Array<PsiReference>
                }
            },
        )
    }
}

/**
 * How oku resolves a `#f/` path, mirrored: the page's own directory first,
 * then the project root (nearest `.git`, else nearest `kit.json`; oku's
 * project_root_for), and a `:line` or `:line-end` suffix read only when the
 * whole string is not itself a file (oku's _LINE_SUFFIX_RE, Zed's rule).
 */
object OkuFileRefs {
    private val lineSuffix = Regex("""^(.*[^\s:]):(\d+)(?:-(\d+))?$""")

    fun bases(page: VirtualFile): List<VirtualFile> {
        val dir = page.parent ?: return emptyList()
        val root = ancestorWith(dir, ".git") ?: ancestorWith(dir, "kit.json") ?: dir
        return listOf(dir, root).distinct()
    }

    fun pathOf(text: String, bases: List<VirtualFile>): String {
        if (bases.any { it.findFileByRelativePath(text) != null }) return text
        val base = lineSuffix.matchEntire(text)?.groupValues?.get(1) ?: return text
        return if (bases.any { it.findFileByRelativePath(base) != null }) base else text
    }

    private fun ancestorWith(start: VirtualFile, name: String): VirtualFile? {
        var dir: VirtualFile? = start
        while (dir != null) {
            if (dir.findChild(name) != null) return dir
            dir = dir.parent
        }
        return null
    }
}

/** An oku link is not a heading anchor, so the Markdown plugin's "cannot resolve anchor" is not about it. */
class OkuInlineLinkSuppressor : InspectionSuppressor {
    override fun isSuppressedFor(element: PsiElement, toolId: String): Boolean {
        if (toolId != HEADER_REFERENCE) return false
        val destination = okuDestination(element) ?: return false
        return service<OkuPreviewService>().greeting.inline.values.any { destination.text.startsWith(it) }
    }

    override fun getSuppressActions(element: PsiElement?, toolId: String): Array<SuppressQuickFix> = SuppressQuickFix.EMPTY_ARRAY

    private companion object {
        const val HEADER_REFERENCE = "MarkdownUnresolvedHeaderReference"
    }
}

/** A greeting changes what the references and the suppressor answer: check open files again. */
class OkuGreetingRestart : OkuGreetingListener {
    override fun greeted(greeting: Greeting) {
        ApplicationManager.getApplication().invokeLater {
            for (project in ProjectManager.getInstance().openProjects) {
                if (!project.isDisposed) DaemonCodeAnalyzer.getInstance(project).restart()
            }
        }
    }
}
