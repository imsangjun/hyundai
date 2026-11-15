"""Image-space density evidence only: never speed, metric queue length, or free flow."""
from collections import deque


class VisualDensityJudge:
    def __init__(self):
        self.history = deque()

    def evaluate(self, time, vehicles, lane):
        # UNKNOWN can contain several lanes/opposing/parked cars and must never be pooled.
        by_id = {v['id']:v['box'] for v in vehicles if v['laneId']==lane and v['confidence']>=.5 and v['id']>=0}
        boxes = list(by_id.values())
        boxes.sort(key=lambda b:b[3])
        group,maximum = 1,1
        for a,b in zip(boxes,boxes[1:]):
            # Perspective proxy, not physical headway. Require three ordered nearby contacts.
            height = ((a[3]-a[1])+(b[3]-b[1]))/2
            gap = b[3]-a[3]
            group = group+1 if 0 < gap <= 1.5*height else 1
            maximum = max(maximum,group)
        dense = lane!='UNKNOWN' and len(boxes)>=3 and maximum>=3
        if self.history and not 0 < time-self.history[-1][0] <= .5:
            self.history.clear()
        self.history.append((time,dense))
        while self.history and time-self.history[0][0]>5.1:
            self.history.popleft()
        sustained = (len(self.history)>=30 and time-self.history[0][0]>=5 and
                     sum(flag for _,flag in self.history)/len(self.history)>=.8)
        return 'DENSE_TRAFFIC_CANDIDATE' if dense and sustained else 'INSUFFICIENT_DATA'
