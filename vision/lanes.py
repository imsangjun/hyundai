"""YOLOP lane segmentation and conservative image-space lane assignment."""
from dataclasses import dataclass
import cv2
import numpy as np


@dataclass
class Boundary:
    coefficients: np.ndarray
    top: float
    bottom: float

    def x(self, y):
        return float(np.polyval(self.coefficients, y))


class LaneGeometry:
    def __init__(self, mask, road):
        self.mask, self.road = mask, road
        self.boundaries = self._trace(mask)
        self.ego_pair = None
        self.reference_y = 0.85
        for index in range(len(self.boundaries) - 1):
            a, b = self.boundaries[index:index+2]
            if self._valid_pair(a, b, self.reference_y) and a.x(self.reference_y) < 0.5 < b.x(self.reference_y):
                self.ego_pair = index
                break

    @staticmethod
    def _trace(mask):
        height, width = mask.shape
        traces = []
        # Follow line centers upward. Short gaps allow dashed paint, but no long extrapolation.
        for row in range(int(height * 0.97), int(height * 0.43), -max(2, height // 90)):
            indices = np.flatnonzero(mask[row] > 0)
            runs = np.split(indices, np.where(np.diff(indices) > 1)[0] + 1)
            centers = [float(r.mean()) / width for r in runs if 1 <= len(r) <= width * 0.04]
            y = row / height
            candidates = []
            for center_index,x in enumerate(centers):
                for i, trace in enumerate(traces):
                    if trace[-1][0] - y > 0.12:
                        continue
                    recent = trace[-5:]
                    predicted = recent[-1][1]
                    if len(recent) >= 3:
                        fit = np.polyfit([p[0] for p in recent], [p[1] for p in recent], 1)
                        predicted = np.polyval(fit, y)
                    candidates.append((abs(x-predicted), i, center_index))
            used_traces,used_centers = set(),set()
            for distance,trace_index,center_index in sorted(candidates):
                if distance <= 0.035 and trace_index not in used_traces and center_index not in used_centers:
                    traces[trace_index].append((y,centers[center_index]))
                    used_traces.add(trace_index); used_centers.add(center_index)
            for i,x in enumerate(centers):
                if i not in used_centers:
                    traces.append([(y,x)])
        boundaries = []
        for trace in traces:
            ys, xs = np.array(trace).T
            if len(trace) < 8 or max(ys)-min(ys) < 0.14:
                continue
            fit = np.polyfit(ys, xs, 2)
            if np.sqrt(np.mean((np.polyval(fit,ys)-xs)**2)) > 0.015:
                continue
            boundaries.append(Boundary(fit, float(min(ys)), float(max(ys))))
        boundaries.sort(key=lambda b: b.x(0.85))
        # Merge overlapping traces of the same painted stripe.
        unique = []
        for b in boundaries:
            if not unique or abs(b.x(0.85)-unique[-1].x(0.85)) > 0.025:
                unique.append(b)
        return unique

    def _valid_pair(self, a, b, y):
        if not (max(a.top,b.top)-0.02 <= y <= min(a.bottom,b.bottom)+0.02):
            return False
        left, right = a.x(y), b.x(y)
        if not 0.025 < right-left < 0.65 or not 0 <= left < right <= 1:
            return False
        h, w = self.road.shape
        # Vehicles occlude the road at their contact row. Inspect the road immediately below.
        support_y = min(y+0.04,0.97)
        road = self.road[min(h-1,int(support_y*h)), max(0,int(a.x(support_y)*w)):min(w,int(b.x(support_y)*w))]
        return len(road) > 0 and float(road.mean()) >= 0.25

    def assign(self, point):
        x, y = point
        if self.ego_pair is None or y >= 0.98:
            return "UNKNOWN"
        for index in range(len(self.boundaries)-1):
            a, b = self.boundaries[index:index+2]
            if self._valid_pair(a,b,y) and a.x(y)+0.008 < x < b.x(y)-0.008:
                relative = index-self.ego_pair
                return "EGO" if relative == 0 else f"{'LEFT' if relative < 0 else 'RIGHT'}_{abs(relative)}"
        return "UNKNOWN"

    def draw(self, frame):
        image = frame.copy()
        image[self.mask > 0] = image[self.mask > 0] // 2 + np.array([0,120,120],dtype=np.uint8)
        h, w = image.shape[:2]
        for b in self.boundaries:
            points = np.array([[int(b.x(y)*w),int(y*h)] for y in np.linspace(b.top,b.bottom,40)],np.int32)
            cv2.polylines(image,[points],False,(255,160,0),2)
        return image


class LaneDetector:
    def __init__(self, model_path):
        self.network = cv2.dnn.readNetFromONNX(str(model_path))

    def detect(self, frame):
        h,w = frame.shape[:2]
        ratio = min(640/h,640/w)
        nh,nw = round(h*ratio),round(w*ratio)
        top,left = (640-nh)//2,(640-nw)//2
        canvas = np.full((640,640,3),114,np.uint8)
        canvas[top:top+nh,left:left+nw] = cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB),(nw,nh),interpolation=cv2.INTER_AREA)
        normalized = (canvas.astype(np.float32)/255 - np.float32([.485,.456,.406])) / np.float32([.229,.224,.225])
        self.network.setInput(normalized.transpose(2,0,1)[None])
        _, road, lane = self.network.forward(["det_out","drive_area_seg","lane_line_seg"])
        masks = [cv2.resize(np.argmax(a[0,:,top:top+nh,left:left+nw],axis=0).astype(np.uint8),
                           (w,h),interpolation=cv2.INTER_NEAREST) for a in (road,lane)]
        return LaneGeometry(masks[1],masks[0])
