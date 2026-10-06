plugins {
    id("org.jetbrains.kotlin.jvm") version "2.4.20"
    id("org.jetbrains.intellij.platform") version "2.19.0"
}

group = "io.github.mmdemirbas"
version = "0.0.1-poc"

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
    }
}

kotlin {
    jvmToolchain(21)
}

intellijPlatform {
    pluginConfiguration {
        ideaVersion {
            sinceBuild = "262"
            untilBuild = provider { null }
        }
    }
    // A PoC has no searchable options worth indexing; this step boots a
    // headless IDE and costs most of the build.
    buildSearchableOptions = false
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
    // -PokuExecutable=/abs/oku/bin/oku runs the preview from a checkout.
    providers.gradleProperty("okuExecutable").orNull?.let { jvmArgs("-Doku.executable=$it") }
}
