package com.mergewindow.app

import android.app.Activity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.View
import android.widget.*

class MainActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private var source: PleosRouteSource? = null
    private var gate: DrivingGate? = null
    internal var route = RouteSnapshot(); private set
    internal var scenario = Scenario.CLEAR; private set
    internal var advice = Advice(AdviceState.WAITING, "", ""); private set
    private var parked = false
    private var virtualTurn = true
    private var observationAt = -1L
    private var events = emptyList<String>()
    private lateinit var headline: TextView
    private lateinit var detail: TextView
    private lateinit var metrics: TextView
    private lateinit var live: TextView
    private lateinit var log: TextView
    private lateinit var provenance: TextView
    private lateinit var lane: LaneView
    private lateinit var request: Button
    private lateinit var actual: Switch
    private val buttons = mutableMapOf<Scenario, Button>()
    private val mint = Color.rgb(109,228,196)
    private val muted = Color.rgb(159,179,193)
    private fun dp(n: Int) = (n * resources.displayMetrics.density).toInt()
    private fun label(value: String, size: Float, color: Int = Color.WHITE) = TextView(this).apply {
        text = value; textSize = size; setTextColor(color); setPadding(0, dp(5), 0, dp(5))
    }
    private fun column() = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
    private fun surface(view: View) {
        view.background = GradientDrawable().apply { setColor(Color.rgb(21,38,48)); cornerRadius = dp(18).toFloat() }
        view.setPadding(dp(22),dp(16),dp(22),dp(16))
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        scenario = savedInstanceState?.getString("scenario")?.let { runCatching { Scenario.valueOf(it) }.getOrNull() } ?: Scenario.CLEAR
        virtualTurn = savedInstanceState?.getBoolean("virtualTurn", true) ?: true
        val root = column().apply { setPadding(dp(28),dp(20),dp(28),dp(24)) }
        val scroll = ScrollView(this).apply { addView(root) }
        setContentView(scroll)
        root.addView(label("MERGEWINDOW   /   준비할 시간을 더하다", 28f, mint).apply { setTypeface(null,Typeface.BOLD) })
        root.addView(label("정차 시연 · 실제 Pleos 경로 + 가상 우회전 혼잡", 17f, muted))
        val row = LinearLayout(this).apply { orientation = if (resources.configuration.screenWidthDp >= 900) LinearLayout.HORIZONTAL else LinearLayout.VERTICAL }
        lane = LaneView(this).apply { contentDescription = "실제 지도나 주변 차량을 나타내지 않는 가상 차선 개념도" }
        val panel = column(); surface(panel)
        panel.addView(label("PREPARATION ADVISORY", 14f, mint))
        headline = label("Pleos 연결 대기",30f).apply { setTypeface(null,Typeface.BOLD); id = View.generateViewId(); tag = "adviceTitle" }; panel.addView(headline)
        detail = label("",18f,muted); panel.addView(detail)
        metrics = label("",20f,mint); panel.addView(metrics)
        provenance = label("",15f,muted); panel.addView(provenance)
        if (row.orientation == LinearLayout.HORIZONTAL) {
            row.addView(lane,LinearLayout.LayoutParams(0,dp(310),0.85f))
            row.addView(panel,LinearLayout.LayoutParams(0,LinearLayout.LayoutParams.WRAP_CONTENT,1.15f))
        } else { row.addView(lane,LinearLayout.LayoutParams(-1,dp(250))); row.addView(panel) }
        root.addView(row)
        root.addView(label("가상 혼잡 시나리오",18f))
        val scenarios = LinearLayout(this)
        Scenario.entries.forEach { s ->
            val b = Button(this).apply { text = s.label; isAllCaps = false; textSize = 15f; setOnClickListener { selectScenario(s) } }
            buttons[s] = b; scenarios.addView(b,LinearLayout.LayoutParams(0,dp(56),1f))
        }
        root.addView(scenarios)
        actual = Switch(this).apply {
            text = "실제 다음 회전 사용 (끄면 가상 650 m 우회전)"; textSize = 17f; setTextColor(Color.WHITE)
            isChecked = !virtualTurn
            setPadding(0,dp(10),0,dp(10))
            setOnCheckedChangeListener { _, checked -> virtualTurn = !checked; render() }
        }; root.addView(actual)
        val controls = LinearLayout(this)
        request = Button(this).apply { text = "테스트 목적지 · 42dot"; isAllCaps = false; setOnClickListener { if (parked) source?.requestExampleRoute() } }
        controls.addView(request)
        controls.addView(Button(this).apply { text = "Pleos 재연결"; setOnClickListener { connect() } })
        root.addView(controls)
        live = label("",16f,mint); root.addView(live)
        log = label("",13f,muted).apply { typeface = Typeface.MONOSPACE }; root.addView(log)
        root.addView(label("가상 대기열 범위는 시연용 설정값입니다. 실제 차로별 관측·차선 변경 판단·보정된 확률 예측을 제공하지 않습니다.",14f,muted))
    }
    override fun onStart() {
        super.onStart()
        gate = DrivingGate(this) { allowed -> runOnUiThread { parked = allowed; render() } }
        connect(); handler.post(tick)
    }
    private fun connect() {
        source?.close(); route = RouteSnapshot(); events = emptyList()
        source = PleosRouteSource(this) { next, history -> route = next; events = history; render() }.also { it.start() }
        render()
    }
    internal fun selectScenario(value: Scenario) {
        scenario = value
        observationAt = if (value == Scenario.STALE) SystemClock.elapsedRealtime() - GuidanceEngine.OBSERVATION_TTL_MS - 1 else SystemClock.elapsedRealtime()
        render()
    }
    private val tick = object : Runnable {
        override fun run() {
            if (scenario != Scenario.STALE) observationAt = SystemClock.elapsedRealtime()
            render(); handler.postDelayed(this, 1000)
        }
    }
    private fun render() {
        if (!::headline.isInitialized) return
        val now = SystemClock.elapsedRealtime()
        advice = GuidanceEngine.evaluate(route,scenario,virtualTurn,observationAt,now,parked)
        headline.text = advice.title
        headline.setTextColor(if (advice.state in listOf(AdviceState.CAUTION,AdviceState.ALTERNATIVE,AdviceState.EXPIRED)) Color.rgb(243,184,117) else Color.WHITE)
        detail.text = advice.detail
        metrics.text = listOfNotNull(advice.distance?.let { "우회전까지 ${it} m" },advice.lower?.let { "가상 대기열 ${it}–${advice.upper} m" },advice.prepareAt?.let { "시연 준비 기준 ${it} m" }).joinToString("   /   ")
        provenance.text = if (virtualTurn) "경로 활성 상태: Pleos  ·  우회전 거리·혼잡: 가상\n혼잡 스트림: ${if (scenario == Scenario.STALE) "중단 / 만료" else "시연 값 갱신 중"}" else "다음 회전·거리: Pleos TBT  ·  혼잡: 가상\n${route.tbtDescription}"
        lane.advice = advice
        live.text = "PLEOS ${if (route.connected) "연결됨" else "연결 대기"}  ·  ${route.mode}  ·  ${route.destination}\n수신 ${route.receivedEvents}건  ·  ${if (parked) "정차 시연 가능" else "차량 제한 확인 / 조작 잠금"}"
        log.text = events.joinToString("\n")
        buttons.forEach { (s,b) -> b.isEnabled = parked; b.alpha = if (s == scenario) 1f else 0.65f; b.setTextColor(if (s == scenario) mint else Color.WHITE) }
        actual.isEnabled = parked
        request.isEnabled = parked && route.connected
    }
    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString("scenario", scenario.name); outState.putBoolean("virtualTurn",virtualTurn); super.onSaveInstanceState(outState)
    }
    override fun onStop() {
        handler.removeCallbacksAndMessages(null); source?.close(); source = null; gate?.close(); gate = null
        parked = false; route = RouteSnapshot(); super.onStop()
    }
}
