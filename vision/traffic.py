"""Temporal lane evidence. Metric inputs must already be ego-motion compensated."""
from dataclasses import dataclass
from math import isfinite, ceil, floor


def longitudinal_speed(distance, previous_distance, elapsed, ego_speed, previous_ego_speed):
    """Straight, locally planar road model. Inputs use meters, seconds and m/s."""
    return (distance - previous_distance) / elapsed + (ego_speed + previous_ego_speed) / 2


@dataclass
class Track:
    id: int
    distance: float
    speed: float
    confidence: float


class QueueJudge:
    def __init__(self, hold_seconds=5.0):
        self.hold = hold_seconds
        self.since = None
        self.previous_time = None
        self.previous_state = None
        self.previous_lane = None

    def evaluate(self, time, tracks, calibration):
        state, camera = "INSUFFICIENT_DATA", None
        valid = [t for t in tracks if all(isfinite(v) for v in (t.distance, t.speed, t.confidence))
                 and 0 <= t.distance <= 500 and 0 <= t.speed <= 70 and t.confidence >= 0.5]
        slow = sorted([t for t in valid if t.speed <= 5 / 3.6], key=lambda t: t.distance)
        # Require a spatially continuous group instead of summing unrelated stopped vehicles.
        groups = []
        for track in slow:
            if not groups or track.distance - groups[-1][-1].distance > 15:
                groups.append([])
            groups[-1].append(track)
        queue = max(groups, key=len, default=[])
        if calibration and len(queue) >= 3:
            state = "LOW_SPEED_QUEUE"
        elif calibration and len(valid) >= 3 and all(t.speed >= 15 / 3.6 for t in valid):
            state = "FLOWING_OBSERVED"
        lane = (calibration["block"], calibration["lane"]) if calibration else None
        if (self.previous_time is None or time <= self.previous_time or time - self.previous_time > 1.0
                or state != self.previous_state or lane != self.previous_lane):
            self.since = time
        self.previous_time, self.previous_state = time, state
        self.previous_lane = lane
        sustained = time - self.since >= self.hold
        if state != "INSUFFICIENT_DATA" and not sustained:
            return "OBSERVING", None
        if state == "LOW_SPEED_QUEUE" and calibration.get("tail_visible"):
            junction = calibration["junction_m"]
            tail = junction - min(t.distance for t in queue)
            error = calibration["error_m"]
            if 0 <= tail - error <= tail + error <= 500:
                camera = {"block": calibration["block"], "lane": calibration["lane"],
                          "low": floor(tail - error), "high": ceil(tail + error),
                          "confidence": min(calibration["quality"], min(t.confidence for t in queue))}
        if state == "FLOWING_OBSERVED" and calibration.get("full_block_visible"):
            camera = {"block": calibration["block"], "lane": calibration["lane"],
                      "low": 0, "high": 0,
                      "confidence": min(calibration["quality"], min(t.confidence for t in valid))}
        return state, camera
