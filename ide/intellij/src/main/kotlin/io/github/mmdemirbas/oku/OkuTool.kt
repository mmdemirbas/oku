package io.github.mmdemirbas.oku

import com.intellij.execution.configurations.PathEnvironmentVariableUtil
import com.intellij.openapi.application.PathManager
import com.intellij.openapi.diagnostic.logger
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import java.util.concurrent.TimeUnit
import kotlin.io.path.Path
import kotlin.io.path.exists
import kotlin.io.path.isExecutable
import kotlin.io.path.readLines

/** What one render produced: the page, and the two roots a link maps between. */
data class Rendered(val html: Path, val root: Path, val out: Path)

/**
 * Runs the installed oku tool's Python over the PoC bridge script.
 *
 * The IDE is usually started from the Dock, so the shell's PATH is not
 * there; the launcher is looked for where `uv tool install` puts it too.
 */
object OkuTool {
    private val log = logger<OkuTool>()
    private const val TIMEOUT_SECONDS = 30L

    val outBase: Path = Path(PathManager.getSystemPath(), "oku-preview")

    private val script: Path by lazy {
        Files.createDirectories(outBase)
        val target = outBase.resolve("preview.py")
        val bundled = requireNotNull(OkuTool::class.java.getResourceAsStream("/oku-preview/preview.py")) {
            "preview.py is missing from the plugin jar"
        }
        bundled.use {
            Files.copy(it, target, StandardCopyOption.REPLACE_EXISTING)
        }
        target
    }

    /** The interpreter named in the `oku` launcher's shebang. */
    fun python(): Path? {
        val home = System.getProperty("user.home")
        val launchers = listOfNotNull(
            PathEnvironmentVariableUtil.findInPath("oku")?.toPath(),
            Path(home, ".local", "bin", "oku"),
        )
        for (launcher in launchers) {
            if (!launcher.exists()) continue
            val first = runCatching { launcher.readLines().firstOrNull() }.getOrNull() ?: continue
            if (!first.startsWith("#!")) continue
            val interpreter = Path(first.removePrefix("#!").trim().split(" ").first())
            if (interpreter.isExecutable()) return interpreter
        }
        return Path(home, ".local", "share", "uv", "tools", "oku", "bin", "python").takeIf { it.isExecutable() }
    }

    private val lock = Any()

    fun render(source: Path, text: String, theme: String): Result<Rendered> = runCatching {
        val python = python() ?: error("oku is not installed: no `oku` launcher on PATH or in ~/.local/bin")
        // One render at a time: two overlapping ones write the same file.
        synchronized(lock) {
            val builder = ProcessBuilder(
                python.toString(), script.toString(),
                "--path", source.toString(), "--out-base", outBase.toString(), "--theme", theme,
            )
            // A Dock-started IDE may hand the child no locale at all.
            builder.environment()["PYTHONIOENCODING"] = "utf-8"
            // To a file, not a pipe: a full stderr pipe blocks the child
            // while this thread is still reading stdout.
            val errLog = outBase.resolve("preview.log")
            builder.redirectError(errLog.toFile())
            val process = builder.start()
            process.outputStream.use { it.write(text.toByteArray(Charsets.UTF_8)) }
            val stdout = process.inputStream.bufferedReader(Charsets.UTF_8).readText()
            if (!process.waitFor(TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
                process.destroyForcibly()
                error("oku preview timed out after ${TIMEOUT_SECONDS}s")
            }
            val stderr = Files.readString(errLog)
            if (process.exitValue() != 0) error("oku preview failed (exit ${process.exitValue()}):\n$stderr")
            log.info(stderr.trim())
            val line = stdout.lines().last { it.isNotBlank() }
            Rendered(Path(field(line, "html")), Path(field(line, "root")), Path(field(line, "out")))
        }
    }

    // The bridge prints one flat JSON object of three path strings; a JSON
    // library would be the only dependency the plugin has.
    private fun field(json: String, name: String): String =
        Regex("\"$name\":\\s*\"((?:[^\"\\\\]|\\\\.)*)\"").find(json)?.groupValues?.get(1)
            ?.replace("\\/", "/")?.replace("\\\"", "\"")?.replace("\\\\", "\\")
            ?: error("oku preview printed no `$name`: $json")
}
