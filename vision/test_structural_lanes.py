import unittest
import numpy as np
from lanes import Boundary
from structural_lanes import StructuralGeometry


def boundary(x,top=.5,bottom=1):
    return Boundary(np.array([0,0,x]),top,bottom)


class StructuralGeometryTest(unittest.TestCase):
    def test_missing_outer_slot_does_not_renumber_lanes(self):
        g=StructuralGeometry([None,boundary(.3),boundary(.7),boundary(.9)])
        self.assertEqual('EGO',g.assign((.5,.8)))
        self.assertEqual('RIGHT_1',g.assign((.8,.8)))
        self.assertEqual('UNKNOWN',g.assign((.2,.8)))
        self.assertEqual('LEFT_OF_EGO',g.side((.2,.8)))

    def test_boundary_and_unsupported_distance_are_unknown(self):
        g=StructuralGeometry([boundary(.1),boundary(.3),boundary(.7),None])
        for point in [(.3,.8),(.31,.8),(.5,.4),(.5,.99)]:
            self.assertEqual('UNKNOWN',g.assign(point))

    def test_crossing_boundaries_are_rejected(self):
        crossing=Boundary(np.array([0,-1,1.1]),.5,1)
        g=StructuralGeometry([None,boundary(.3),crossing,None])
        self.assertIsNone(g.ego_pair)
        self.assertEqual('UNKNOWN',g.assign((.4,.6)))


if __name__=='__main__': unittest.main()
