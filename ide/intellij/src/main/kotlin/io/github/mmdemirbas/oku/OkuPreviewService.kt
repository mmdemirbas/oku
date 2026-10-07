package io.github.mmdemirbas.oku

import com.google.gson.Gson
import com.google.gson.JsonSyntaxException
import com.intellij.execution.configurations.PathEnvironmentVariableUtil
import com.intellij.openapi.Disposable
import com.intellij.openapi.application.PathManager
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.logger
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

/**
 * One `oku preview --serve` process for the whole IDE, shared by every open
 * preview, so a render after the first costs the page and not a Python start.
 *
 * The JSON it speaks is oku's contract (`PREVIEW_PROTOCOL` in oku's cli.py).
 * The process greets first; one that names another protocol is refused with
 * a message saying which side to update, rather than failing later on a
 * missing field. A process that dies or stops answering is replaced on the
 * next render.
 */
@Service(Service.Level.APP)
class OkuPreviewService : Disposable {
    private val log = logger<OkuPreviewService>()
    private val gson = Gson()
    private val lock = Any()
    private var session: Session? = null
    private var nextId = 0L

    val outBase: Path = Path(PathManager.getSystemPath(), "oku-preview")
    private val errLog: Path = outBase.resolve("preview.log")

    fun render(source: Path, text: String, theme: String): Result<Rendered> = runCatching {
        synchronized(lock) {
            val live = session?.takeIf { it.alive } ?: start().also { session = it }
            nextId += 1
            val request = gson.toJson(mapOf("id" to nextId, "path" to source.toString(), "text" to text, "theme" to theme))
            val line = live.ask(request, REQUEST_TIMEOUT_SECONDS) ?: run {
                live.kill()
                session = null
                error("oku preview did not answer within ${REQUEST_TIMEOUT_SECONDS}s${logTail()}")
            }
            val reply = parse(line)
            reply.error?.let { error(it) }
            val html = reply.html ?: error("oku preview answered without a page: $line")
            Rendered(
                Path(html),
                Path(requireNotNull(reply.root)),
                Path(requireNotNull(reply.out)),
                Path(requireNotNull(reply.page)),
                requireNotNull(reply.shell),
            )
        }
    }

    private fun start(): Session {
        val oku = launcher() ?: error("oku is not installed: no `oku` on PATH or in ~/.local/bin")
        Files.createDirectories(outBase)
        val builder = ProcessBuilder(oku.toString(), "preview", "--serve", "--out", outBase.toString())
        // A Dock-started IDE may hand the child no locale at all.
        builder.environment()["PYTHONIOENCODING"] = "utf-8"
        // To a file, not a pipe: a full stderr pipe would block the child.
        builder.redirectError(errLog.toFile())
        val started = Session(builder.start())
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
        log.info("oku preview session: oku ${hello.oku}, kit ${hello.kit}, protocol ${hello.protocol}")
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

    private fun parse(line: String): Reply = try {
        gson.fromJson(line, Reply::class.java)
    } catch (e: JsonSyntaxException) {
        throw IllegalStateException("oku preview printed something that is not JSON: $line", e)
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
        synchronized(lock) {
            session?.kill()
            session = null
        }
    }

    /** One line in, one line out, with a deadline on every read. */
    private class Session(private val process: Process) {
        private val lines = LinkedBlockingQueue<String>()
        private val writer = process.outputStream.bufferedWriter(Charsets.UTF_8)

        init {
            Thread({
                process.inputStream.bufferedReader(Charsets.UTF_8).useLines { all -> all.forEach(lines::put) }
                lines.put(CLOSED)
            }, "oku-preview-reader").apply { isDaemon = true }.start()
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

    /** Every field either message can carry; Gson leaves the absent ones null. */
    private class Reply(
        val protocol: Int? = null,
        val oku: String? = null,
        val kit: String? = null,
        val html: String? = null,
        val root: String? = null,
        val out: String? = null,
        val page: String? = null,
        val shell: String? = null,
        val error: String? = null,
    )

    private companion object {
        /** The `PREVIEW_PROTOCOL` of the oku this plugin is written against. */
        const val PROTOCOL = 2
        const val START_TIMEOUT_SECONDS = 30L
        const val REQUEST_TIMEOUT_SECONDS = 30L

        // Identity, not equality: a page whose output line is this text is
        // still a line.
        val CLOSED = String(charArrayOf('\u0000'))
    }
}
