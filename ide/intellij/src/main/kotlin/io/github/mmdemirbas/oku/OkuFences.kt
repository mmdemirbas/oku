package io.github.mmdemirbas.oku

import com.intellij.codeInsight.completion.CompletionParameters
import com.intellij.codeInsight.completion.InsertHandler
import com.intellij.codeInsight.completion.InsertionContext
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
import com.intellij.injected.editor.VirtualFileWindow
import com.intellij.openapi.project.Project
import com.intellij.psi.PsiManager
import com.jetbrains.jsonSchema.extension.ContentAwareJsonSchemaFileProvider
import com.jetbrains.jsonSchema.extension.JsonSchemaFileProvider
import com.jetbrains.jsonSchema.extension.JsonSchemaProviderFactory
import com.jetbrains.jsonSchema.extension.SchemaType
import com.jetbrains.jsonSchema.ide.JsonSchemaService
import org.intellij.plugins.markdown.injection.CodeFenceLanguageProvider
import org.intellij.plugins.markdown.lang.psi.impl.MarkdownCodeFence
import org.intellij.plugins.markdown.lang.psi.impl.MarkdownFrontMatterHeader
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
internal fun fenceTag(info: String?): String? = info?.trim()?.substringBefore(' ')?.takeIf { it.isNotEmpty() }

/**
 * An oku-* fence is JSON. Before a session has said which fences exist, the
 * prefix decides: every oku-* fence body is a JSON object by the format's
 * own rule, and highlighting a fence as JSON a moment early costs nothing.
 */
class OkuFenceLanguageProvider : CodeFenceLanguageProvider {
    override fun getLanguageByInfoString(infoString: String): Language? {
        if (!OkuSettings.get().state.enabled) return null
        val tag = fenceTag(infoString) ?: return null
        val known = service<OkuPreviewService>().fences
        val oku = if (known.isEmpty()) tag.startsWith("oku-") else tag in known
        return if (oku) JsonLanguage.INSTANCE else null
    }

    /**
     * Every component, offered after ``` — only in a file that is an oku page:
     * each fence kind, and each chart type as `oku-chart sankey`, so typing
     * `sank` finds it. Picking one writes oku's own example as the body
     * ([OkuSnippetInsert]). Before a session has named them, the tags alone.
     */
    override fun getCompletionVariantsForInfoString(parameters: CompletionParameters): List<LookupElement> {
        val file = parameters.originalFile.viewProvider.virtualFile
        if (!OkuPages.isOkuPage(file)) return emptyList()
        val greeting = service<OkuPreviewService>().greeting
        if (greeting.snippets.isEmpty()) {
            return greeting.fences.keys.sorted().map { LookupElementBuilder.create(it).withTypeText("oku") }
        }
        return greeting.snippets.map { snippet ->
            LookupElementBuilder.create(snippet, snippet.type?.let { "${snippet.tag} $it" } ?: snippet.tag)
                .withPresentableText(snippet.tag)
                .withTailText(snippet.type?.let { " $it" }, true)
                .withTypeText("oku")
                .withInsertHandler(OkuSnippetInsert)
        }
    }
}

/**
 * Puts a picked component in: the tag on the fence line, and oku's example
 * as the body when the fence has none yet — the next line closes it, or
 * nothing but a blank line follows, in which case the fence is closed too.
 * A fence that already has a body only gets its tag: what the author wrote
 * there is theirs. The caret lands on the body's first key.
 */
object OkuSnippetInsert : InsertHandler<LookupElement> {
    private val OPENER = Regex("^ {0,3}(`{3,}|~{3,})")

    override fun handleInsert(context: InsertionContext, item: LookupElement) {
        val snippet = item.`object` as? Snippet ?: return
        val document = context.document
        document.replaceString(context.startOffset, context.tailOffset, snippet.tag)
        val text = document.charsSequence
        val line = document.getLineNumber(context.startOffset)
        val lineEnd = document.getLineEndOffset(line)
        val opener = OPENER.find(text.subSequence(document.getLineStartOffset(line), lineEnd))?.groupValues?.get(1) ?: return
        val next = if (line + 1 < document.lineCount) {
            text.subSequence(document.getLineStartOffset(line + 1), document.getLineEndOffset(line + 1)).toString()
        } else {
            null
        }
        val closes = next != null && next.trim().let { it.length >= opener.length && it.all { c -> c == opener[0] } }
        when {
            closes -> document.insertString(lineEnd, "\n" + snippet.body)
            next == null || next.isBlank() -> document.insertString(lineEnd, "\n" + snippet.body + "\n" + opener)
            else -> return
        }
        val firstKey = snippet.body.indexOf('"').coerceAtLeast(0)
        context.editor.caretModel.moveToOffset(lineEnd + 1 + firstKey)
        context.commitDocument()
    }
}

