package io.github.mmdemirbas.oku

import com.intellij.codeInsight.completion.CompletionContributor
import com.intellij.codeInsight.completion.CompletionParameters
import com.intellij.codeInsight.completion.CompletionProvider
import com.intellij.codeInsight.completion.CompletionResultSet
import com.intellij.codeInsight.completion.CompletionType
import com.intellij.codeInsight.lookup.LookupElementBuilder
import com.intellij.lang.injection.InjectedLanguageManager
import com.intellij.patterns.PlatformPatterns
import com.intellij.util.ProcessingContext
import org.intellij.plugins.markdown.lang.psi.impl.MarkdownFrontMatterHeader
import kotlin.io.path.Path

/**
 * `parent:` in an oku page's front matter completes from the pages of its
 * tree — the value the manifest groups a page under, its source path from
 * the tree's root without `.md` — each with its title, which also finds it.
 * The keys and the other values come from oku's front-matter schema
 * ([OkuFrontMatterSchemaFactory]); a page list is per tree, which a schema written
 * once per session cannot carry.
 *
 * The page itself is not offered: a page that is its own parent is a loop.
 * Its id is the longest one its own path ends with, since every other id
 * that is a suffix of it names a page nearer the root.
 */
class OkuParentCompletion : CompletionContributor() {
    init {
        extend(CompletionType.BASIC, PlatformPatterns.psiElement(), object : CompletionProvider<CompletionParameters>() {
            override fun addCompletions(parameters: CompletionParameters, context: ProcessingContext, result: CompletionResultSet) {
                val fragment = parameters.originalFile
                val host = InjectedLanguageManager.getInstance(fragment.project).getInjectionHost(fragment)
                    as? MarkdownFrontMatterHeader ?: return
                val page = host.containingFile.originalFile.viewProvider.virtualFile
                if (!page.isInLocalFileSystem || !OkuPages.isOkuPage(page)) return
                val text = parameters.position.containingFile.text
                val before = text.substring(text.lastIndexOf('\n', parameters.offset - 1) + 1, parameters.offset)
                val typed = PARENT.matchEntire(before)?.groupValues?.get(1) ?: return
                val registry = OkuRegistryCache.of(Path(page.path), host.containingFile.text) ?: return
                val own = page.path.removeSuffix(".md")
                val self = registry.pages.map { it.id }.filter { own.endsWith("/$it") }.maxByOrNull { it.length }
                val matching = result.withPrefixMatcher(typed)
                for (entry in registry.pages) {
                    if (entry.id == self) continue
                    matching.addElement(
                        LookupElementBuilder.create(entry.id)
                            .withLookupString(entry.title)
                            .withTypeText(entry.title, true),
                    )
                }
            }
        })
    }

    private companion object {
        /** The value of a `parent:` line up to the caret, past an opening quote. */
        val PARENT = Regex("""^parent:\s*["']?([^"'\s]*)$""")
    }
}
