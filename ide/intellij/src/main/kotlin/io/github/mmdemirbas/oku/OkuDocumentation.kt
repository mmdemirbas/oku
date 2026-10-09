package io.github.mmdemirbas.oku

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.intellij.lang.documentation.DocumentationMarkup
import com.intellij.model.Pointer
import com.intellij.openapi.components.service
import com.intellij.openapi.util.text.StringUtil
import com.intellij.platform.backend.documentation.DocumentationResult
import com.intellij.platform.backend.documentation.DocumentationTarget
import com.intellij.platform.backend.documentation.DocumentationTargetProvider
import com.intellij.platform.backend.presentation.TargetPresentation
import com.intellij.psi.PsiFile
import com.intellij.psi.util.PsiTreeUtil
import org.intellij.plugins.markdown.lang.psi.impl.MarkdownCodeFence
import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.Path

/**
 * What the reader of a page will see, shown to its author on hover: the
 * definition behind `#g/term` and `#x/ref` (in the page's language, as the
 * tooltip draws it), what an `oku-*` fence is with its keys and oku's own
 * example, and what a `> [!TYPE]` alert is for.
 *
 * A registry name the tree does not activate says so instead of showing
 * nothing: an empty popup reads as "the IDE does not know", where this is
 * the finding `oku check` reports.
 */
class OkuDocumentation : DocumentationTargetProvider {
    override fun documentationTargets(file: PsiFile, offset: Int): List<DocumentationTarget> {
        val page = file.originalFile.viewProvider.virtualFile
        if (!page.isInLocalFileSystem || !OkuPages.isOkuPage(page)) return emptyList()
        val leaf = file.findElementAt(offset) ?: return emptyList()
        val greeting = service<OkuPreviewService>().greeting
        okuDestination(leaf)?.let { destination ->
            val link = destination.text
            val kind = listOf("glossary-term" to Registry::glossary, "ext-ref" to Registry::extrefs)
                .firstOrNull { (k, _) -> greeting.inline[k]?.let(link::startsWith) == true } ?: return emptyList()
            val name = link.removePrefix(requireNotNull(greeting.inline[kind.first]))
            return listOf(RegistryDoc(Path(page.path), file.text, name, kind.first == "glossary-term"))
        }
        PsiTreeUtil.getParentOfType(leaf, MarkdownCodeFence::class.java, false)?.let { fence ->
            val text = fence.text
            val tag = fenceTag(fence.fenceLanguage) ?: return emptyList()
            val schema = greeting.fences[tag] ?: return emptyList()
            val at = text.indexOf(tag)
            val from = fence.textRange.startOffset + at
            if (at < 0 || offset !in from until from + tag.length) return emptyList()
            val type = CHART_TYPE.find(text)?.groupValues?.get(1)
            val example = greeting.snippets.firstOrNull { it.tag == tag && (it.type == null || it.type == type) }
                ?: greeting.snippets.firstOrNull { it.tag == tag }
            return listOf(FenceDoc(tag, schema, example?.body))
        }
        val document = file.viewProvider.document ?: return emptyList()
        val line = document.getLineNumber(offset)
        val start = document.getLineStartOffset(line)
        val alert = ALERT.find(document.charsSequence.subSequence(start, document.getLineEndOffset(line))) ?: return emptyList()
        val type = alert.groups[1] ?: return emptyList()
        if (offset - start !in type.range) return emptyList()
        val what = greeting.admonitions[type.value.uppercase()] ?: return emptyList()
        return listOf(AlertDoc(type.value.uppercase(), what))
    }

