package com.mergewindow.app

import android.os.SystemClock
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.atomic.AtomicReference
import java.util.concurrent.atomic.AtomicBoolean

/** Runs against the installed, real Pleos service; no fake SDK transport. */
@RunWith(AndroidJUnit4::class)
class PleosIntegrationTest {
    @Test fun liveRouteEventsDriveAllScenarios() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val latest = AtomicReference(RouteSnapshot())
        val allowed = AtomicReference<Boolean?>(null)
        val cancelledEvent = AtomicBoolean(false)
        lateinit var source: PleosRouteSource
        lateinit var gate: DrivingGate
        instrumentation.runOnMainSync {
            gate = DrivingGate(instrumentation.targetContext) { allowed.set(it) }
            source = PleosRouteSource(instrumentation.targetContext) { route, history ->
                latest.set(route)
                if (history.any { it.endsWith("onRouteCancelled") }) cancelledEvent.set(true)
            }
            source.start()
        }
        fun awaitState(timeout: Long, predicate: (RouteSnapshot) -> Boolean): Boolean {
            val deadline = SystemClock.elapsedRealtime()+timeout
            while (SystemClock.elapsedRealtime()<deadline) {
                if (predicate(latest.get())) return true
                Thread.sleep(100)
            }
            return false
        }
        try {
            assertTrue("Real NaviHelper must connect and deliver route state", awaitState(20000) { it.connected && it.stateAt >= 0 })
            // A previous run may have left a route active. Establish a real inactive
            // state first so this request cannot pass using that old route.
            if (latest.get().active) {
                instrumentation.runOnMainSync { source.cancelRoute() }
                assertTrue("Reset previous route after cancellation event", awaitState(10000) { cancelledEvent.get() && !it.active })
            }
            instrumentation.runOnMainSync { source.requestExampleRoute() }
            val activated=awaitState(45000) { it.active }
            assertTrue("Pleos route activation: mode=${latest.get().mode}, event=${latest.get().lastEvent}",activated)
            assertTrue("Real TBT callback required", awaitState(10000) { it.tbtAt >= 0 })
            assertEquals("Stationary emulator must permit the demo UI", true, allowed.get())
            val now = SystemClock.elapsedRealtime()
            val r=latest.get()
            for ((s,expected) in listOf(Scenario.CLEAR to AdviceState.NORMAL,Scenario.CONGESTED to AdviceState.PREPARE,Scenario.UNCERTAIN to AdviceState.CAUTION,Scenario.STALE to AdviceState.EXPIRED,Scenario.MISSED to AdviceState.ALTERNATIVE)) {
                val a=GuidanceEngine.evaluate(r,s,true,if(s==Scenario.STALE) now-13000 else now,now,true)
                assertEquals("Live route + ${s.name}",expected,a.state)
            }
            cancelledEvent.set(false)
            instrumentation.runOnMainSync { source.cancelRoute() }
            assertTrue("Actual cancellation must clear route", awaitState(10000) { cancelledEvent.get() && !it.active })
            val cancelled = GuidanceEngine.evaluate(latest.get(),Scenario.CONGESTED,true,now,SystemClock.elapsedRealtime(),true)
            assertEquals(AdviceState.WAITING,cancelled.state)
            assertNull(cancelled.lower)
        } finally { instrumentation.runOnMainSync { source.close(); gate.close() } }
    }
}
