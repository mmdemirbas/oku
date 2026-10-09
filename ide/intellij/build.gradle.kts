import org.jetbrains.intellij.platform.gradle.TestFrameworkType
import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

plugins {
    id("org.jetbrains.kotlin.jvm") version "2.4.20"
    id("org.jetbrains.intellij.platform") version "2.19.0"
}

group = "io.github.mmdemirbas"
version = "0.4.0"

repositories {
    mavenCentral()
    intellijPlatform {
        defaultRepositories()
    }
}

dependencies {
    intellijPlatform {
        local(providers.gradleProperty("ideaPath"))
        // JCEF is its own bundled plugin since 2026.x, not part of the core.
        bundledPlugin("com.intellij.modules.jcef")
        // Optional at runtime (plugin.xml): what an author gets while typing.
        bundledPlugin("org.intellij.plugins.markdown")
        bundledPlugin("com.intellij.modules.json")
        testFramework(TestFrameworkType.Platform)
        pluginVerifier()
    }
    testImplementation("junit:junit:4.13.2")
}

// Bytecode for Java 21, compiled by whichever JDK runs Gradle. Not a
// toolchain: that demands a JDK 21 on the machine, and `./ctl deploy ide`
// builds on the runtime of the IDE being installed into — Java 25 in
// 2026.2, which every machine with that IDE already has.
tasks.withType<KotlinCompile>().configureEach {
    compilerOptions { jvmTarget = JvmTarget.JVM_21 }
}
java {
    sourceCompatibility = JavaVersion.VERSION_21
    targetCompatibility = JavaVersion.VERSION_21
}

intellijPlatform {
    pluginConfiguration {
        ideaVersion {
            sinceBuild = "262"
            untilBuild = provider { null }
        }
    }
    // Two settings rows are not worth indexing for Settings search; this
    // step boots a headless IDE and costs most of the build.
    buildSearchableOptions = false
    pluginVerification {
        // The IDE the plugin is built against. The verifier still fetches the
        // plugins that IDE's own plugins depend on from the Marketplace:
        // 915 MB on the first run, cached after it.
        ides {
            local(file(providers.gradleProperty("ideaPath").get()))
        }
    }
}

tasks.runIde {
    // Lets a test drive the preview's Chromium over CDP, the way the
    // repo's browser suite drives a built page.
    jvmArgs(
        "-Dide.browser.jcef.debug.port=9222",
        // A sandbox has no user to answer first-run dialogs.
        "-Djb.consents.confirmation.enabled=false",
        "-Djb.privacy.policy.text=<!--999.999-->",
        "-Didea.trust.all.projects=true",
        "-Didea.trust.disabled=true",
    )
    providers.gradleProperty("openPaths").orNull?.let { args(it.split(",")) }
    // -PokuExecutable=/abs/oku/.venv/bin/oku runs the preview from a checkout.
    // Not bin/oku: run directly its shebang is the system python3, without
    // jsonschema, and oku then skips schema validation without a word.
    providers.gradleProperty("okuExecutable").orNull?.let { jvmArgs("-Doku.executable=$it") }
    // -Pbackground: on macOS the sandbox runs as a UI element (no Dock icon,
    // no menu bar) and never takes focus from the app in front, so it can be
    // measured over CDP while someone is using the machine.
    if (providers.gradleProperty("background").isPresent) jvmArgs("-Dapple.awt.UIElement=true")
}

tasks.prepareTestSandbox {
    // The local IDEA's ultimate-plugin registers an obfuscated startup
    // activity whose constructor the test framework cannot call, and the
    // error it logs fails every test. Nothing under test needs it.
    disabledPlugins.add("com.intellij.modules.ultimate")
}

tasks.test {
    // The checkout's oku (`uv sync` in the repo root makes it), so a test
    // exercises the oku this repository holds rather than whichever one is
    // installed. Not bin/oku, whose shebang finds a python3 without jsonschema.
    systemProperty("oku.executable", rootProject.projectDir.resolve("../../.venv/bin/oku").canonicalPath)
}
