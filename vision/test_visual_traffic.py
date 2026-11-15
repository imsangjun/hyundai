import unittest
from visual_traffic import VisualDensityJudge


def vehicles(lane='LEFT_1'):
    return [dict(id=i,box=[100,200+i*35,150,250+i*35],confidence=.9,laneId=lane) for i in range(3)]


class VisualDensityTest(unittest.TestCase):
    def test_dense_requires_five_seconds_and_never_confirms_congestion(self):
        judge=VisualDensityJudge()
        for step in range(50):
            self.assertEqual('INSUFFICIENT_DATA',judge.evaluate(step/10,vehicles(),'LEFT_1'))
        self.assertEqual('DENSE_TRAFFIC_CANDIDATE',judge.evaluate(5,vehicles(),'LEFT_1'))

    def test_unknown_and_mixed_lanes_are_not_pooled(self):
        for lane,boxes in [('UNKNOWN',vehicles('UNKNOWN')),('EGO',vehicles())]:
            judge=VisualDensityJudge()
            for step in range(70):
                self.assertEqual('INSUFFICIENT_DATA',judge.evaluate(step/10,boxes,lane))

    def test_gap_and_current_loss_clear_candidate(self):
        judge=VisualDensityJudge()
        for step in range(60): judge.evaluate(step/10,vehicles(),'LEFT_1')
        self.assertEqual('INSUFFICIENT_DATA',judge.evaluate(6,[],'LEFT_1'))
        self.assertEqual('INSUFFICIENT_DATA',judge.evaluate(8,vehicles(),'LEFT_1'))

    def test_spatially_distant_vehicles_are_not_a_dense_group(self):
        boxes=vehicles()
        for i,b in enumerate(boxes): b['box']=[100,100+i*200,150,130+i*200]
        judge=VisualDensityJudge()
        for step in range(70):
            self.assertEqual('INSUFFICIENT_DATA',judge.evaluate(step/10,boxes,'LEFT_1'))

    def test_duplicate_track_is_one_vehicle(self):
        boxes=vehicles()
        for b in boxes: b['id']=1
        judge=VisualDensityJudge()
        for step in range(70):
            self.assertEqual('INSUFFICIENT_DATA',judge.evaluate(step/10,boxes,'LEFT_1'))


if __name__=='__main__': unittest.main()
