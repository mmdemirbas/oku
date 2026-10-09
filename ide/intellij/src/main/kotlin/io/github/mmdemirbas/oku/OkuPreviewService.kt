package io.github.mmdemirbas.oku

import com.google.gson.Gson
import com.google.gson.JsonSyntaxException
import com.intellij.openapi.Disposable
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.PathManager
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.logger
import com.intellij.util.messages.Topic
import kotlinx.coroutines.CoroutineScope
import java.nio.file.Files
import java.nio.file.Path
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import kotlin.io.path.Path
import kotlin.io.path.exists
import kotlin.io.path.extension
import kotlin.io.path.pathString
import kotlin.io.path.readText

/**
 * What one render produced: the page, the two roots a link maps between,
 * the page JSON the HTML inlines, and `shell` — a digest of everything else
 * the HTML carries. Two renders of one `html` with one `shell` differ only
 * in `page`, which can then be handed to the page on screen instead of
 * reloading it.
 */
data class Rendered(val html: Path, val root: Path, val out: Path, val page: Path?, val shell: String) {
    /**
     * Where a link out of this render goes in the project. A page of the same
     * tree is rendered as `x.html` beside this one and is `x.md` in the tree;
     * a page with no `.md` — a front door — is its shell, `index.html`.
     */
    fun sourceOf(target: Path): Path {
        if (!target.startsWith(out)) return target
        val rel = out.relativize(target)
        val asMd = root.resolve(rel).resolveSibling(rel.fileName.pathString.removeSuffix(".html") + ".md")
        return if (target.extension == "html" && asMd.exists()) asMd else root.resolve(rel)
    }
}

/** A term a page can name with `#g/`, or a reference with `#x/`, and what its reader sees on hover. */
data class RegistryEntry(val term: String, val domain: String, val def: String)

/** Everything a page can name with `#g/` ([glossary]) and `#x/` ([extrefs]), as `oku check` resolves them. */
data class Registry(val glossary: List<RegistryEntry>, val extrefs: List<RegistryEntry>)

/** One finding of `oku check` for a page; `line` is 1-based, absent for the page as a whole. */
data class Issue(val severity: String, val code: String, val where: String, val message: String, val line: Int?)

/**
 * What an oku session says about the format when it starts: the JSON schema
 * of each `oku-*` fence body (`oku-chart` → its file), the link prefixes
 * that are not heading anchors (`filepath` → `#f/`), and every component an
 * author can insert.
 */
data class Greeting(
    val fences: Map<String, Path>,
    val inline: Map<String, String>,
    val snippets: List<Snippet> = emptyList(),
)

/**
 * A component as an editor inserts it: the fence tag, the chart type when it
 * is a chart (null for any other kind), and the body — the payload `oku spec`
 * prints, a key per line and a record per line.
 */
data class Snippet(val tag: String, val type: String?, val body: String)

/** Told when an oku session's greeting says something new. */
fun interface OkuGreetingListener {
    fun greeted(greeting: Greeting)

    companion object {
        @Topic.AppLevel
        val TOPIC = Topic(OkuGreetingListener::class.java, Topic.BroadcastDirection.NONE)
    }
}

/**
 * `oku preview --serve` for the whole IDE: one process renders every open
 * preview, a second one checks pages, so a render after the first costs the
 * page and not a Python start, and a render never waits behind a check of
 * a whole tree.
 *
 * The JSON they speak is oku's contract (`PREVIEW_PROTOCOL` in oku's
 * cli.py). A process greets first; one that names another protocol is
 * refused with a message saying which side to update, rather than failing
 * later on a missing field. The greeting also says what the editor needs
 * to know about the format ([greeting]). A process that dies or stops
 * answering is replaced on the next request, and so is every process when
 * the settings name another oku ([restart]).
 *
 * [scope] lives as long as the IDE; each preview runs its own work in a
 * child of it.
 */
@Service(Service.Level.APP)
class OkuPreviewService(val scope: CoroutineScope) : Disposable {
    private val log = logger<OkuPreviewService>()
    private val gson = Gson()

    val outBase: Path = Path(PathManager.getSystemPath(), "oku-preview")

