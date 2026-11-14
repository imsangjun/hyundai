import unittest
from traffic import QueueJudge, Track, longitudinal_speed
from analyze import calibration_at


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.calibration = dict(junction_m=450, error_m=5, quality=0.9,
                                block=1, lane="RIGHT", tail_visible=True, full_block_visible=False)
        self.tracks = [Track(i, 20 + i * 8, 0.3, 0.9) for i in range(3)]

    def run_sequence(self, tracks, calibration):
        judge = QueueJudge()
        for t in range(7):
            state, camera = judge.evaluate(t, tracks, calibration)
        return state, camera

    def test_sustained_queue_has_metric_interval(self):
        state, camera = self.run_sequence(self.tracks, self.calibration)
        self.assertEqual("LOW_SPEED_QUEUE", state)
        self.assertEqual((425, 435), (camera["low"], camera["high"]))

    def test_occluded_tail_has_no_invented_upper_bound(self):
        state, camera = self.run_sequence(self.tracks, {**self.calibration, "tail_visible": False})
        self.assertEqual("LOW_SPEED_QUEUE", state)
        self.assertIsNone(camera)

    def test_sparse_or_uncalibrated_observations_cannot_confirm_queue(self):
        self.assertIsNone(self.run_sequence(self.tracks, None)[1])
        scattered = [Track(i, i * 80, 0.2, 0.9) for i in range(3)]
        self.assertEqual("INSUFFICIENT_DATA", self.run_sequence(scattered, self.calibration)[0])

    def test_gap_resets_duration_and_flow_needs_coverage(self):
        judge = QueueJudge()
        judge.evaluate(0, self.tracks, self.calibration)
        self.assertEqual("OBSERVING", judge.evaluate(10, self.tracks, self.calibration)[0])
        moving = [Track(i, 20+i*8, 10, 0.9) for i in range(3)]
        self.assertIsNone(self.run_sequence(moving, self.calibration)[1])
        self.assertEqual(0, self.run_sequence(moving, {**self.calibration, "full_block_visible": True})[1]["high"])

    def test_moving_camera_calibration_expires(self):
        config = {"calibration": [{"time_s": 0, "ego_mps": 5}]}
        self.assertIsNone(calibration_at(config, 1))
        with self.assertRaises(ValueError):
            calibration_at({**config, "fixed_camera": True}, 0)

    def test_same_relative_position_does_not_mean_stopped(self):
        self.assertEqual(10, longitudinal_speed(20, 20, 0.1, 10, 10))
        self.assertAlmostEqual(0, longitudinal_speed(19, 20, 0.1, 10, 10))


if __name__ == "__main__":
    unittest.main()
