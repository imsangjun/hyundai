package com.mergewindow.app

/** Pure, deterministic demo logic. Queue bounds are fixtures, NOT calibrated quantiles. */
enum class AdviceState { WAITING, NORMAL, PREPARE, CAUTION, EXPIRED, ALTERNATIVE, RESTRICTED }
enum class Scenario(val label: String, val low: Int?, val high: Int?, val virtualDistance: Int, val risk: Boolean) {
    CLEAR("원활", 60, 120, 650, false),
    CONGESTED("혼잡", 430, 520, 650, true),
    UNCERTAIN("관측 부족", null, null, 650, true),
    STALE("데이터 만료", 430, 520, 650, true),
    MISSED("진입 기회 상실", 430, 520, 350, true)
}

data class RouteSnapshot(
    val connected: Boolean = false,
    val active: Boolean = false,
    val stateAt: Long = -1,
    val destination: String = "목적지 미수신",
    val mode: String = "미수신",
    val rightTurn: Boolean = false,
    val turnMeters: Double? = null,
    val tbtAt: Long = -1,
    val tbtDescription: String = "회전 정보 미수신",
    val receivedEvents: Int = 0,
    val lastEvent: String = "연결 대기",
    val latitude: Double? = null,
    val longitude: Double? = null,
    val heading: Double = 0.0,
    val locationAt: Long = -1,
    val destinationLatitude: Double? = null,
    val destinationLongitude: Double? = null,
    val turnType: String = "",
    val turnLabel: String = ""
)
data class Advice(val state: AdviceState, val title: String, val detail: String,
    val distance: Int? = null, val lower: Int? = null, val upper: Int? = null, val prepareAt: Int? = null)

object GuidanceEngine {
    const val ROUTE_TTL_MS = 15_000L
    const val OBSERVATION_TTL_MS = 12_000L
    const val PREPARATION_MARGIN_METERS = 150
    fun fresh(timestamp: Long, now: Long, ttl: Long) = timestamp >= 0 && now >= timestamp && now - timestamp <= ttl

    fun evaluate(route: RouteSnapshot, scenario: Scenario, virtualTurn: Boolean,
        observationAt: Long, now: Long, parked: Boolean): Advice {
        if (!parked) return Advice(AdviceState.RESTRICTED, "정차 후 시연하세요", "주행 중이거나 차량 제한 상태를 확인할 수 없어 시연 조작을 잠갔습니다.")
        if (!route.connected) return Advice(AdviceState.WAITING, "Pleos 연결 대기", "NaviHelper 연결 후 실제 경로 이벤트를 확인합니다.")
        if (!fresh(route.stateAt, now, ROUTE_TTL_MS)) return Advice(AdviceState.EXPIRED, "경로 상태를 확인 중입니다", "오래된 경로 정보로 준비 안내를 계속하지 않습니다.")
        if (!route.active) return Advice(AdviceState.WAITING, "경로를 먼저 설정하세요", "Pleos 내비에서 안내를 시작하거나 아래 테스트 목적지를 요청하세요.")
        val distance = if (virtualTurn) scenario.virtualDistance else {
            if (!fresh(route.tbtAt, now, ROUTE_TTL_MS)) return Advice(AdviceState.WAITING, "새 회전 정보를 기다립니다", "실제 TBT 이벤트가 도착해야 해당 회전에 혼잡 시나리오를 적용합니다.")
            if (!route.rightTurn) return Advice(AdviceState.NORMAL, "다음 안내는 우회전이 아닙니다", "다른 회전에 우회전 대기열 시나리오를 적용하지 않습니다.")
            val d = route.turnMeters
            if (d == null || !d.isFinite() || d < 0 || d > 100_000) return Advice(AdviceState.WAITING, "회전 거리를 확인 중입니다", "유효한 거리 정보가 필요합니다.")
            d.toInt()
        }
        if (!fresh(observationAt, now, OBSERVATION_TTL_MS)) return Advice(AdviceState.EXPIRED, "혼잡 정보가 만료되었습니다", "새 관측을 기다립니다. 대기열 위치와 준비 거리는 표시하지 않습니다.", distance)
        val lower = scenario.low
        val upper = scenario.high
        if (lower == null || upper == null) return Advice(AdviceState.CAUTION, "우회전 차로 혼잡 가능성", "관측이 부족합니다. 정확한 대기열 후미는 알 수 없습니다.", distance)
        val prepare = upper + PREPARATION_MARGIN_METERS
        if (scenario.risk && distance <= upper) return Advice(AdviceState.ALTERNATIVE, "무리한 차선 변경을 피하세요", "가상 대기열 후미 구간에 도달했습니다. 기존 내비에서 다음 경로를 확인하세요.", distance, lower, upper, prepare)
        if (scenario.risk && distance <= prepare) return Advice(AdviceState.PREPARE, "우측 차로를 미리 준비하세요", "주변 차량과 차선을 직접 확인하세요. 이 표시는 차선 변경 허가가 아닙니다.", distance, lower, upper, prepare)
        return Advice(AdviceState.NORMAL, "아직 준비 구간 전입니다", "혼잡 상황을 확인하고 있습니다. 지금 차선을 바꿀 필요를 뜻하지 않습니다.", distance, lower, upper, prepare)
    }
}