    private val previews = Channel("preview")
    private val checks = Channel("check")

    /** The last greeting, empty until a session has started. */
    @Volatile
    var greeting: Greeting = Greeting(emptyMap(), emptyMap())
        private set

    /** Fence tag (`oku-chart`) → the schema of its body, once a session has greeted. */
    val fences: Map<String, Path> get() = greeting.fences

    /**
     * Render [source] holding [text]; a shell (`index.html`) has no text of
     * its own, so oku reads it, and a front door comes back with no `page`.
     */
    fun render(source: Path, text: String?, theme: String): Result<Rendered> =
        previews.ask(buildMap { put("path", source.toString()); text?.let { put("text", it) }; put("theme", theme) }) { reply, line ->
            val html = reply.html ?: error("oku preview answered without a page: $line")
            Rendered(
                Path(html),
                Path(requireNotNull(reply.root)),
                Path(requireNotNull(reply.out)),
                reply.page?.let(::Path),
                requireNotNull(reply.shell),
            )
        }

    /** What `oku check` would report for [source] if it held [text], inside its tree. */
    fun check(source: Path, text: String): Result<List<Issue>> =
        checks.ask(mapOf("path" to source.toString(), "text" to text, "check" to true)) { reply, line ->
            reply.issues ?: error("oku preview answered a check without issues: $line")
        }

    /**
     * The source line of the heading whose id is [anchor] on the page at
     * [source], or null when no heading has it. [text] is the page's unsaved
     * buffer when it has one; without it oku reads the file.
     */
    fun anchorLine(source: Path, anchor: String, text: String?): Result<Int?> {
        val fields = mutableMapOf<String, Any>("path" to source.toString(), "anchor" to anchor)
        if (text != null) fields["text"] = text
        return checks.ask(fields) { reply, _ -> reply.line }
    }

    /**
     * What the page at [source] can name with `#g/` and `#x/`: the slice of
     * the kit's registries its tree's kit.json activates, plus the project's
     * own entries — the slice `oku check` resolves its links against. [text]
     * is the unsaved buffer, read for its `lang:`.
     */
    fun registry(source: Path, text: String?): Result<Registry> {
        val fields = mutableMapOf<String, Any>("path" to source.toString(), "registry" to true)
        if (text != null) fields["text"] = text
        return checks.ask(fields) { reply, line ->
            Registry(
                reply.glossary ?: error("oku preview answered without a glossary: $line"),
                reply.extrefs ?: error("oku preview answered without external references: $line"),
            )
        }
    }

    private fun parse(line: String): Reply = try {
        gson.fromJson(line, Reply::class.java)
    } catch (e: JsonSyntaxException) {
        throw IllegalStateException("oku preview printed something that is not JSON: $line", e)
    }

    private fun greeted(hello: Reply) {
        val said = Greeting(
            hello.fences.orEmpty().mapValues { Path(it.value) },
            hello.inline.orEmpty(),
            hello.snippets.orEmpty(),
        )
        if (said == greeting) return
        greeting = said
        ApplicationManager.getApplication().messageBus.syncPublisher(OkuGreetingListener.TOPIC).greeted(said)
    }

    /** End both processes; the next request starts whichever oku [OkuLauncher] finds then. */
    fun restart() {
        previews.close()
        checks.close()
    }

    override fun dispose() = restart()

