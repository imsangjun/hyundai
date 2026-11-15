package com.mergewindow.app

import android.os.Bundle
import android.os.SystemClock
import android.util.Log
import ai.pleos.playground.navi.constants.NaviErrorCode
import ai.pleos.playground.navi.constants.TrafficCongestionType
import ai.pleos.playground.navi.data.RouteStateInfo
import ai.pleos.playground.navi.data.TripInfo
import ai.pleos.playground.navi.data.TripRequest
import ai.pleos.playground.navi.helper.NaviHelper
import ai.pleos.playground.navi.helper.listener.NaviHelperEventListener
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

/** Explicit live diagnostic. Never substitutes a simulated TripInfo or logs coordinates. */
@RunWith(AndroidJUnit4::class)
class TripTrafficProbeTest {
    @Test fun requestTripReportsTrafficAvailability() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        val context=instrumentation.targetContext
        val started=SystemClock.elapsedRealtime()
        val initialized=CountDownLatch(1)
        val stateReceived=CountDownLatch(1)
        val connected=AtomicBoolean(false)
        val requestedAt=AtomicLong(-1)
        val ignoredCallbacks=AtomicInteger(0)
        val routeMode=AtomicReference("NOT_RECEIVED")
        val setupError=AtomicReference<String?>(null)
        val errors=CopyOnWriteArrayList<String>()
        val responses=CopyOnWriteArrayList<JSONObject>()
        var registered=false
        lateinit var helper: NaviHelper
        val listener=object : NaviHelperEventListener {
            override fun onRouteStateInfo(routeStateInfo: RouteStateInfo) {
                routeMode.set(routeStateInfo.naviMode.name)
                stateReceived.countDown()
            }
            override fun onError(errorCode: NaviErrorCode) {
                errors.add(errorCode.name)
                Log.i(TAG,"SDK_ERROR ${errorCode.name}")
            }
            override fun onTripInfo(tripInfo: TripInfo) {
                val sent=requestedAt.get()
                if(sent<0) { ignoredCallbacks.incrementAndGet(); return }
                val summary=tripInfo.summary
                val traffic=summary.trafficConditions
                val rows=JSONArray()
                traffic.forEach { segment -> rows.put(JSONObject().apply {
                    put("congestionType",segment.congestionType.name)
                    put("startRatioRaw",segment.startRatio)
                    put("endRatioRaw",segment.endRatio)
                }) }
                val response=JSONObject().apply {
                    put("afterRequestMs",SystemClock.elapsedRealtime()-sent)
                    put("distanceRaw",tripInfo.distance)
                    put("etaRaw",tripInfo.eta)
                    put("routePointCount",summary.routePoints.size)
                    put("trafficCount",traffic.size)
                    put("knownTrafficCount",traffic.count { it.congestionType!=TrafficCongestionType.UNKNOWN })
                    put("unknownTrafficCount",traffic.count { it.congestionType==TrafficCongestionType.UNKNOWN })
                    put("orderedRatioCount",traffic.count { it.startRatio>=0 && it.endRatio>=it.startRatio })
                    put("traffic",rows)
                }
                responses.add(response)
                Log.i(TAG,"TRIP_CALLBACK count=${traffic.size} known=${response.getInt("knownTrafficCount")}")
            }
        }
        val report=JSONObject().apply {
            put("sdk","NaviHelper 3.0.5 / navi-data 3.0.4")
            put("destinationFixture","42dot official example")
            put("coordinatesRecorded",false)
        }
        try {
            instrumentation.runOnMainSync {
                helper=NaviHelper(context)
                try {
                    helper.initialize(onConnected={
                        try {
                            helper.addListener(listener)
                            registered=true
                            connected.set(true)
                            helper.getRouteStateInfo()
                        } catch(e: Exception) { setupError.set(e.javaClass.simpleName) }
                        initialized.countDown()
                    },onFailed={ e -> setupError.set(e.javaClass.simpleName); initialized.countDown() })
                } catch(e: Exception) { setupError.set(e.javaClass.simpleName); initialized.countDown() }
            }
            initialized.await(20,TimeUnit.SECONDS)
            if(connected.get() && setupError.get()==null) {
                stateReceived.await(5,TimeUnit.SECONDS)
                report.put("routeModeBefore",routeMode.get())
                instrumentation.runOnMainSync {
                    requestedAt.set(SystemClock.elapsedRealtime())
                    try {
                        helper.requestTrip(TripRequest(latitude=37.48544722,longitude=127.03636666,
                            poiId="36khp37hh8gqcm5nqhe5",poiName="42dot",poiSubId="0"))
                        report.put("requestCallReturned",true)
                    } catch(e: Exception) { setupError.set(e.javaClass.simpleName) }
                }
                // Empty/UNKNOWN responses get the entire window in case a fuller update follows.
                val deadline=SystemClock.elapsedRealtime()+45_000
                while(SystemClock.elapsedRealtime()<deadline && setupError.get()==null) {
                    if(responses.any { it.optInt("knownTrafficCount")>0 })break
                    Thread.sleep(100)
                }
            }
        } finally {
            instrumentation.runOnMainSync {
                try { if(registered)helper.removeListener(listener) } catch(_: Exception) { }
                try { helper.release() } catch(_: Exception) { }
            }
            val outcome=when {
                !connected.get() -> "CONNECTION_FAILED"
                setupError.get()!=null -> "REQUEST_EXCEPTION"
                responses.any { it.optInt("knownTrafficCount")>0 } -> "TRAFFIC_DATA_RECEIVED"
                responses.any { it.optInt("trafficCount")>0 } -> "UNKNOWN_TRAFFIC_ONLY"
                responses.isNotEmpty() -> "TRIP_RECEIVED_EMPTY_TRAFFIC"
                errors.isNotEmpty() -> "SDK_ERROR_NO_TRIP"
                else -> "TIMEOUT_NO_TRIP"
            }
            report.put("outcome",outcome)
            report.put("connected",connected.get())
            report.put("routeStateReceived",stateReceived.count==0L)
            report.put("routeModeAfter",routeMode.get())
            report.put("requestIssued",requestedAt.get()>=0)
            report.put("tripCallbackCount",responses.size)
            report.put("ignoredPreRequestCallbacks",ignoredCallbacks.get())
            report.put("elapsedMs",SystemClock.elapsedRealtime()-started)
            report.put("exceptionType",setupError.get() ?: JSONObject.NULL)
            report.put("errors",JSONArray(errors))
            report.put("responses",JSONArray(responses))
            File(context.filesDir,"trip-traffic-probe.json").writeText(report.toString(2))
            instrumentation.sendStatus(0,Bundle().apply { putString("tripProbe",report.toString()) })
            Log.i(TAG,"TRIP_PROBE_RESULT $report")
        }
        // Passing means a real TripInfo arrived; the report still distinguishes empty/unknown traffic.
        assertTrue("No onTripInfo received: ${report.optString("outcome")}; errors=$errors",responses.isNotEmpty())
    }

    companion object { private const val TAG="MergeWindowTripProbe" }
}
