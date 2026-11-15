import unittest
import numpy as np
from lanes import Boundary, LaneGeometry
from structural_lanes import StructuralGeometry,FusedGeometry
from audit_lanes import match_vehicle


def boundary(x,top=.5):
    return Boundary(np.array([0.,0.,x]),top,1.)


def painted(boundaries,ego):
    g=LaneGeometry.__new__(LaneGeometry)
    g.mask=np.zeros((100,100),np.uint8);g.road=np.ones_like(g.mask)
    g.boundaries=boundaries;g.ego_pair=ego
    return g


class FusionTest(unittest.TestCase):
    def test_far_vehicle_uses_supported_paint_when_structural_range_ends(self):
        u=StructuralGeometry([None,boundary(.3,.7),boundary(.7,.7),None])
        s=painted([boundary(.3),boundary(.7)],0)
        g=FusedGeometry(u,s)
        self.assertEqual('UNKNOWN',u.assign((.5,.6)))
        self.assertEqual({'laneId':'EGO','reason':'PAINT_BOUNDARIES_RECOVERY','metricEligible':True},g.explain((.5,.6)))

    def test_missing_outer_boundary_can_use_compatible_paint(self):
        u=StructuralGeometry([None,boundary(.3),boundary(.7),None])
        s=painted([boundary(.1),boundary(.3),boundary(.7)],1)
        self.assertEqual('LEFT_1',FusedGeometry(u,s).assign((.2,.8)))

    def test_incompatible_models_do_not_fill_unknown(self):
        u=StructuralGeometry([None,boundary(.3,.7),boundary(.7,.7),None])
        s=painted([boundary(.4),boundary(.8)],0)
        self.assertEqual('UNKNOWN',FusedGeometry(u,s).assign((.5,.6)))

    def test_short_extension_is_provisional_requires_paint_and_bounded_gap(self):
        u=StructuralGeometry([None,boundary(.3,.645),boundary(.7,.665),None])
        g=FusedGeometry(u,painted([boundary(.7,.64)],None))
        result=g.explain((.5,.64))
        self.assertEqual('EGO',result['laneId'])
        self.assertFalse(result['metricEligible'])
        self.assertEqual('UNKNOWN',g.assign((.5,.62)))
        self.assertEqual('UNKNOWN',g.assign((.302,.64)))
        self.assertEqual('UNKNOWN',FusedGeometry(u,painted([],None)).assign((.5,.64)))

    def test_both_absent_are_explained_not_filled(self):
        g=FusedGeometry(StructuralGeometry([None]*4),painted([boundary(.7)],None))
        self.assertEqual('EGO_BOUNDARIES_MISSING',g.explain((.5,.8))['reason'])

    def test_reference_box_does_not_match_foreground_car(self):
        label={'point':[930,690],'referenceBox':[900,610,962,693]}
        car=[875,657,944,704];bus=[898,610,962,691]
        self.assertIsNone(match_vehicle(label,[car],1080))
        self.assertEqual(bus,match_vehicle(label,[car,bus],1080))


if __name__=='__main__': unittest.main()