    /** One process and the requests it answers, one at a time. */
    private inner class Channel(private val name: String) {
        private val lock = Any()
        private var session: Session? = null
        private var nextId = 0L
        private val errLog: Path = outBase.resolve("$name.log")

        fun <T> ask(fields: Map<String, Any>, read: (Reply, String) -> T): Result<T> = runCatching {
            synchronized(lock) {
                val live = session?.takeIf { it.alive } ?: start().also { session = it }
                nextId += 1
                val line = live.ask(gson.toJson(mapOf("id" to nextId) + fields), REQUEST_TIMEOUT_SECONDS) ?: run {
                    live.kill()
                    session = null
                    error("oku preview did not answer within ${REQUEST_TIMEOUT_SECONDS}s${logTail()}")
                }
                val reply = parse(line)
                reply.error?.let { error(it) }
                read(reply, line)
            }
        }

        private fun start(): Session {
            val oku = when (val launch = OkuLauncher.find()) {
                is OkuLaunch.Found -> launch.path
                is OkuLaunch.Missing -> error(launch.reason)
            }
            Files.createDirectories(outBase)
            val builder = ProcessBuilder(oku.toString(), "preview", "--serve", "--out", outBase.toString())
            // A Dock-started IDE may hand the child no locale at all.
            builder.environment()["PYTHONIOENCODING"] = "utf-8"
            // To a file, not a pipe: a full stderr pipe would block the child.
            // One per process, because opening it truncates it.
            builder.redirectError(errLog.toFile())
            val started = Session(builder.start(), name)
            val hello = started.next(START_TIMEOUT_SECONDS)?.let(::parse)
            if (hello?.protocol == null) {
                started.kill()
                error(startFailure())
            }
            if (hello.protocol != PROTOCOL) {
                started.kill()
                val update = if (hello.protocol < PROTOCOL) "oku (./ctl deploy in the oku repository)" else "this plugin"
                error("oku ${hello.oku} speaks preview protocol ${hello.protocol}, this plugin speaks $PROTOCOL: update $update")
            }
            log.info("oku $name session: oku ${hello.oku}, kit ${hello.kit}, protocol ${hello.protocol}")
            greeted(hello)
            return started
        }

        private fun startFailure(): String {
            val said = logTail()
            return if ("invalid choice: 'preview'" in said) {
                "the installed oku has no `preview` command: update it (./ctl deploy in the oku repository)"
            } else {
                "oku preview did not start$said"
            }
        }

        private fun logTail(): String {
            val text = runCatching { errLog.readText() }.getOrNull()?.trim().orEmpty()
            return if (text.isEmpty()) "" else ":\n" + text.lines().takeLast(12).joinToString("\n")
        }

        fun close() {
            synchronized(lock) {
                session?.kill()
                session = null
            }
        }
    }

    /** One line in, one line out, with a deadline on every read. */
    private class Session(private val process: Process, name: String) {
        private val lines = LinkedBlockingQueue<String>()
        private val writer = process.outputStream.bufferedWriter(Charsets.UTF_8)

        init {
            Thread({
                process.inputStream.bufferedReader(Charsets.UTF_8).useLines { all -> all.forEach(lines::put) }
                lines.put(CLOSED)
            }, "oku-$name-reader").apply { isDaemon = true }.start()
        }

        val alive: Boolean get() = process.isAlive

        fun next(timeoutSeconds: Long): String? =
            lines.poll(timeoutSeconds, TimeUnit.SECONDS)?.takeIf { it !== CLOSED }

        fun ask(request: String, timeoutSeconds: Long): String? {
            writer.write(request)
            writer.newLine()
            writer.flush()
            return next(timeoutSeconds)
        }

        fun kill() {
            process.destroy()
            if (!process.waitFor(2, TimeUnit.SECONDS)) process.destroyForcibly()
        }
    }

    /** Every field any message can carry; Gson leaves the absent ones null. */
    private class Reply(
        val protocol: Int? = null,
        val oku: String? = null,
        val kit: String? = null,
        val fences: Map<String, String>? = null,
        val inline: Map<String, String>? = null,
        val snippets: List<Snippet>? = null,
        val html: String? = null,
        val root: String? = null,
        val out: String? = null,
        val page: String? = null,
        val shell: String? = null,
        val issues: List<Issue>? = null,
        val line: Int? = null,
        val glossary: List<RegistryEntry>? = null,
        val extrefs: List<RegistryEntry>? = null,
        val error: String? = null,
    )

    private companion object {
        /** The `PREVIEW_PROTOCOL` of the oku this plugin is written against. */
        const val PROTOCOL = 5
        const val START_TIMEOUT_SECONDS = 30L
        const val REQUEST_TIMEOUT_SECONDS = 30L

        // Identity, not equality: a page whose output line is this text is
        // still a line.
        val CLOSED = String(charArrayOf('\u0000'))
    }
}
