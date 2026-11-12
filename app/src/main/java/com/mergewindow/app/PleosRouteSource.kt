package com.mergewindow.app

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import ai.pleos.playground.navi.constants.*
import ai.pleos.playground.navi.data.*
import ai.pleos.playground.navi.helper.NaviHelper
import ai.pleos.playground.navi.helper.listener.NaviHelperEventListener

/** Only this adapter creates live route state. No fake route events or private SDK APIs. */
class PleosRouteSource(context: Context, private val changed: (RouteSnapshot, List<String>) -> Unit) {
    private val helper = NaviHelper(context.applicationContext)
    private val handler = Handler(Looper.getMainLooper())
    private var closed = false
    private var registered = false
    private var snapshot = RouteSnapshot()
    private val events = ArrayDeque<String>()
    private val origin = SystemClock.elapsedRealtime()

    private fun receive(name: String, transform: (RouteSnapshot) -> RouteSnapshot = { it }) {
        handler.post {
            if (closed) return@post
            snapshot = transform(snapshot).copy(receivedEvents = snapshot.receivedEvents + 1, lastEvent = name)
            events.addFirst("+${(SystemClock.elapsedRealtime() - origin) / 1000}s  $name")
            while (events.size > 7) events.removeLast()
            Log.i("MergeWindow", "SDK $name active=${snapshot.active} mode=${snapshot.mode}")
            changed(snapshot, events.toList())
        }
    }

    private val listener = object : NaviHelperEventListener {
        override fun onRouteStarted(routeStartInfo: RouteStartInfo) {
            receive("onRouteStarted") { it.copy(active = false, tbtAt = -1, turnMeters = null, mode = "경로 계산 중") }
        }
        override fun onRoutingCompleted() { receive("onRoutingCompleted"); refresh() }
        override fun onReRouteEnded() { receive("onReRouteEnded"); refresh() }
        override fun onDestinationChanged() {
            receive("onDestinationChanged") { it.copy(active = false, tbtAt = -1, turnMeters = null, destination = "목적지 갱신 중") }
            refresh()
        }
        override fun onRouteCancelled() = ended("onRouteCancelled")
        override fun onRouteEnded() = ended("onRouteEnded")
        override fun onDestinationArrived(destinationArrivedInfo: DestinationArrivedInfo) = ended("onDestinationArrived")
        override fun onRouteStateInfo(routeStateInfo: RouteStateInfo) {
            val active = routeStateInfo.naviMode == NaviMode.ROUTE_GUIDING || routeStateInfo.naviMode == NaviMode.SIMULATION_GUIDING
            receive("onRouteStateInfo") {
                it.copy(active = active, mode = routeStateInfo.naviMode.name, stateAt = SystemClock.elapsedRealtime(),
                    tbtAt = if (active) it.tbtAt else -1, turnMeters = if (active) it.turnMeters else null)
            }
        }
        override fun onNavigationStatus(navigationStatus: NavigationStatus) {
            receive("onNavigationStatus:${navigationStatus.name}") {
                it.copy(active = navigationStatus == NavigationStatus.ROUTE_DRIVE,
                    stateAt = SystemClock.elapsedRealtime(), mode = navigationStatus.name,
                    tbtAt = if (navigationStatus == NavigationStatus.ROUTE_DRIVE) it.tbtAt else -1)
            }
        }
        override fun onDestinationInfo(destinationInfo: DestinationInfo) {
            receive("onDestinationInfo") { it.copy(destination = destinationInfo.name.ifBlank { "이름 없는 목적지" }) }
        }
        override fun onTBTInfo(tbtInfo: List<TBTInfo>) {
            // Use the next instruction in the SDK's ordered list, not a later right turn.
            val next = tbtInfo.firstOrNull()
            receive("onTBTInfo(${tbtInfo.size})") {
                it.copy(rightTurn = next?.type == TurnType.TURN_RIGHT || next?.type == TurnType.TURN_SHARP_R,
                    turnMeters = next?.distance, tbtAt = if (next == null) -1 else SystemClock.elapsedRealtime(),
                    tbtDescription = next?.let { t -> "${t.type.name} · ${t.distance.toInt()} m · ${t.description}" } ?: "다음 회전 없음")
            }
        }
        override fun onError(errorCode: NaviErrorCode) {
            receive("onError:${errorCode.name}") { it.copy(active = false, tbtAt = -1, turnMeters = null, mode = "경로 요청 오류") }
        }
    }

    private fun ended(name: String) = receive(name) {
        it.copy(active = false, stateAt = SystemClock.elapsedRealtime(), tbtAt = -1, turnMeters = null,
            destination = "목적지 없음", mode = "경로 종료")
    }

    private val poll = object : Runnable {
        override fun run() {
            if (closed) return
            refresh()
            handler.postDelayed(this, 3000)
        }
    }

    fun start() {
        try {
            helper.initialize(onConnected = {
                handler.post {
                    if (closed) return@post
                    try {
                        helper.addListener(listener)
                        registered = true
                        receive("NaviHelper connected") { it.copy(connected = true) }
                        handler.post(poll)
                    } catch (e: Exception) { failed(e) }
                }
            }, onFailed = { failed(it) })
        } catch (e: Exception) { failed(e) }
    }

    fun refresh() {
        handler.post {
            if (closed || !registered) return@post
            try {
                helper.getRouteStateInfo()
                helper.getDestinationInfo()
                helper.getTBTInfo()
            } catch (e: Exception) { failed(e) }
        }
    }

    /** Public example destination from Pleos documentation. Only invoked by a user/test action. */
    fun requestExampleRoute() {
        if (closed || !registered) return
        try {
            helper.requestRoute(RouteInfo(latitude = 37.48544722, longitude = 127.03636666,
                displayLongitude = null, displayLatitude = null, poiName = "42dot",
                poiId = "36khp37hh8gqcm5nqhe5", poiSubId = "0", address = "서울시 강남구 남부순환로 2621"))
            // A successful request is not a successful route. Wait for SDK callbacks.
            Log.i("MergeWindow", "REQUEST example route; waiting for SDK callbacks")
        } catch (e: Exception) { failed(e) }
    }

    fun cancelRoute() {
        if (closed || !registered) return
        try { helper.cancelRoute() } catch (e: Exception) { failed(e) }
    }

    private fun failed(e: Throwable) {
        receive("연결 오류: ${e.javaClass.simpleName}") { it.copy(connected = false, active = false, stateAt = -1, tbtAt = -1) }
        Log.w("MergeWindow", "NaviHelper failure: ${e.javaClass.simpleName}")
    }

    fun close() {
        closed = true
        handler.removeCallbacksAndMessages(null)
        try { if (registered) helper.removeListener(listener) } catch (_: Exception) { }
        try { helper.release() } catch (_: Exception) { }
        registered = false
    }
}
