import unittest
import cv2
import numpy as np
from lanes import LaneGeometry


class LaneTest(unittest.TestCase):
    def geometry(self, lines):
        mask = np.zeros((300,600),np.uint8)
        for bottom,top in lines:
            cv2.line(mask,(int(bottom*600),290),(int(top*600),135),1,4)
        return LaneGeometry(mask,np.ones_like(mask))

    def test_adjacent_lanes_are_distinct(self):
        g = self.geometry([(.1,.3),(.4,.45),(.7,.6)])
        self.assertEqual("EGO",g.assign((.52,.8)))
        self.assertEqual("LEFT_1",g.assign((.3,.8)))

    def test_missing_boundary_and_outside_region_are_unknown(self):
        g = self.geometry([(.4,.45)])
        self.assertEqual("UNKNOWN",g.assign((.5,.8)))
        g = self.geometry([(.3,.4),(.7,.6)])
        self.assertEqual("UNKNOWN",g.assign((.5,.3)))
        self.assertEqual("UNKNOWN",g.assign((.5,.99)))

    def test_contact_on_boundary_is_not_forced_into_lane(self):
        g = self.geometry([(.3,.4),(.7,.6)])
        self.assertEqual("UNKNOWN",g.assign((g.boundaries[0].x(.8),.8)))


if __name__ == "__main__":
    unittest.main()
