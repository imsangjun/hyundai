package com.mergewindow.app

import org.junit.Assert.*
import org.junit.Test

class V2xSimulationTest {
    @Test fun fourHopsDeliverTwoIndependentNextBlockSources() {
        val network = V2xSimulation()
        network.tick(0); network.tick(1000)
        assertEquals(2, network.estimate(1, 1000).sources)
        assertEquals(450, network.estimate(1, 1000).high)
        assertEquals(listOf("V4", "V3", "V2", "V1", "EGO"), network.nodes.first().received["V4"]!!.path)
        assertTrue(network.nodes.last().received.containsKey("EGO"))
    }
    @Test fun shortHopBudgetAndTotalLossDoNotInventQueue() {
        val network = V2xSimulation().apply { maxHops = 2 }
        network.tick(0); network.tick(1000)
        assertNull(network.estimate(1, 1000).high)
        val disconnected = V2xSimulation().apply { lossPercent = 100 }
        disconnected.tick(0); disconnected.tick(1000)
        assertEquals(0, disconnected.delivered)
        assertNull(disconnected.estimate(0, 1000).high)
    }
    @Test fun stoppedSourcesExpireAndFreshClearObservationChangesAdvice() {
        val network = V2xSimulation()
        network.tick(0); network.tick(1000)
        fun advice(now: Long): Advice {
            val current = network.estimate(0, now)
            val next = network.estimate(1, now)
            return GuidanceEngine.evaluate(RouteSnapshot(connected=true,active=true,stateAt=now),
                Scenario.BOTH_BLOCKS,true,next.observedAt,now,true,blocks=BlockTraffic.demo(now).copy(
                    currentLow=current.low,currentHigh=current.high,currentObservedAt=current.observedAt),receivedQueue=next)
        }
        assertEquals(PreparationBlock.CURRENT, advice(1000).preparationBlock)
        network.nextClear = true
        network.tick(3000); network.tick(4000)
        assertEquals(PreparationBlock.NEXT, advice(4000).preparationBlock)
        network.paused = true
        network.tick(16001)
        assertNull(advice(16001).prepareAt)
    }
    @Test fun duplicatesOldPacketsWrongRouteAndFutureObservationsAreRejected() {
        val node = V2xNode("EGO",0)
        val observation = VehicleObservation("V1",1,100,"demo-route",200,2.0,CameraQueue(0,TurnDirection.LEFT,100,180,0.9))
        val packet = V2xPacket(observation,listOf("V1"))
        assertTrue(node.receive(packet,100))
        assertFalse(node.receive(packet,101))
        assertFalse(node.receive(packet.copy(observation=observation.copy(sequence=2,routeId="other")),101))
        assertFalse(node.receive(packet.copy(observation=observation.copy(sequence=2,observedAt=200)),101))
        assertNull(node.estimate(0,TurnDirection.RIGHT,101).high)
        assertEquals(1,node.estimate(0,TurnDirection.LEFT,101).sources)
    }
}
