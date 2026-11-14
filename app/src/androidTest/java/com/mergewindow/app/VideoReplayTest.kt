package com.mergewindow.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class VideoReplayTest {
    private fun fixture(): JSONObject {
        val entries = JSONArray()
        for (step in 0..1) for (node in 1..4) {
            val current = node <= 2
            val clear = !current && step == 1
            entries.put(JSONObject().apply {
                put("offsetMs",step * 2000); put("origin","video-" + node.toString().repeat(64))
                put("node","V$node"); put("sequence",step+1)
                put("visionState",if (clear) "FLOWING_OBSERVED" else "LOW_SPEED_QUEUE")
                put("vehicleCount",3)
                put("camera",JSONObject().apply {
                    put("block",if(current) 0 else 1); put("lane","RIGHT")
                    put("low",if(clear) 0 else if(current) 150 else 425)
                    put("high",if(clear) 0 else if(current) 170 else 435)
                    put("confidence",0.9)
                })
            })
        }
        return JSONObject().put("version",1).put("kind","YOLO_VIDEO").put("observations",entries)
    }

    @Test fun calibratedContractRelaysChangesAdviceAndExpires() {
        val network = V2xSimulation().apply { syntheticSources = false }
        val replay = VideoReplay(fixture().toString(),1000)
        fun advice(now: Long): Advice {
            val current = network.estimate(0,now)
            val next = network.estimate(1,now)
            return GuidanceEngine.evaluate(RouteSnapshot(connected=true,active=true,stateAt=now),
                Scenario.BOTH_BLOCKS,true,next.observedAt,now,true,blocks=BlockTraffic.demo(now).copy(
                    currentLow=current.low,currentHigh=current.high,currentObservedAt=current.observedAt),receivedQueue=next)
        }
        replay.tick(1000,network); network.tick(1500)
        assertEquals(PreparationBlock.CURRENT,advice(1500).preparationBlock)
        replay.tick(3000,network); network.tick(3500)
        assertEquals(PreparationBlock.NEXT,advice(3500).preparationBlock)
        assertTrue(replay.finished)
        network.tick(16000)
        assertNull(advice(16000).prepareAt)
    }

    @Test fun repeatedFootageCannotBecomeIndependentVehicles() {
        val json = fixture()
        val entries = json.getJSONArray("observations")
        entries.getJSONObject(1).put("origin",entries.getJSONObject(0).getString("origin"))
        assertThrows(IllegalArgumentException::class.java) { VideoReplay(json.toString(),0) }
    }
}
