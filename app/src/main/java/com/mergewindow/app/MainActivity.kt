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
    private var scenario = Scenario.CLEAR
    private var virtualTurn = true
    private var offlineDemo = true
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
                    "scenario" -> runCatching { Scenario.valueOf(value) }.getOrNull()?.let {
                        scenario = it
                        observationAt = if (it == Scenario.STALE) -1 else SystemClock.elapsedRealtime()
                    }
                    "actual" -> virtualTurn = value != "true"
                    "offline" -> { offlineDemo = value == "true"; connect() }
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
        val advice = GuidanceEngine.evaluate(displayRoute,scenario,useVirtual,observationAt,now,parked)
        val json = JSONObject().apply {
            put("connected",route.connected); put("active",active); put("parked",parked)
            put("offline",offlineDemo); put("virtual",useVirtual); put("scenario",scenario.name)
            put("destination",if(active) displayRoute.destination else "목적지를 설정해 주세요")
            put("turnType",if(active && useVirtual) "TURN_RIGHT" else if(tbtFresh) route.turnType else "")
            put("turnMeters",if(active && useVirtual) scenario.virtualDistance else if(tbtFresh && route.turnMeters?.isFinite() == true && route.turnMeters!! >= 0) route.turnMeters else JSONObject.NULL)
            put("turnLabel",if(active && useVirtual) "한빛로 우회전 · 가상 구간" else if(tbtFresh) route.turnLabel else "")
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
    }
    override fun onStop() {
        started = false; handler.removeCallbacksAndMessages(null)
        source?.close(); source = null; gate?.close(); gate = null; parked = false; route = RouteSnapshot()
        web.evaluateJavascript("window.resetNavigation && window.resetNavigation()",null)
        web.onPause(); super.onStop()
    }
    override fun onDestroy() { web.removeJavascriptInterface("MergeWindow"); web.destroy(); super.onDestroy() }
}
