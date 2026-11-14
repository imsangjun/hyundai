package com.mergewindow.app

/** Pure, deterministic demo logic. Queue bounds are fixtures, NOT calibrated quantiles. */
enum class AdviceState { WAITING, NORMAL, PREPARE, CAUTION, EXPIRED, ALTERNATIVE, RESTRICTED }
enum class TurnDirection(val label: String, val lane: String) {
    RIGHT("우회전", "우측"), LEFT("좌회전", "좌측")
}
enum class Scenario(val label: String, val low: Int?, val high: Int?, val virtualDistance: Int, val risk: Boolean, val twoBlocks: Boolean = false) {
    CLEAR("원활", 60, 120, 650, false),
    CONGESTED("혼잡", 430, 520, 650, true),
    UNCERTAIN("관측 부족", null, null, 650, true),
    STALE("데이터 만료", 430, 520, 650, true),
    MISSED("진입 기회 상실", 430, 520, 350, true),
    BOTH_BLOCKS("이번·다음 블록 혼잡", 360, 450, 800, true, true),
    NEXT_BLOCK_CLEAR("이번 혼잡·다음 원활", 60, 120, 800, false, true)
}

enum class PreparationBlock { CURRENT, NEXT }

/** Explicit fictional geometry and lane assumptions, never inferred from a single TBT. */
data class BlockTraffic(
    val blockLength: Int,
    val intersectionBuffer: Int,
    val currentLow: Int?,
    val currentHigh: Int?,
    val currentObservedAt: Long,
    val throughLaneContinues: Boolean?,
    val currentChangeWindowKnown: Boolean?,
    val nextChangeWindowKnown: Boolean?
) {
    companion object {
        fun demo(now: Long) = BlockTraffic(500,50,100,180,now,true,true,true)
    }
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
    val distance: Int? = null, val lower: Int? = null, val upper: Int? = null, val prepareAt: Int? = null,
    val preparationBlock: PreparationBlock? = null)

object GuidanceEngine {
    const val ROUTE_TTL_MS = 15_000L
    const val OBSERVATION_TTL_MS = 12_000L
    const val PREPARATION_MARGIN_METERS = 150
    fun fresh(timestamp: Long, now: Long, ttl: Long) = timestamp >= 0 && now >= timestamp && now - timestamp <= ttl

    fun evaluate(route: RouteSnapshot, scenario: Scenario, virtualTurn: Boolean,
        observationAt: Long, now: Long, parked: Boolean, demoDirection: TurnDirection = TurnDirection.RIGHT,
        blocks: BlockTraffic? = null, receivedQueue: QueueEstimate? = null): Advice {
        if (!parked) return Advice(AdviceState.RESTRICTED, "정차 후 시연하세요", "주행 중이거나 차량 제한 상태를 확인할 수 없어 시연 조작을 잠갔습니다.")
        if (!route.connected) return Advice(AdviceState.WAITING, "Pleos 연결 대기", "NaviHelper 연결 후 실제 경로 이벤트를 확인합니다.")
        if (!fresh(route.stateAt, now, ROUTE_TTL_MS)) return Advice(AdviceState.EXPIRED, "경로 상태를 확인 중입니다", "오래된 경로 정보로 준비 안내를 계속하지 않습니다.")
        if (!route.active) return Advice(AdviceState.WAITING, "경로를 먼저 설정하세요", "Pleos 내비에서 안내를 시작하거나 아래 테스트 목적지를 요청하세요.")
        if (scenario.twoBlocks && !virtualTurn) return Advice(AdviceState.WAITING, "두 블록 경로 정보가 필요합니다", "실제 첫 TBT만으로 다음 블록의 차로 연결과 회전 위치를 추정하지 않습니다. 두 블록 비교는 가상 경로 시연에서 사용하세요.")
        val direction = if (virtualTurn) demoDirection else when (route.turnType) {
            "TURN_LEFT", "TURN_SHARP_L" -> TurnDirection.LEFT
            "TURN_RIGHT", "TURN_SHARP_R" -> TurnDirection.RIGHT
            "" -> if (route.rightTurn) TurnDirection.RIGHT else null
            else -> null
        }
        val distance = if (virtualTurn) scenario.virtualDistance else {
            if (!fresh(route.tbtAt, now, ROUTE_TTL_MS)) return Advice(AdviceState.WAITING, "새 회전 정보를 기다립니다", "실제 TBT 이벤트가 도착해야 해당 회전에 혼잡 시나리오를 적용합니다.")
            if (direction == null) return Advice(AdviceState.NORMAL, "다음 안내는 좌·우회전이 아닙니다", "직진·유턴 등에는 회전 차로 대기열 시나리오를 적용하지 않습니다.")
            val d = route.turnMeters
            if (d == null || !d.isFinite() || d < 0 || d > 100_000) return Advice(AdviceState.WAITING, "회전 거리를 확인 중입니다", "유효한 거리 정보가 필요합니다.")
            d.toInt()
        }
        if (!fresh(observationAt, now, OBSERVATION_TTL_MS)) return Advice(AdviceState.EXPIRED, "혼잡 정보가 만료되었습니다", "새 관측을 기다립니다. 대기열 위치와 준비 거리는 표시하지 않습니다.", distance)
        val lower = if (receivedQueue != null) receivedQueue.low else scenario.low
        val upper = if (receivedQueue != null) receivedQueue.high else scenario.high
        if (lower == null || upper == null) return Advice(AdviceState.CAUTION, "${direction!!.label} 차로 혼잡 가능성", "관측이 부족합니다. 정확한 대기열 후미는 알 수 없습니다.", distance)
        if (scenario.twoBlocks) return evaluateBlocks(direction!!,distance,lower,upper,blocks,now)
        val prepare = upper + PREPARATION_MARGIN_METERS
        if (scenario.risk && distance <= upper) return Advice(AdviceState.ALTERNATIVE, "무리한 차선 변경을 피하세요", "가상 대기열 후미 구간에 도달했습니다. 기존 내비에서 다음 경로를 확인하세요.", distance, lower, upper, prepare)
        if (scenario.risk && distance <= prepare) return Advice(AdviceState.PREPARE, "${direction!!.lane} 차로를 미리 준비하세요", "주변 차량과 차선을 직접 확인하세요. 이 표시는 차선 변경 허가가 아닙니다.", distance, lower, upper, prepare)
        return Advice(AdviceState.NORMAL, "아직 준비 구간 전입니다", "혼잡 상황을 확인하고 있습니다. 지금 차선을 바꿀 필요를 뜻하지 않습니다.", distance, lower, upper, prepare)
    }

