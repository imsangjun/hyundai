package com.mergewindow.app

import org.junit.Assert.*
import org.junit.Test

class BlockGuidanceTest {
    private val now=100_000L
    private val route=RouteSnapshot(connected=true,active=true,stateAt=now)
    private val blocks=BlockTraffic.demo(now)
    private fun advice(s: Scenario, b: BlockTraffic?=blocks, observed: Long=now,
        direction: TurnDirection=TurnDirection.RIGHT, r: RouteSnapshot=route, parked: Boolean=true,
        virtual: Boolean=true)=GuidanceEngine.evaluate(r,s,virtual,observed,now,parked,direction,b)

    @Test fun bothQueuesRequirePreparationBeforeCurrentQueue() {
        val a=advice(Scenario.BOTH_BLOCKS)
        assertEquals(PreparationBlock.CURRENT,a.preparationBlock)
        assertEquals(AdviceState.PREPARE,a.state)
        // Target queue alone gives 600 m; current queue requires 500 + 180 + 150.
        assertEquals(830,a.prepareAt)
        assertEquals(360,a.lower);assertEquals(450,a.upper)
        assertTrue(a.title.contains("이번 블록"))
    }
    @Test fun nextBlockClearDefersPastFirstIntersection() {
        val a=advice(Scenario.NEXT_BLOCK_CLEAR)
        assertEquals(PreparationBlock.NEXT,a.preparationBlock)
        assertEquals(AdviceState.NORMAL,a.state)
        assertEquals(270,a.prepareAt)
        assertEquals(230,blocks.blockLength-a.prepareAt!!)
        assertTrue(a.title.contains("다음 블록"))
    }
    @Test fun clearButShortNextBlockDoesNotJustifyDeferral() {
        val a=advice(Scenario.NEXT_BLOCK_CLEAR,blocks.copy(blockLength=250))
        assertEquals(PreparationBlock.CURRENT,a.preparationBlock)
        assertEquals(580,a.prepareAt)
    }
    @Test fun exactPostIntersectionMarginBoundary() {
        assertEquals(PreparationBlock.NEXT,advice(Scenario.NEXT_BLOCK_CLEAR,blocks.copy(blockLength=320)).preparationBlock)
        assertEquals(PreparationBlock.CURRENT,advice(Scenario.NEXT_BLOCK_CLEAR,blocks.copy(blockLength=319)).preparationBlock)
    }
    @Test fun staleObservationInEitherBlockSuppressesPrecision() {
        for (b in listOf(blocks.copy(currentObservedAt=now-12001),blocks.copy(currentObservedAt=now+1))) {
            val a=advice(Scenario.NEXT_BLOCK_CLEAR,b)
            assertEquals(AdviceState.EXPIRED,a.state);assertNull(a.prepareAt);assertNull(a.preparationBlock)
        }
        val a=advice(Scenario.NEXT_BLOCK_CLEAR,observed=now-12001)
        assertEquals(AdviceState.EXPIRED,a.state);assertNull(a.prepareAt)
    }
    @Test fun missingLaneKnowledgeAndInvalidGeometryCannotPromiseLaterChange() {
        for (b in listOf(null,blocks.copy(throughLaneContinues=null),blocks.copy(throughLaneContinues=false),
            blocks.copy(currentChangeWindowKnown=false),blocks.copy(nextChangeWindowKnown=null),
            blocks.copy(currentLow=null),blocks.copy(currentHigh=99),blocks.copy(currentHigh=100001),
            blocks.copy(blockLength=0),blocks.copy(blockLength=800),blocks.copy(intersectionBuffer=500))) {
            val a=advice(Scenario.NEXT_BLOCK_CLEAR,b)
            assertEquals(AdviceState.CAUTION,a.state);assertNull(a.prepareAt);assertNull(a.preparationBlock)
        }
    }
    @Test fun reachingCurrentQueueTakesPriorityOverPreparation() {
        val a=advice(Scenario.BOTH_BLOCKS,blocks.copy(currentHigh=300))
        assertEquals(AdviceState.ALTERNATIVE,a.state)
        assertTrue(a.title.contains("무리한"))
    }
    @Test fun inactiveRestrictedAndRealTbtCannotInventTwoBlockGeometry() {
        assertNull(advice(Scenario.BOTH_BLOCKS,r=route.copy(active=false)).prepareAt)
        assertEquals(AdviceState.RESTRICTED,advice(Scenario.BOTH_BLOCKS,parked=false).state)
        val a=advice(Scenario.BOTH_BLOCKS,virtual=false)
        assertEquals(AdviceState.WAITING,a.state);assertNull(a.prepareAt)
    }
    @Test fun leftTurnHasSameBlockDecisionAndCorrectLaneCopy() {
        for(s in listOf(Scenario.BOTH_BLOCKS,Scenario.NEXT_BLOCK_CLEAR)) {
            val right=advice(s)
            val left=advice(s,direction=TurnDirection.LEFT)
            assertEquals(right.preparationBlock,left.preparationBlock)
            assertEquals(right.prepareAt,left.prepareAt)
            assertTrue(left.title.contains("좌측"))
        }
    }
}
