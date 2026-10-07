package io.github.mmdemirbas.oku

import com.intellij.openapi.components.service
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.LightProjectDescriptor
import com.intellij.testFramework.UsefulTestCase
import com.intellij.testFramework.fixtures.CodeInsightTestFixture
import com.intellij.testFramework.fixtures.IdeaTestFixtureFactory
import com.intellij.testFramework.fixtures.impl.TempDirTestFixtureImpl
import kotlin.io.path.Path

/**
 * A light project whose files are on disk: every feature under test hands
 * a page's path to oku, and a `temp://` file has no path oku can read.
 */
abstract class OkuFixtureTestCase : UsefulTestCase() {
    protected lateinit var fixture: CodeInsightTestFixture

    override fun setUp() {
        super.setUp()
        val factory = IdeaTestFixtureFactory.getFixtureFactory()
        val project = factory.createLightFixtureBuilder(LightProjectDescriptor.EMPTY_PROJECT_DESCRIPTOR, name).fixture
        fixture = factory.createCodeInsightFixture(project, TempDirTestFixtureImpl())
        fixture.setUp()
        greet()
    }

    /**
     * A session that has greeted before anything is highlighted. The first
     * greeting names the fence schemas and the JSON support is reset to read
     * them — in the IDE that restarts the daemon, which is the point; inside
     * a test's highlighting the framework refuses it as a model change.
     */
    private fun greet() {
        val text = "---\ntitle: W\n---\n\nwarm\n"
        val warm = fixture.tempDirFixture.createFile("warm/w.md", text)
        service<OkuPreviewService>().check(Path(warm.path), text).getOrThrow()
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
    }

    override fun tearDown() {
        try {
            fixture.tearDown()
        } catch (e: Throwable) {
            addSuppressedException(e)
        } finally {
            super.tearDown()
        }
    }

    /** A project (`.git`) holding a docs tree (`kit.json`) with [pages] in it. */
    protected fun tree(vararg pages: Pair<String, String>): Map<String, VirtualFile> {
        fixture.tempDirFixture.findOrCreateDir("proj/.git")
        fixture.tempDirFixture.createFile("proj/docs/kit.json", """{"name": "t"}""")
        return pages.associate { (name, text) -> name to fixture.tempDirFixture.createFile("proj/docs/$name", text) }
    }
}