    private fun evaluateBlocks(direction: TurnDirection, distance: Int, lower: Int, upper: Int,
        blocks: BlockTraffic?, now: Long): Advice {
        fun unknown(detail: String) = Advice(AdviceState.CAUTION,"블록별 준비 구간 확인 중",detail,distance)
        if (blocks == null) return unknown("두 교차로 간 거리와 각 블록의 차로 정보가 필요합니다.")
        if (!fresh(blocks.currentObservedAt,now,OBSERVATION_TTL_MS)) return Advice(AdviceState.EXPIRED,
            "이번 블록 혼잡 정보가 만료되었습니다","두 블록 중 하나라도 오래되면 준비 지점을 표시하지 않습니다.",distance)
        val currentLow=blocks.currentLow
        val currentHigh=blocks.currentHigh
        if (blocks.blockLength !in 1..100_000 || blocks.intersectionBuffer !in 0 until blocks.blockLength ||
            distance <= blocks.blockLength || currentLow == null || currentHigh == null ||
            currentLow < 0 || currentHigh < currentLow || currentHigh > 100_000 || lower < 0 || upper < lower)
            return unknown("교차로 거리와 두 블록의 대기열 범위를 다시 확인해야 합니다.")
        if (blocks.throughLaneContinues != true || blocks.currentChangeWindowKnown != true || blocks.nextChangeWindowKnown != true)
            return unknown("직진 가능한 차로의 연결과 변경 가능 구간이 확인되지 않아 다음 블록으로 준비를 미루지 않습니다.")
        val targetPrepare=upper+PREPARATION_MARGIN_METERS
        // A short next block may still need early preparation even if it looks uncongested.
        if (targetPrepare <= blocks.blockLength-blocks.intersectionBuffer) {
            return Advice(AdviceState.NORMAL,"다음 블록에서 ${direction.lane} 차로 준비",
                "이번 교차로는 직진하고, 다음 블록에서 ${direction.label}을 준비하는 시연입니다. 다음 블록 ${blocks.blockLength} m에서 교차로 통과 여유 ${blocks.intersectionBuffer} m와 목표 대기열 상한 $upper m를 제외해도 준비 여유 ${PREPARATION_MARGIN_METERS} m가 남습니다. 실제 차로 연결·표시와 주변 차량을 확인하세요.",
                distance,lower,upper,targetPrepare,PreparationBlock.NEXT)
        }
        // Preparing before the first junction must also precede its own queue, not just the target queue.
        val currentTail=blocks.blockLength+currentHigh
        val prepare=maxOf(targetPrepare,currentTail+PREPARATION_MARGIN_METERS)
        val state=when {
            distance <= maxOf(upper,currentTail) -> AdviceState.ALTERNATIVE
            distance <= prepare -> AdviceState.PREPARE
            else -> AdviceState.NORMAL
        }
        val title=if(state==AdviceState.ALTERNATIVE) "무리한 차선 변경을 피하세요" else "이번 블록에서 ${direction.lane} 차로 준비"
        return Advice(state,title,
            "다음 블록 안에는 목표 대기열 전에 준비할 여유가 부족합니다. 이번 블록의 회전·직진 공용 차로에서 미리 준비한 뒤 이번 교차로를 직진하는 시연입니다. 준비 기준은 목표 교차로 전 $prepare m이며, 이번 대기열 후미와 ${PREPARATION_MARGIN_METERS} m 여유를 함께 반영했습니다. 차선 변경 허가를 뜻하지 않습니다.",
            distance,lower,upper,prepare,PreparationBlock.CURRENT)
    }
}
