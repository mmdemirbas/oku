package io.github.mmdemirbas.oku

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.service
import com.intellij.openapi.progress.EmptyProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import java.nio.file.Path
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException
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

    private val clock = OkuRegistryCache.clock

    override fun tearDown() {
        try {
            OkuRegistryCache.clock = clock
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

    fun `test an oku that stops says it stopped, and what it said`() {
        // VI.2: the end of oku's output reads the same as a timeout, so an
        // oku that exited at once was reported as one that "did not answer
        // within 30s" — after waiting no time at all.
        fakeOku(
            """
            sys.stderr.write("boom\n")
            sys.stderr.flush()
            sys.exit(3)
            """,
        )
        val message = service.check(page, "x").exceptionOrNull()?.message.orEmpty()
        assertTrue(message, "stopped" in message && "boom" in message)
        assertFalse(message, "within" in message)
    }

    fun `test a reply is the one its request asked for, whatever else oku prints`() {
        // IX.1: every request carries an id and oku echoes it, but the reply
        // read was simply the next line. One stray line on oku's stdout
        // failed that request as "not JSON" and left its real reply in the
        // queue, so every later request read the answer to the one before.
        fakeOku(
            """
            print("stray output before the reply to " + str(req["id"]), flush=True)
            issue = {"severity": "info", "code": req["text"], "where": "w", "message": "m", "line": None}
            print(json.dumps({"id": req["id"], "issues": [issue]}), flush=True)
            """,
        )
        assertEquals("first", service.check(page, "first").getOrThrow().single().code)
        assertEquals("second", service.check(page, "second").getOrThrow().single().code)
    }

    fun `test a completion that is cancelled stops waiting for oku`() {
        // IV.5: completion asks oku for the registry inside its read action,
        // and the wait never checked for cancellation: a completion the
        // author had typed past kept the read lock — and every edit queued
        // behind it — until oku answered or 30 s ran out.
        fakeOku("time.sleep(600)")
        val indicator = EmptyProgressIndicator()
        val call = ApplicationManager.getApplication().executeOnPooledThread<Registry?> {
            ProgressManager.getInstance().runProcess<Registry?>({ OkuRegistryCache.of(page, "x") }, indicator)
        }
        awaitRequests(1)
        indicator.cancel()
        val ended = runCatching { call.get(2, TimeUnit.SECONDS) }.exceptionOrNull()
        assertFalse("still waiting for oku 2 s after the cancel", ended is TimeoutException)
    }

    fun `test a fix that is cancelled stops waiting for oku`() {
        // IV.5, the fix's half: its progress offered Cancel, and the wait
        // never looked at it, so Cancel did nothing until oku answered.
        fakeOku("time.sleep(600)")
        val indicator = EmptyProgressIndicator()
        val call = ApplicationManager.getApplication().executeOnPooledThread<Result<Fixed>> {
            ProgressManager.getInstance().runProcess<Result<Fixed>>({ OkuChipFix.ask(page, "x") }, indicator)
        }
        awaitRequests(1)
        indicator.cancel()
        val ended = runCatching { call.get(2, TimeUnit.SECONDS) }.exceptionOrNull()
        assertFalse("still waiting for oku 2 s after the cancel", ended is TimeoutException)
    }

    fun `test a completion does not wait behind a check`() {
        // Measured on an 84-page tree: a check takes 525 ms and the registry
        // 247 ms, and one session answers one request at a time, so a
        // completion asked during a check waited 789 ms for its list.
        fakeOku(
            """
            if req.get("check"):
                time.sleep(600)
            print(json.dumps({"id": req["id"], "glossary": [], "extrefs": [], "pages": []}), flush=True)
            """,
        )
        ApplicationManager.getApplication().executeOnPooledThread { service.check(page, "x") }
        awaitRequests(1)
        val asked = ApplicationManager.getApplication().executeOnPooledThread<Result<Registry>> { service.registry(page, "x") }
        val answer = runCatching { asked.get(2, TimeUnit.SECONDS) }
        assertTrue("the registry was still queued behind the check 2 s later", answer.getOrNull()?.isSuccess == true)
    }

    fun `test a clock set back does not keep a registry answer fresh`() {
        // XII.1: freshness was a difference of wall-clock readings, so a clock
        // set back made every held answer's age negative: fresh for as long as
        // the clock had been set back, and never pruned either.
        fakeOku(
            """
            n = globals().get("n", 0) + 1
            entry = {"term": str(n), "domain": "d", "def": ""}
            print(json.dumps({"id": req["id"], "glossary": [entry], "extrefs": [], "pages": []}), flush=True)
            """,
        )
        var now = 1_000_000_000L
        OkuRegistryCache.clock = { now }
        assertEquals("1", OkuRegistryCache.of(page, "x")?.glossary?.single()?.term)
        now -= 3_600_000 // the clock is set back an hour
        now += OkuRegistryCache.FRESH_MS + 1 // and the answer's five seconds pass
        assertEquals("the answer from before the clock moved was still fresh", "2", OkuRegistryCache.of(page, "x")?.glossary?.single()?.term)
    }

    fun `test the registry cache holds only what is still fresh`() {
        // V.5: an answer is used for 5 s and kept forever, one per page ever
        // completed in, each holding the glossary of every domain its tree
        // activates: a map that only grows for the life of the IDE.
        fakeOku("""print(json.dumps({"id": req["id"], "glossary": [], "extrefs": [], "pages": []}), flush=True)""")
        repeat(100) { assertNotNull(OkuRegistryCache.of(dir.resolve("p$it.md"), "x")) }
        Thread.sleep(OkuRegistryCache.FRESH_MS + 200)
        assertNotNull(OkuRegistryCache.of(page, "x"))
        assertEquals(1, OkuRegistryCache.held.size)
    }
}