/**
 * The schema oku named for the fence a JSON fragment sits in.
 *
 * A content-aware provider is the JSON support's last resort — asked only
 * when no registered provider takes the file — which is right for a fence
 * body, which nothing else claims.
 */
class OkuFenceSchemaProvider : ContentAwareJsonSchemaFileProvider {
    override fun getSchemaFile(psiFile: PsiFile): VirtualFile? {
        val host = InjectedLanguageManager.getInstance(psiFile.project).getInjectionHost(psiFile) as? MarkdownCodeFence
            ?: return null
        return service<OkuPreviewService>().fences[fenceTag(host.fenceLanguage)]?.let(OkuSchemaFiles::of)
    }
}

/**
 * The schema of an oku page's front matter (the greeting's `front_matter`):
 * `title`, `summary`, `order`, `parent`, `accent`… complete and describe
 * themselves. Only on an oku page — every markdown file has front matter,
 * and the Markdown plugin's schema (Jekyll's keys) stays for the rest.
 *
 * A registered provider, placed first, and not a content-aware one: the
 * JSON support asks a content-aware provider only when no registered one
 * takes the file, and the Markdown plugin's takes every front matter. Among
 * registered providers that are not user schemas the first one wins.
 */
class OkuFrontMatterSchemaFactory : JsonSchemaProviderFactory {
    override fun getProviders(project: Project): List<JsonSchemaFileProvider> = listOf(Provider(project))

    private class Provider(private val project: Project) : JsonSchemaFileProvider {
        override fun isAvailable(file: VirtualFile): Boolean {
            if (file !is VirtualFileWindow || service<OkuPreviewService>().greeting.frontMatter == null) return false
            val page = file.delegate
            if (!page.isInLocalFileSystem || !OkuPages.isOkuPage(page)) return false
            val fragment = PsiManager.getInstance(project).findFile(file) ?: return false
            return InjectedLanguageManager.getInstance(project).getInjectionHost(fragment) is MarkdownFrontMatterHeader
        }

        override fun getName(): String = "oku page front matter"

        override fun getSchemaFile(): VirtualFile? = service<OkuPreviewService>().greeting.frontMatter?.let(OkuSchemaFiles::of)

        override fun getSchemaType(): SchemaType = SchemaType.embeddedSchema
    }
}

/**
 * The schema files oku writes, held in memory rather than found in the VFS:
 * oku writes them when a session starts, which is usually inside
 * highlighting (the first check starts one), and bringing a new file into
 * the VFS there is a model change the daemon has to restart for. One object
 * per file and mtime, because the JSON support keeps a parsed schema per
 * VirtualFile.
 */
private object OkuSchemaFiles {
    private val held = ConcurrentHashMap<Path, Pair<FileTime, VirtualFile>>()

    fun of(path: Path): VirtualFile? {
        val stamp = runCatching { Files.getLastModifiedTime(path) }.getOrNull() ?: return null
        held[path]?.let { (at, file) -> if (at == stamp) return file }
        val text = runCatching { Files.readString(path) }.getOrNull() ?: return null
        val file = LightVirtualFile(path.fileName.toString(), JsonFileType.INSTANCE, text)
        held[path] = stamp to file
        return file
    }
}

/** oku named its schemas: let every open project's JSON support read them. */
class OkuFenceSchemaReset : OkuGreetingListener {
    override fun greeted(greeting: Greeting) {
        ApplicationManager.getApplication().invokeLater {
            for (project in ProjectManager.getInstance().openProjects) {
                if (project.isDisposed) continue
                JsonSchemaService.Impl.get(project).reset()
                DaemonCodeAnalyzer.getInstance(project).restart("oku named its schemas")
            }
        }
    }
}
