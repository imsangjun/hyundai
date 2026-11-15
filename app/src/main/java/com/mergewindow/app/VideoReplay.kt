package com.mergewindow.app

import org.json.JSONObject

/** Finite offline playback. Video time is rebased once, never refreshed after end of file. */
class VideoReplay(text: String, private val startedAt: Long) {
    private data class Record(val offset: Long, val node: String, val origin: String,
        val sequence: Long, val state: String, val count: Int, val camera: CameraQueue?, val lanes: String)
    private val records: List<Record>
    private var cursor = 0
    val finished get() = cursor == records.size

    init {
        require(text.length <= 2_000_000) { "영상 관측 파일이 너무 큽니다" }
        val root = JSONObject(text)
        require(root.getInt("version") == 1 && root.getString("kind") == "YOLO_VIDEO")
        val entries = root.getJSONArray("observations")
        require(entries.length() in 1..10000)
        val origins = mutableMapOf<String, Pair<String, Long>>()
        val nodes = mutableMapOf<String, String>()
        var lastTime = -1L
        records = (0 until entries.length()).map { index ->
            val o = entries.getJSONObject(index)
            val offset = o.getLong("offsetMs")
            val node = o.getString("node")
            val origin = o.getString("origin")
            val sequence = o.getLong("sequence")
            val state = o.getString("visionState")
            val count = o.getInt("vehicleCount")
            require(offset in 0..3_600_000 && offset >= lastTime && count in 0..1000)
            require(node in listOf("V1", "V2", "V3", "V4") && origin.matches(Regex("video-[a-f0-9]{64}")))
            require(state in listOf("INSUFFICIENT_DATA", "VEHICLES_DETECTED", "OBSERVING", "LOW_SPEED_QUEUE", "FLOWING_OBSERVED"))
            val previous = origins[origin]
            require(sequence > (previous?.second ?: 0) && (previous == null || previous.first == node))
            require(nodes[node] == null || nodes[node] == origin)
            origins[origin] = node to sequence
            nodes[node] = origin
            lastTime = offset
            val camera = if (o.isNull("camera")) null else o.getJSONObject("camera").let { c ->
                require(state == "LOW_SPEED_QUEUE" || state == "FLOWING_OBSERVED")
                CameraQueue(c.getInt("block"),TurnDirection.valueOf(c.getString("lane")),
                    c.getInt("low"),c.getInt("high"),c.getDouble("confidence")).also {
                    require(it.block in 0..1 && it.low >= 0 && it.high in it.low..500 && it.confidence in 0.0..1.0)
                }
            }
            val lanes = o.optJSONArray("laneObservations")
            require(lanes == null || lanes.length() <= 12)
            val laneSummary = if (lanes == null) "" else (0 until lanes.length()).joinToString(" / ") { i ->
                val lane = lanes.getJSONObject(i)
                val id = lane.getString("laneId")
                val vehicles = lane.getInt("vehicleCount")
                val laneState = lane.getString("state")
                require(id.matches(Regex("EGO|UNKNOWN|LEFT_[1-9]|RIGHT_[1-9]")) && vehicles in 0..1000)
                val stateLabel = when(laneState) {
                    "INSUFFICIENT_DATA" -> "판단 보류"
                    "OBSERVING" -> "관측 중"
                    "LOW_SPEED_QUEUE" -> "저속 대기열"
                    "FLOWING_OBSERVED" -> "진행 관측"
                    else -> throw IllegalArgumentException("Unknown lane state")
                }
                val laneLabel = when(id) { "EGO" -> "내 차로"; "UNKNOWN" -> "차로 미확정"; else -> id }
                "$laneLabel ${vehicles}대 $stateLabel"
            }
            Record(offset,node,origin,sequence,state,count,camera,laneSummary)
        }
    }

    fun tick(now: Long, network: V2xSimulation) {
        while (cursor < records.size && startedAt + records[cursor].offset <= now) {
            val r = records[cursor++]
            val position = network.nodes.first { it.id == r.node }.position
            // The transport node position is a fictional topology, not video GPS.
            val observation = VehicleObservation(r.origin,r.sequence,startedAt+r.offset,"demo-route",position,
                null,r.camera,r.state,r.count,r.lanes)
            network.publishVideo(r.node,observation,now)
        }
    }
}
