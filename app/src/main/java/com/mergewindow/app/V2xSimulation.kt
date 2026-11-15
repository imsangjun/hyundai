package com.mergewindow.app

import java.util.PriorityQueue
import kotlin.math.abs
import kotlin.random.Random

/** Application messages over a simulated NR-V2X PC5 transport. All coordinates are fictional route meters. */
data class CameraQueue(val block: Int, val lane: TurnDirection, val low: Int, val high: Int, val confidence: Double)
data class VehicleObservation(val origin: String, val sequence: Long, val observedAt: Long,
    val routeId: String, val positionMeters: Int, val speedMps: Double?, val camera: CameraQueue?,
    val visionState: String = "SIMULATED", val vehicleCount: Int = 0, val laneSummary: String = "")
data class V2xPacket(val observation: VehicleObservation, val path: List<String>)
data class QueueEstimate(val low: Int?, val high: Int?, val observedAt: Long, val sources: Int = 0)

/** Each node owns its receive cache. Relaying preserves origin, sequence and observation time. */
class V2xNode(val id: String, val position: Int) {
    val received = mutableMapOf<String, V2xPacket>()
    fun receive(packet: V2xPacket, now: Long): Boolean {
        val observation = packet.observation
        if (!GuidanceEngine.fresh(observation.observedAt, now, GuidanceEngine.OBSERVATION_TTL_MS) ||
            observation.routeId != "demo-route" || id in packet.path ||
            (observation.speedMps != null && observation.speedMps !in 0.0..70.0) || observation.positionMeters !in 0..1000) return false
        val camera = observation.camera
        if (camera != null && (camera.block !in 0..1 || camera.low < 0 || camera.high < camera.low ||
                camera.high > 500 || camera.confidence !in 0.0..1.0)) return false
        val previous = received[observation.origin]?.observation
        if (previous != null && (previous.sequence >= observation.sequence || previous.observedAt > observation.observedAt)) return false
        received[observation.origin] = packet.copy(path = packet.path + id)
        return true
    }

    fun estimate(block: Int, lane: TurnDirection, now: Long): QueueEstimate {
        val samples = received.values.map { it.observation }.filter {
            GuidanceEngine.fresh(it.observedAt, now, GuidanceEngine.OBSERVATION_TTL_MS) &&
                it.camera?.block == block && it.camera.lane == lane && it.camera.confidence >= 0.7
        }
        if (samples.size < 2) return QueueEstimate(null, null, now, samples.size)
        // Envelope of source intervals, not a probability interval. Relays never add independent votes.
        return QueueEstimate(samples.minOf { it.camera!!.low }, samples.maxOf { it.camera!!.high },
            samples.minOf { it.observedAt }, samples.size)
    }
}

class V2xSimulation {
    val nodes = (0..4).map { V2xNode(if (it == 0) "EGO" else "V$it", it * 200) }
    var maxHops = 4
    var lossPercent = 0
    var paused = false
    var nextClear = false
    var direction = TurnDirection.RIGHT
    var syntheticSources = true
    var transmitted = 0; private set
    var delivered = 0; private set
    var dropped = 0; private set
    private var sequence = 0L
    private var lastPublished = -1L
    private val random = Random(42)
    private data class Delivery(val at: Long, val target: V2xNode, val packet: V2xPacket)
    private val pending = PriorityQueue<Delivery>(compareBy { it.at })

    fun publishVideo(nodeId: String, observation: VehicleObservation, now: Long) {
        val sender = nodes.first { it.id == nodeId }
        if (!paused) broadcast(sender, V2xPacket(observation, listOf(nodeId)), now)
    }

    private fun broadcast(sender: V2xNode, packet: V2xPacket, at: Long) {
        if (packet.path.size - 1 >= maxHops.coerceIn(1, 4)) return
        transmitted++
        nodes.filter { it.id !in packet.path && abs(it.position - sender.position) <= 250 }.forEach {
            if (random.nextInt(100) < lossPercent.coerceIn(0, 100)) dropped++
            else pending.add(Delivery(at + 100, it, packet))
        }
    }

    fun tick(now: Long) {
        while (pending.isNotEmpty() && pending.peek().at <= now) {
            val delivery = pending.remove()
            if (delivery.target.receive(delivery.packet, now)) {
                delivered++
                broadcast(delivery.target, delivery.target.received.getValue(delivery.packet.observation.origin), delivery.at)
            }
        }
        if (!syntheticSources || paused || (lastPublished >= 0 && now - lastPublished < 3000)) return
        lastPublished = now
        sequence++
        nodes.forEachIndexed { index, node ->
            val block = if (index <= 2) 0 else 1
            val clear = block == 1 && nextClear
            val camera = if (index == 0) null else CameraQueue(block, direction,
                if (clear) 60 else if (block == 0) 100 else 360,
                if (clear) 120 else if (block == 0) 180 else 450, 0.9)
            val observation = VehicleObservation(node.id, sequence, now, "demo-route", node.position,
                if (clear) 11.0 else 2.0, camera)
            broadcast(node, V2xPacket(observation, listOf(node.id)), now)
        }
    }

    fun estimate(block: Int, now: Long) = nodes.first().estimate(block, direction, now)
    fun status(now: Long): String {
        val packets = nodes.first().received.values.filter {
            GuidanceEngine.fresh(it.observation.observedAt, now, GuidanceEngine.OBSERVATION_TTL_MS)
        }
        val paths = packets.joinToString("\n") {
            val vision = if (it.observation.visionState == "SIMULATED") "" else
                " · 차량 ${it.observation.vehicleCount}대 · ${it.observation.visionState}\n${it.observation.laneSummary}"
            "${it.path.joinToString(" → ")} · ${(now-it.observation.observedAt)/1000}s$vision"
        }
        return "5G NR-V2X PC5 가정 · 가상 차량 5대\n송신 $transmitted · 수신 $delivered · 손실 $dropped\n내 차량의 유효 출처 ${packets.size}대 / 최대 $maxHops 홉\n$paths"
    }
}
