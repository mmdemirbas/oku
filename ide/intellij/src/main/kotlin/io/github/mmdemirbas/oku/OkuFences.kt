package io.github.mmdemirbas.oku

import com.intellij.codeInsight.completion.CompletionParameters
import com.intellij.codeInsight.daemon.DaemonCodeAnalyzer
import com.intellij.codeInsight.lookup.LookupElement
import com.intellij.codeInsight.lookup.LookupElementBuilder
import com.intellij.json.JsonLanguage
import com.intellij.lang.Language
import com.intellij.lang.injection.InjectedLanguageManager
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.service
import com.intellij.openapi.project.ProjectManager
import com.intellij.json.JsonFileType
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.testFramework.LightVirtualFile
import com.intellij.psi.PsiFile
import com.jetbrains.jsonSchema.extension.ContentAwareJsonSchemaFileProvider
import com.jetbrains.jsonSchema.ide.JsonSchemaService
import org.intellij.plugins.markdown.injection.CodeFenceLanguageProvider
import org.intellij.plugins.markdown.lang.psi.impl.MarkdownCodeFence
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.FileTime
import java.util.concurrent.ConcurrentHashMap

/*
 * An oku-* fence body is one JSON object, and oku names the schema of each
 * one (the greeting's `fences`, generated from the page schema). Three
 * pieces put that in front of an author: the fence is JSON, its schema is
 * the one oku named, and when oku names them the open editors are checked
 * again — the first greeting usually arrives after the page has been
 * highlighted once.
 */

/** The tag of a fence, as its info string starts: ```oku-chart → `oku-chart`. */
private fun fenceTag(info: String?): String? = info?.trim()?.substringBefore(' ')?.takeIf { it.isNotEmpty() }

/**
 * An oku-* fence is JSON. Before a session has said which fences exist, the
 * prefix decides: every oku-* fence body is a JSON object by the format's
 * own rule, and highlighting a fence as JSON a moment early costs nothing.
 */
class OkuFenceLanguageProvider : CodeFenceLanguageProvider {
    override fun getLanguageByInfoString(infoString: String): Language? {
        val tag = fenceTag(infoString) ?: return null
        val known = service<OkuPreviewService>().fences
        val oku = if (known.isEmpty()) tag.startsWith("oku-") else tag in known
        return if (oku) JsonLanguage.INSTANCE else null
    }

    /** The fence tags, offered after ``` — only in a file that is an oku page. */
    override fun getCompletionVariantsForInfoString(parameters: CompletionParameters): List<LookupElement> {
        val file = parameters.originalFile.viewProvider.virtualFile
        if (!OkuPages.isOkuPage(file)) return emptyList()
        return service<OkuPreviewService>().fences.keys.sorted().map {
            LookupElementBuilder.create(it).withTypeText("oku")
        }
    }
}

/**
 * The schema oku named for the fence a JSON fragment sits in.
 *
 * Held in memory rather than found in the VFS: oku writes the files when a
 * session starts, which is usually inside highlighting (the first check
 * starts one), and bringing a new file into the VFS there is a model change
 * the daemon has to restart for. One object per file and mtime, because
 * the JSON support keeps a parsed schema per VirtualFile.
 */
class OkuFenceSchemaProvider : ContentAwareJsonSchemaFileProvider {
    private val held = ConcurrentHashMap<Path, Pair<FileTime, VirtualFile>>()

    override fun getSchemaFile(psiFile: PsiFile): VirtualFile? {
        val host = InjectedLanguageManager.getInstance(psiFile.project).getInjectionHost(psiFile) as? MarkdownCodeFence
            ?: return null
        val path = service<OkuPreviewService>().fences[fenceTag(host.fenceLanguage)] ?: return null
        return schema(path)
    }

    private fun schema(path: Path): VirtualFile? {
        val stamp = runCatching { Files.getLastModifiedTime(path) }.getOrNull() ?: return null
        held[path]?.let { (at, file) -> if (at == stamp) return file }
        val text = runCatching { Files.readString(path) }.getOrNull() ?: return null
        val file = LightVirtualFile(path.fileName.toString(), JsonFileType.INSTANCE, text)
        held[path] = stamp to file
        return file
    }
}

/** oku named the fence schemas: let every open project's JSON support read them. */
class OkuFenceSchemaReset : OkuGreetingListener {
    override fun greeted(greeting: Greeting) {
        ApplicationManager.getApplication().invokeLater {
            for (project in ProjectManager.getInstance().openProjects) {
                if (project.isDisposed) continue
                JsonSchemaService.Impl.get(project).reset()
                DaemonCodeAnalyzer.getInstance(project).restart()
            }
        }
    }
}
