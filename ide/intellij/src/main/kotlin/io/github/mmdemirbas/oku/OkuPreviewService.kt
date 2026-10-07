package io.github.mmdemirbas.oku

import com.google.gson.Gson
import com.google.gson.JsonSyntaxException
import com.intellij.execution.configurations.PathEnvironmentVariableUtil
import com.intellij.openapi.Disposable
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.PathManager
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.logger
import com.intellij.util.messages.Topic
import java.nio.file.Files
import java.nio.file.Path
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import kotlin.io.path.Path
import kotlin.io.path.isExecutable
import kotlin.io.path.readText

/**
 * What one render produced: the page, the two roots a link maps between,
 * the page JSON the HTML inlines, and `shell` — a digest of everything else
 * the HTML carries. Two renders of one `html` with one `shell` differ only
 * in `page`, which can then be handed to the page on screen instead of
 * reloading it.
 */
data class Rendered(val html: Path, val root: Path, val out: Path, val page: Path, val shell: String)

/** One finding of `oku check` for a page; `line` is 1-based, absent for the page as a whole. */
data class Issue(val severity: String, val code: String, val where: String, val message: String, val line: Int?)

/** Told when an oku session names the JSON schema of each `oku-*` fence body. */
fun interface OkuFencesListener {
    fun fencesChanged(fences: Map<String, Path>)

    companion object {
        @Topic.AppLevel
        val TOPIC = Topic(OkuFencesListener::class.java, Topic.BroadcastDirection.NONE)
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
 * later on a missing field. The greeting also maps every `oku-*` fence to a
 * JSON schema for its body ([fences]). A process that dies or stops
 * answering is replaced on the next request.
 */
@Service(Service.Level.APP)
class OkuPreviewService : Disposable {
    private val log = logger<OkuPreviewService>()
    private val gson = Gson()

    val outBase: Path = Path(PathManager.getSystemPath(), "oku-preview")

    private val previews = Channel("preview")
    private val checks = Channel("check")

    /** Fence tag (`oku-chart`) → the schema of its body, once a session has greeted. */
    @Volatile
    var fences: Map<String, Path> = emptyMap()
        private set

    fun render(source: Path, text: String, theme: String): Result<Rendered> =
        previews.ask(mapOf("path" to source.toString(), "text" to text, "theme" to theme)) { reply, line ->
            val html = reply.html ?: error("oku preview answered without a page: $line")
            Rendered(
                Path(html),
                Path(requireNotNull(reply.root)),
                Path(requireNotNull(reply.out)),
                Path(requireNotNull(reply.page)),
                requireNotNull(reply.shell),
            )
        }

    /** What `oku check` would report for [source] if it held [text], inside its tree. */
    fun check(source: Path, text: String): Result<List<Issue>> =
        checks.ask(mapOf("path" to source.toString(), "text" to text, "check" to true)) { reply, line ->
            reply.issues ?: error("oku preview answered a check without issues: $line")
        }

    private fun parse(line: String): Reply = try {
        gson.fromJson(line, Reply::class.java)
    } catch (e: JsonSyntaxException) {
        throw IllegalStateException("oku preview printed something that is not JSON: $line", e)
    }

    private fun greeted(hello: Reply) {
        val named = hello.fences?.mapValues { Path(it.value) } ?: return
        if (named == fences) return
        fences = named
        ApplicationManager.getApplication().messageBus.syncPublisher(OkuFencesListener.TOPIC).fencesChanged(named)
    }

    /**
     * `-Doku.executable=/path/to/oku` points the plugin at a checkout while
     * developing it; otherwise the launcher `uv tool install` puts on PATH,
     * looked for in ~/.local/bin too because a Dock-started IDE has no shell PATH.
     */
    private fun launcher(): Path? {
        System.getProperty("oku.executable")?.let { return Path(it) }
        PathEnvironmentVariableUtil.findInPath("oku")?.let { return it.toPath() }
        return Path(System.getProperty("user.home"), ".local", "bin", "oku").takeIf { it.isExecutable() }
    }

    override fun dispose() {
        previews.close()
        checks.close()
    }

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
            val oku = launcher() ?: error("oku is not installed: no `oku` on PATH or in ~/.local/bin")
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
        val html: String? = null,
        val root: String? = null,
        val out: String? = null,
        val page: String? = null,
        val shell: String? = null,
        val issues: List<Issue>? = null,
        val error: String? = null,
    )

    private companion object {
        /** The `PREVIEW_PROTOCOL` of the oku this plugin is written against. */
        const val PROTOCOL = 3
        const val START_TIMEOUT_SECONDS = 30L
        const val REQUEST_TIMEOUT_SECONDS = 30L

        // Identity, not equality: a page whose output line is this text is
        // still a line.
        val CLOSED = String(charArrayOf('\u0000'))
    }
}
