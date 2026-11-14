package com.mergewindow.app

import android.annotation.SuppressLint
import android.app.Activity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.webkit.*
import org.json.JSONObject
import org.json.JSONArray
import java.io.ByteArrayInputStream

/** Bundled offline map. Live Pleos route events are an explicit, separate mode. */
class MainActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private var source: PleosRouteSource? = null
    private var gate: DrivingGate? = null
    private var route = RouteSnapshot()
    private var v2xEnabled = false
    private var v2x = V2xSimulation()
    private var scenario = Scenario.CLEAR
    private var virtualTurn = true
    private var offlineDemo = true
    private var demoDirection = TurnDirection.RIGHT
    private var parked = false
    private var started = false
    private var ready = false
    private var observationAt = -1L
    private var events = emptyList<String>()
    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        scenario = savedInstanceState?.getString("scenario")?.let { runCatching { Scenario.valueOf(it) }.getOrNull() } ?: Scenario.CLEAR
        virtualTurn = savedInstanceState?.getBoolean("virtualTurn",true) ?: true
        offlineDemo = savedInstanceState?.getBoolean("offlineDemo",true) ?: true
        demoDirection = savedInstanceState?.getString("demoDirection")?.let { runCatching { TurnDirection.valueOf(it) }.getOrNull() } ?: TurnDirection.RIGHT
        web = WebView(this)
        web.setBackgroundColor(android.graphics.Color.rgb(232,237,232))
        web.settings.apply {
            javaScriptEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            blockNetworkLoads = true
        }
        web.addJavascriptInterface(Controls(), "MergeWindow")
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean = true
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                val uri = request.url
                if (uri.scheme == "https" && uri.host == "mergewindow.local") {
                    val path = uri.path.orEmpty().removePrefix("/")
                    if (path.isNotEmpty() && !path.contains("..") && path.matches(Regex("[a-zA-Z0-9_./-]+"))) {
                        try {
                            val mime = when(path.substringAfterLast('.')) { "html" -> "text/html"; "js" -> "application/javascript"; "css" -> "text/css"; "svg" -> "image/svg+xml"; "png" -> "image/png"; else -> "text/plain" }
                            return WebResourceResponse(mime,"UTF-8",assets.open(path))
                        } catch (_: Exception) { }
                    }
                }
                return WebResourceResponse("text/plain","UTF-8",403,"Blocked",emptyMap(),ByteArrayInputStream(ByteArray(0)))
            }
            override fun onPageFinished(view: WebView, url: String) { ready = true; render() }
        }
        setContentView(web)
        web.loadUrl("https://mergewindow.local/index.html")
    }

    /** No arbitrary URLs, scripts or commands accepted by the local UI bridge. */
    private inner class Controls {
        @JavascriptInterface fun action(name: String, value: String) {
            handler.post {
                if (!started || !parked) return@post
                when(name) {
                    "v2x" -> {
                        v2xEnabled = value == "true"
                        if (v2xEnabled) { offlineDemo = true; virtualTurn = true; scenario = Scenario.BOTH_BLOCKS; v2x = V2xSimulation(); connect() }
                    }
                    "v2xHops" -> value.toIntOrNull()?.takeIf { it in 1..4 }?.let { v2x.maxHops = it }
                    "v2xLoss" -> v2x.lossPercent = if (value == "true") 100 else 0
                    "v2xPause" -> v2x.paused = value == "true"
                    "v2xClear" -> { v2x.nextClear = value == "true"; scenario = if (v2x.nextClear) Scenario.NEXT_BLOCK_CLEAR else Scenario.BOTH_BLOCKS }

                    "scenario" -> runCatching { Scenario.valueOf(value) }.getOrNull()?.let {
                        v2xEnabled = false; scenario = it
                        observationAt = if (it == Scenario.STALE) -1 else SystemClock.elapsedRealtime()
                    }
                    "actual" -> { v2xEnabled = false; virtualTurn = value != "true"; if (!virtualTurn && scenario.twoBlocks) scenario = Scenario.CLEAR }
                    "direction" -> runCatching { TurnDirection.valueOf(value) }.getOrNull()?.let { demoDirection = it }
                    "offline" -> { v2xEnabled = false; offlineDemo = value == "true"; connect() }
                    "start" -> if (!offlineDemo) source?.requestExampleRoute()
                    "cancel" -> if (!offlineDemo) source?.cancelRoute()
                    "reconnect" -> connect()
                }
                render()
            }
        }
    }
    override fun onStart() {
        super.onStart(); started = true; web.onResume()
        gate = DrivingGate(this) { allowed -> runOnUiThread { parked = allowed; render() } }
        connect(); handler.post(tick)
    }
    private fun connect() {
        source?.close(); route = RouteSnapshot(); events = emptyList()
        source = if (offlineDemo) null else PleosRouteSource(this) { next, history -> route = next; events = history; render() }.also { it.start() }
        render()
    }
    private val tick = object : Runnable {
        override fun run() {
            if (!started) return
            if (v2xEnabled) { v2x.direction = demoDirection; v2x.tick(SystemClock.elapsedRealtime()) }
            if (scenario != Scenario.STALE) observationAt = SystemClock.elapsedRealtime()
            render(); handler.postDelayed(this,1000)
        }
    }
    private fun render() {
        if (!ready || !started) return
        val now = SystemClock.elapsedRealtime()
        // Explicit demo data never enters the real SDK adapter or its event history.
        val displayRoute = if (offlineDemo) RouteSnapshot(connected=true,active=true,stateAt=now,
            destination="시연 목적지",mode="OFFLINE_DEMO") else route
        val active = parked && displayRoute.connected && displayRoute.active && GuidanceEngine.fresh(displayRoute.stateAt,now,GuidanceEngine.ROUTE_TTL_MS)
        val tbtFresh = active && GuidanceEngine.fresh(route.tbtAt,now,GuidanceEngine.ROUTE_TTL_MS)
        val useVirtual = offlineDemo || virtualTurn
        val twoBlocks = scenario.twoBlocks && useVirtual
        val receivedQueue = if (v2xEnabled) v2x.estimate(1, now) else null
        val currentQueue = if (v2xEnabled) v2x.estimate(0, now) else null
        val blocks = if (twoBlocks) BlockTraffic.demo(observationAt).let {
            if (currentQueue != null) it.copy(currentLow=currentQueue.low,currentHigh=currentQueue.high,currentObservedAt=currentQueue.observedAt) else it
        } else null
        val advice = GuidanceEngine.evaluate(displayRoute,scenario,useVirtual,receivedQueue?.observedAt ?: observationAt,now,parked,demoDirection,blocks,receivedQueue)
        val json = JSONObject().apply {
            put("v2x",v2xEnabled); put("v2xStatus",if (v2xEnabled) v2x.status(now) else "")
            put("v2xHops",v2x.maxHops); put("v2xPause",v2x.paused); put("v2xLoss",v2x.lossPercent == 100); put("v2xClear",v2x.nextClear)
            put("connected",route.connected); put("active",active); put("parked",parked)
            put("offline",offlineDemo); put("virtual",useVirtual); put("scenario",scenario.name)
            put("demoDirection",demoDirection.name)
            put("twoBlocks",twoBlocks)
            put("blockLength",blocks?.blockLength ?: JSONObject.NULL)
            put("intersectionBuffer",blocks?.intersectionBuffer ?: JSONObject.NULL)
            put("preparationBlock",advice.preparationBlock?.name ?: JSONObject.NULL)
            put("currentLow",if (advice.preparationBlock != null) blocks?.currentLow else JSONObject.NULL)
            put("currentHigh",if (advice.preparationBlock != null) blocks?.currentHigh else JSONObject.NULL)
            put("destination",if(active) displayRoute.destination else "목적지를 설정해 주세요")
            put("turnType",if(active && useVirtual) "TURN_${demoDirection.name}" else if(tbtFresh) route.turnType else "")
            put("turnMeters",if(active && useVirtual) scenario.virtualDistance else if(tbtFresh && route.turnMeters?.isFinite() == true && route.turnMeters!! >= 0) route.turnMeters else JSONObject.NULL)
            put("turnLabel",if(active && useVirtual) "한빛로 ${demoDirection.label} · 가상 구간" else if(tbtFresh) route.turnLabel else "")
            put("state",advice.state.name); put("title",advice.title); put("detail",advice.detail)
            put("low",advice.lower ?: JSONObject.NULL); put("high",advice.upper ?: JSONObject.NULL)
            put("prepareAt",advice.prepareAt ?: JSONObject.NULL)
            put("events",JSONArray(events)); put("mode",displayRoute.mode); put("eventCount",route.receivedEvents)
        }
        web.evaluateJavascript("window.renderState && window.renderState($json)",null)
    }
    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString("scenario",scenario.name); outState.putBoolean("virtualTurn",virtualTurn)
        outState.putBoolean("offlineDemo",offlineDemo); super.onSaveInstanceState(outState)
        outState.putString("demoDirection",demoDirection.name)
    }
    override fun onStop() {
        started = false; handler.removeCallbacksAndMessages(null)
        source?.close(); source = null; gate?.close(); gate = null; parked = false; route = RouteSnapshot()
        web.evaluateJavascript("window.resetNavigation && window.resetNavigation()",null)
        web.onPause(); super.onStop()
    }
    override fun onDestroy() { web.removeJavascriptInterface("MergeWindow"); web.destroy(); super.onDestroy() }
}
