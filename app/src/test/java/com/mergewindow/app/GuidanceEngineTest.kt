package com.mergewindow.app

import org.junit.Assert.*
import org.junit.Test

class GuidanceEngineTest {
    private val now = 100_000L
    private val live = RouteSnapshot(connected=true,active=true,stateAt=now,rightTurn=true,turnMeters=650.0,tbtAt=now)
    private fun check(s: Scenario, r: RouteSnapshot = live, virtual: Boolean = true, observed: Long = now, parked: Boolean = true) = GuidanceEngine.evaluate(r,s,virtual,observed,now,parked)
    @Test fun scenarioMatrix() {
        assertEquals(AdviceState.NORMAL,check(Scenario.CLEAR).state)
        assertEquals(AdviceState.PREPARE,check(Scenario.CONGESTED).state)
        assertEquals(AdviceState.CAUTION,check(Scenario.UNCERTAIN).state)
        assertEquals(AdviceState.ALTERNATIVE,check(Scenario.MISSED).state)
    }
    @Test fun neverInventActiveRoute() {
        assertEquals(AdviceState.WAITING,check(Scenario.CONGESTED,live.copy(active=false)).state)
        assertEquals(AdviceState.WAITING,check(Scenario.CONGESTED,live.copy(connected=false)).state)
    }
    @Test fun staleDataSuppressesPrecision() {
        val a = check(Scenario.STALE,observed=now-12_001)
        assertEquals(AdviceState.EXPIRED,a.state); assertNull(a.lower); assertNull(a.prepareAt)
        assertEquals(AdviceState.EXPIRED,check(Scenario.CONGESTED,live.copy(stateAt=now-15_001)).state)
        assertEquals(AdviceState.EXPIRED,check(Scenario.CONGESTED,live.copy(stateAt=now+1)).state)
    }
    @Test fun actualTurnAndBoundaryDistances() {
        for ((d,state) in listOf(671.0 to AdviceState.NORMAL,670.0 to AdviceState.PREPARE,521.0 to AdviceState.PREPARE,520.0 to AdviceState.ALTERNATIVE)) {
            assertEquals(state,check(Scenario.CONGESTED,live.copy(turnMeters=d),false).state)
        }
        assertEquals(AdviceState.NORMAL,check(Scenario.CONGESTED,live.copy(rightTurn=false),false).state)
        for (d in listOf(Double.NaN,Double.POSITIVE_INFINITY,-1.0,100001.0)) assertEquals(AdviceState.WAITING,check(Scenario.CONGESTED,live.copy(turnMeters=d),false).state)
        assertEquals(AdviceState.WAITING,check(Scenario.CONGESTED,live.copy(tbtAt=now-15_001),false).state)
    }
    @Test fun unknownAndRestrictedSuppressGeometry() {
        assertNull(check(Scenario.UNCERTAIN).lower)
        val a=check(Scenario.CONGESTED,parked=false)
        assertEquals(AdviceState.RESTRICTED,a.state); assertNull(a.distance); assertNull(a.lower)
    }
    @Test fun leftAndRightUseIdenticalPreparationBoundaries() {
        for (direction in TurnDirection.entries) {
            for (type in if(direction==TurnDirection.LEFT) listOf("TURN_LEFT","TURN_SHARP_L") else listOf("TURN_RIGHT","TURN_SHARP_R")) {
                for ((distance,expected) in listOf(671.0 to AdviceState.NORMAL,670.0 to AdviceState.PREPARE,521.0 to AdviceState.PREPARE,520.0 to AdviceState.ALTERNATIVE)) {
                    val r=live.copy(rightTurn=false,turnType=type,turnMeters=distance)
                    val advice=check(Scenario.CONGESTED,r,false)
                    assertEquals("$type at $distance",expected,advice.state)
                    assertEquals(670,advice.prepareAt)
                    if(expected==AdviceState.PREPARE)assertTrue(advice.title.contains(direction.lane))
                }
            }
            val demo=GuidanceEngine.evaluate(live,Scenario.CONGESTED,true,now,now,true,direction)
            assertTrue(demo.title.contains(direction.lane))
            val uncertain=GuidanceEngine.evaluate(live,Scenario.UNCERTAIN,true,now,now,true,direction)
            assertTrue(uncertain.title.contains(direction.label));assertNull(uncertain.prepareAt)
            val expired=GuidanceEngine.evaluate(live,Scenario.STALE,true,now-12001,now,true,direction)
            assertNull(expired.prepareAt)
        }
        // An explicit straight/U-turn instruction must override the legacy rightTurn flag.
        for(type in listOf("TURN_STRAIGHT","TURN_UTURN")) {
            val advice=check(Scenario.CONGESTED,live.copy(turnType=type),false)
            assertEquals(AdviceState.NORMAL,advice.state);assertNull(advice.prepareAt)
        }
    }
}
