package io.github.mmdemirbas.oku

import com.intellij.codeInsight.daemon.DaemonCodeAnalyzer
import com.intellij.execution.configurations.PathEnvironmentVariableUtil
import com.intellij.openapi.components.BaseState
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.SimplePersistentStateComponent
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.openapi.components.service
import com.intellij.openapi.fileChooser.FileChooserDescriptorFactory
import com.intellij.openapi.options.BoundConfigurable
import com.intellij.openapi.project.ProjectManager
import com.intellij.openapi.ui.DialogPanel
import com.intellij.ui.dsl.builder.AlignX
import com.intellij.ui.dsl.builder.bindSelected
import com.intellij.ui.dsl.builder.bindText
import com.intellij.ui.dsl.builder.panel
import java.nio.file.Path
import kotlin.io.path.Path
import kotlin.io.path.isDirectory
import kotlin.io.path.isExecutable

/** What the reader chose in Settings → Tools → oku. */
@Service(Service.Level.APP)
@State(name = "OkuSettings", storages = [Storage("oku.xml")])
class OkuSettings : SimplePersistentStateComponent<OkuSettings.Options>(Options()) {

    class Options : BaseState() {
        /** Off: no markdown file is an oku page, so nothing in this plugin runs. */
        var enabled by property(true)

        /** The oku to run; blank finds one ([OkuLauncher]). */
        var executable by string()
    }

    companion object {
        fun get(): OkuSettings = service()
    }
}

/** Which oku would run, or why none can. */
sealed interface OkuLaunch {
    data class Found(val path: Path) : OkuLaunch
    data class Missing(val reason: String) : OkuLaunch
}

object OkuLauncher {
    /**
     * `-Doku.executable` first (a checkout, while developing the plugin),
     * then the path set in the settings, then `oku` on PATH, then the
     * launcher `uv tool install` writes to ~/.local/bin — looked for by name
     * because an IDE started from the Dock has no shell PATH. A path set in
     * the settings that does not run is reported as that, never passed over
     * for another oku: the reader asked for that one.
     */
    fun find(): OkuLaunch {
        System.getProperty("oku.executable")?.let { return OkuLaunch.Found(Path(it)) }
        val chosen = OkuSettings.get().state.executable?.trim().orEmpty()
        if (chosen.isNotEmpty()) {
            val path = expandHome(chosen)
            return if (path.isExecutable() && !path.isDirectory()) {
                OkuLaunch.Found(path)
            } else {
                OkuLaunch.Missing("the oku set in Settings → Tools → oku is not a program that runs: $chosen")
            }
        }
        PathEnvironmentVariableUtil.findInPath("oku")?.let { return OkuLaunch.Found(it.toPath()) }
        val local = Path(System.getProperty("user.home"), ".local", "bin", "oku")
        if (local.isExecutable()) return OkuLaunch.Found(local)
        return OkuLaunch.Missing("oku is not installed: no `oku` on PATH or in ~/.local/bin, and none set in Settings → Tools → oku")
    }

    private fun expandHome(path: String): Path =
        if (path == "~" || path.startsWith("~/")) Path(System.getProperty("user.home") + path.removePrefix("~")) else Path(path)
}

class OkuConfigurable : BoundConfigurable("oku") {
    private val options = OkuSettings.get().state

    override fun createPanel(): DialogPanel = panel {
        row {
            checkBox("Open oku pages with oku's own rendering, and check them as they are typed")
                .bindSelected(options::enabled)
                .comment(
                    "An oku page is a markdown file in a tree with a kit.json or an _oku link, or one using an " +
                        "```oku- fence. Off: every markdown file is plain markdown. A file already open changes " +
                        "when it is opened again.",
                )
        }
        row("oku executable:") {
            textFieldWithBrowseButton(
                FileChooserDescriptorFactory.createSingleFileNoJarsDescriptor().withTitle("The oku Program"),
            )
                .bindText({ options.executable.orEmpty() }, { options.executable = it.trim().ifEmpty { null } })
                .align(AlignX.FILL)
                .comment("Empty: the oku on PATH, else ~/.local/bin/oku. In use now: ${inUse()}")
        }
    }

    override fun apply() {
        val before = options.enabled to options.executable
        super.apply()
        if (before == (options.enabled to options.executable)) return
        // The next request starts the oku now chosen, and every open page is
        // checked again with it — or not at all.
        service<OkuPreviewService>().restart()
        for (project in ProjectManager.getInstance().openProjects) {
            if (!project.isDisposed) DaemonCodeAnalyzer.getInstance(project).restart("oku settings changed")
        }
    }

    private fun inUse(): String = when (val launch = OkuLauncher.find()) {
        is OkuLaunch.Found -> launch.path.toString()
        is OkuLaunch.Missing -> "none — ${launch.reason}"
    }
}
