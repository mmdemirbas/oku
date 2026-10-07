package io.github.mmdemirbas.oku

import com.intellij.openapi.vfs.VirtualFile
import com.intellij.testFramework.LightProjectDescriptor
import com.intellij.testFramework.UsefulTestCase
import com.intellij.testFramework.fixtures.CodeInsightTestFixture
import com.intellij.testFramework.fixtures.IdeaTestFixtureFactory
import com.intellij.testFramework.fixtures.impl.TempDirTestFixtureImpl

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
