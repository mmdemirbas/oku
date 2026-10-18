package io.github.mmdemirbas.oku

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.service
import java.nio.file.Path
import java.util.concurrent.TimeUnit
import kotlin.io.path.Path
import kotlin.io.path.exists
import kotlin.io.path.readLines
import kotlin.io.path.setPosixFilePermissions
import kotlin.io.path.writeText
import kotlin.system.measureTimeMillis

/**
 * The service against an oku that misbehaves on purpose: a small Python
 * program that greets as oku does, writes every request it reads to a log,
 * and then answers each one the way a test says — or does not.
 */
class OkuPreviewServiceTest : OkuFixtureTestCase() {

    /** The checkout's oku the tests run, which `-Doku.executable` names. */
    private val checkout: String = System.getProperty("oku.executable")

    private val service get() = service<OkuPreviewService>()

    private val dir: Path get() = Path(fixture.tempDirFixture.tempDirPath)

    private val requests: Path get() = dir.resolve("fake-requests.log")

    private val page: Path get() = dir.resolve("a.md")

    override fun tearDown() {
        try {
            System.setProperty("oku.executable", checkout)
            service.restart()
        } catch (e: Throwable) {
            addSuppressedException(e)
        } finally {
            super.tearDown()
        }
    }

    /**
     * An oku that greets, logs each request, then runs [body] with the request
     * as `req` (a dict) and its line as `raw`. Every later request starts it.
     */
    private fun fakeOku(body: String) {
        val python = Path(checkout).resolveSibling("python")
        val script = dir.resolve("fake-oku")
        script.writeText(
            """
            |#!$python
            |import json, sys, time
            |print(json.dumps({"protocol": ${OkuPreviewService.PROTOCOL}, "oku": "fake", "kit": "fake"}), flush=True)
            |for raw in sys.stdin:
            |    req = json.loads(raw)
            |    with open(${pyString(requests.toString())}, "a") as log:
            |        log.write(raw)
            |${body.trimIndent().prependIndent("    ")}
            |
            """.trimMargin(),
        )
        script.setPosixFilePermissions(java.nio.file.attribute.PosixFilePermissions.fromString("rwx------"))
        System.setProperty("oku.executable", script.toString())
        service.restart()
    }

    private fun pyString(s: String) = "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"

    /** Wait until the fake has read [count] requests: they are in flight, not still being written. */
    private fun awaitRequests(count: Int) {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(10)
        while (!(requests.exists() && requests.readLines().size >= count)) {
            assertTrue("the fake oku read fewer than $count requests", System.nanoTime() < deadline)
            Thread.sleep(20)
        }
    }

    fun `test a restart does not wait for a request oku never answers`() {
        // IV.1: close() takes the lock ask() holds while it waits for a reply,
        // so restart() — which the settings' Apply runs on the EDT — waited out
        // the request's whole 30 s deadline, the IDE frozen for all of it.
        fakeOku("time.sleep(600)")
        val pending = ApplicationManager.getApplication().executeOnPooledThread<Result<List<Issue>>> { service.check(page, "x") }
        awaitRequests(1)
        val took = measureTimeMillis { service.restart() }
        assertTrue("restart took $took ms behind a request nobody answers", took < 2_000)
        assertTrue(pending.get(5, TimeUnit.SECONDS).isFailure)
    }
}