    private companion object {
        val CHART_TYPE = Regex(""""type"\s*:\s*"([^"]+)"""")
        val ALERT = Regex("""^\s*>\s?\[!([A-Za-z]+)]""")
    }
}

private fun doc(name: String, body: String, sections: List<Pair<String, String>> = emptyList()): String = buildString {
    append(DocumentationMarkup.DEFINITION_START).append(StringUtil.escapeXmlEntities(name)).append(DocumentationMarkup.DEFINITION_END)
    append(DocumentationMarkup.CONTENT_START).append(body).append(DocumentationMarkup.CONTENT_END)
    if (sections.isNotEmpty()) {
        append(DocumentationMarkup.SECTIONS_START)
        for ((label, value) in sections) {
            append(DocumentationMarkup.SECTION_HEADER_START).append(label).append(DocumentationMarkup.SECTION_SEPARATOR)
                .append(value).append(DocumentationMarkup.SECTION_END)
        }
        append(DocumentationMarkup.SECTIONS_END)
    }
}

private fun escaped(text: String): String = StringUtil.escapeXmlEntities(text)

/** `#g/term` or `#x/ref`; asked of oku off the read action, since that is a process round trip. */
private class RegistryDoc(val page: Path, val text: String, val name: String, val glossary: Boolean) : DocumentationTarget {
    override fun createPointer(): Pointer<out DocumentationTarget> = Pointer.hardPointer(this)

    override fun computePresentation(): TargetPresentation = TargetPresentation.builder(name).presentation()

    override fun computeDocumentation(): DocumentationResult = DocumentationResult.asyncDocumentation {
        val registry = OkuRegistryCache.of(page, text)
        val entry = registry?.let { if (glossary) it.glossary else it.extrefs }?.firstOrNull { it.term == name }
        val body = when {
            registry == null -> "oku could not say what this page can name."
            entry == null -> "Not in any domain this tree activates, nor among its own entries: " +
                "<code>oku check</code> reports the link."
            entry.def.isEmpty() -> "No definition is written for it."
            else -> escaped(entry.def)
        }
        val kind = if (glossary) "Glossary term" else "External reference"
        DocumentationResult.documentation(doc(name, body, listOfNotNull(("Kind:" to kind), entry?.let { "Domain:" to escaped(it.domain) })))
    }
}

/** An `oku-*` fence: what its schema says it is, its keys, and the example oku inserts. */
private class FenceDoc(val tag: String, val schema: Path, val example: String?) : DocumentationTarget {
    override fun createPointer(): Pointer<out DocumentationTarget> = Pointer.hardPointer(this)

    override fun computePresentation(): TargetPresentation = TargetPresentation.builder(tag).presentation()

    override fun computeDocumentation(): DocumentationResult {
        val json = runCatching { JsonParser.parseString(Files.readString(schema)).asJsonObject }.getOrNull() ?: JsonObject()
        val required = json.getAsJsonArray("required")?.map { it.asString }.orEmpty()
        val keys = json.getAsJsonObject("properties")?.keySet().orEmpty().filter { it != "k" }
        val shown = keys.take(SHOWN_KEYS).joinToString(", ") { if (it in required) "<b>$it</b>" else it } +
            if (keys.size > SHOWN_KEYS) ", … ${keys.size - SHOWN_KEYS} more" else ""
        val what = json.get("description")?.takeIf { it.isJsonPrimitive }?.asString
            ?: "An oku component; its body is one JSON object."
        val sections = buildList {
            if (keys.isNotEmpty()) add("Keys:" to shown)
            if (example != null) add("Example:" to "<pre>${escaped(example)}</pre>")
        }
        return DocumentationResult.documentation(doc(tag, escaped(what), sections))
    }

    private companion object {
        const val SHOWN_KEYS = 16
    }
}

/** A `> [!TYPE]` alert and what the kit draws it for. */
private class AlertDoc(val type: String, val what: String) : DocumentationTarget {
    override fun createPointer(): Pointer<out DocumentationTarget> = Pointer.hardPointer(this)

    override fun computePresentation(): TargetPresentation = TargetPresentation.builder("[!$type]").presentation()

    override fun computeDocumentation(): DocumentationResult = DocumentationResult.documentation(doc("[!$type]", escaped(what)))
}
