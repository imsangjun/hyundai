"""CPU UFLDv2 CULane ResNet18 inference; no training/CUDA/DALI dependency.

Network and local-softmax decoder adapted from cfzd/Ultra-Fast-Lane-Detection-v2.
Copyright (c) 2022 zequn qin, MIT; see THIRD_PARTY_UFLD_LICENSE.txt.
Lane slots are retained: losing a boundary must not renumber adjacent lanes.
"""
import cv2
import numpy as np
import torch
from torch import nn
from torchvision.models import resnet18
from PIL import Image
from lanes import Boundary


class Network(nn.Module):
    def __init__(self):
        super().__init__()
        self.model = resnet18(weights=None)
        del self.model.fc
        self.pool = nn.Conv2d(512, 8, 1)
        self.cls = nn.Sequential(nn.LayerNorm(4000), nn.Linear(4000, 2048),
                                 nn.ReLU(), nn.Linear(2048, 200*72*4+100*81*4+2*72*4+2*81*4))

    def forward(self, x):
        m = self.model
        x = m.maxpool(m.relu(m.bn1(m.conv1(x))))
        x = m.layer4(m.layer3(m.layer2(m.layer1(x))))
        output = self.cls(self.pool(x).flatten(1))
        chunks = output.split([200*72*4,100*81*4,2*72*4,2*81*4], dim=1)
        return dict(zip(('loc_row','loc_col','exist_row','exist_col'),
                        [c.reshape(1,grid,anchors,4) for c,grid,anchors in
                         zip(chunks,[200,100,2,2],[72,81,72,81])]))


class StructuralGeometry:
    def __init__(self, slots):
        self.slots = slots
        self.boundaries = [b for b in slots if b is not None]
        self.ego_pair = 1 if self.valid_pair(1,.85) and slots[1].x(.85)<.5<slots[2].x(.85) else None

    def valid_pair(self, index, y):
        a,b = self.slots[index:index+2]
        if a is None or b is None or not max(a.top,b.top) <= y <= min(a.bottom,b.bottom):
            return False
        return 0 <= a.x(y) < b.x(y) <= 1 and .025 < b.x(y)-a.x(y) < .8

    def assign(self, point):
        x,y = point
        if self.ego_pair is None or y >= .98:
            return 'UNKNOWN'
        # Reject crossed boundaries throughout the supported interval.
        for i,name in enumerate(('LEFT_1','EGO','RIGHT_1')):
            if self.valid_pair(i,y):
                a,b = self.slots[i:i+2]
                if all(self.valid_pair(i,v) for v in np.linspace(y,min(a.bottom,b.bottom),8)):
                    margin = max(.008, (b.x(y)-a.x(y))*.06)
                    if a.x(y)+margin < x < b.x(y)-margin:
                        return name
        return 'UNKNOWN'

    def side(self, point):
        """Coarse side evidence, never an exact lane or input to queue aggregation."""
        if self.ego_pair is None:
            return 'UNKNOWN'
        x,y = point
        if not self.valid_pair(1,y):
            return 'UNKNOWN'
        if x < self.slots[1].x(y)-.008:
            return 'LEFT_OF_EGO'
        if x > self.slots[2].x(y)+.008:
            return 'RIGHT_OF_EGO'
        return 'UNKNOWN'

    def draw(self, frame):
        image = frame.copy()
        h,w = image.shape[:2]
        for b in self.boundaries:
            points = np.array([[int(b.x(y)*w),int(y*h)] for y in np.linspace(b.top,b.bottom,60)],np.int32)
            cv2.polylines(image,[points],False,(255,160,0),2)
        return image


class StructuralLaneDetector:
    def __init__(self, model_path):
        self.network = Network().eval()
        checkpoint = torch.load(model_path,map_location='cpu',weights_only=True)
        weights = {k.removeprefix('module.'):v for k,v in checkpoint['model'].items()}
        self.network.load_state_dict(weights,strict=True)

    def detect(self, frame):
        # Match official PIL Resize -> Normalize -> bottom crop, including bilinear interpolation.
        rgb = Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
        rgb = np.array(rgb.resize((1600,int(320/.6)),Image.Resampling.BILINEAR))[-320:]
        rgb = (rgb.astype(np.float32)/255-np.float32([.485,.456,.406]))/np.float32([.229,.224,.225])
        with torch.inference_mode():
            output = self.network(torch.from_numpy(rgb.transpose(2,0,1).copy())[None])
        slots = [None]*4
        for lane in range(4):
            axis = 'row' if lane in (1,2) else 'col'
            locations = output['loc_'+axis][0,:,:,lane]
            existence = output['exist_'+axis][0,:,:,lane].softmax(0)[1]
            valid = existence > .7
            if valid.sum().item() <= locations.shape[1] / (2 if axis=='row' else 4):
                continue
            anchors = np.linspace(.42,1,72) if axis=='row' else np.linspace(0,1,81)
            points = []
            for k in range(len(anchors)):
                if not valid[k]:
                    continue
                center = int(locations[:,k].argmax())
                indices = torch.arange(max(0,center-1),min(locations.shape[0],center+2))
                value = float((locations[indices,k].softmax(0)*indices).sum()+.5)/(locations.shape[0]-1)
                x,y = (value,anchors[k]) if axis=='row' else (anchors[k],value)
                if 0<=x<=1 and .42<=y<=1:
                    points.append((y,x))
            if len(points)<8:
                continue
            ys,xs = np.array(points).T
            if np.ptp(ys)<.12:
                continue
            coefficients = np.polyfit(ys,xs,2)
            if np.sqrt(np.mean((np.polyval(coefficients,ys)-xs)**2))>.025:
                continue
            slots[lane] = Boundary(coefficients,float(min(ys)),float(max(ys)))
        return StructuralGeometry(slots)


class HybridLaneDetector:
    """Fuse compatible geometry per vehicle instead of discarding a whole model."""
    def __init__(self, structural_path, segmentation_path, fuse=True):
        from lanes import LaneDetector
        self.structural = StructuralLaneDetector(structural_path)
        self.segmentation = LaneDetector(segmentation_path)
        self.fuse = fuse

    def detect(self, frame):
        geometry = self.structural.detect(frame)
        geometry.source = 'UFLDv2'
        if self.fuse:
            return FusedGeometry(geometry,self.segmentation.detect(frame))
        if geometry.ego_pair is None:
            geometry = self.segmentation.detect(frame)
            geometry.source = 'YOLOP_FALLBACK'
        return geometry


class FusedGeometry:
    def __init__(self, structural, painted):
        self.structural,self.painted = structural,painted
        self.source = 'PER_VEHICLE_FUSION'
        self.ego_pair = structural.ego_pair if structural.ego_pair is not None else painted.ego_pair
        self.boundaries = structural.boundaries if structural.ego_pair is not None else painted.boundaries
        self.compatible = self._compatible()

    def _compatible(self):
        u,s = self.structural,self.painted
        if u.ego_pair is None or s.ego_pair is None:
            return False
        ua,ub=u.slots[1:3]; sa,sb=s.boundaries[s.ego_pair:s.ego_pair+2]
        top=max(ua.top,ub.top,sa.top,sb.top,.65)
        bottom=min(ua.bottom,ub.bottom,sa.bottom,sb.bottom,.9)
        return bottom-top>=.1 and all(abs(ua.x(y)-sa.x(y))<.04 and abs(ub.x(y)-sb.x(y))<.04
                                     for y in np.linspace(top,bottom,5))

    def explain(self, point):
        u,s = self.structural,self.painted
        up,sp = u.assign(point),s.assign(point)
        if up!='UNKNOWN':
            if self.compatible and sp!='UNKNOWN' and up!=sp:
                return {'laneId':'UNKNOWN','reason':'MODEL_DISAGREEMENT','metricEligible':False}
            return {'laneId':up,'reason':'STRUCTURAL_BOUNDARIES','metricEligible':True}
        if sp!='UNKNOWN' and (u.ego_pair is None or self.compatible):
            return {'laneId':sp,'reason':'PAINT_BOUNDARIES_RECOVERY','metricEligible':True}
        extension=self._short_extension(point)
        if extension!='UNKNOWN':
            return {'laneId':extension,'reason':'SHORT_RANGE_SUPPORTED_RECOVERY','metricEligible':False}
        if u.ego_pair is None and s.ego_pair is None:
            reason='EGO_BOUNDARIES_MISSING'
        elif u.ego_pair is not None and not u.valid_pair(1,point[1]):
            reason='OUTSIDE_SUPPORTED_RANGE'
        elif u.side(point)!='UNKNOWN':
            reason='OUTER_BOUNDARY_MISSING'
        else:
            reason='BOUNDARY_AMBIGUOUS'
        return {'laneId':'UNKNOWN','reason':reason,'metricEligible':False}

    def _short_extension(self, point):
        """Provisional ego-only estimate across a small occlusion; never metric evidence."""
        u,s=self.structural,self.painted
        if u.ego_pair is None:
            return 'UNKNOWN'
        a,b=u.slots[1:3]; x,y=point
        gaps=[max(0,boundary.top-y) for boundary in (a,b)]
        if not 0<max(gaps)<=.03 or min(gaps)>.01 or y>=min(a.bottom,b.bottom):
            return 'UNKNOWN'
        if not .025<b.x(y)-a.x(y)<.8 or not 0<=a.x(y)<b.x(y)<=1:
            return 'UNKNOWN'
        # Reject an unstable continuation using the tangent/curve discrepancy.
        for boundary,gap in zip((a,b),gaps):
            tangent=boundary.x(boundary.top)+np.polyval(np.polyder(boundary.coefficients),boundary.top)*(y-boundary.top)
            if gap and abs(tangent-boundary.x(y))>.003:
                return 'UNKNOWN'
        margin=max(.008,(b.x(y)-a.x(y))*.08)
        if not a.x(y)+margin<x<b.x(y)-margin:
            return 'UNKNOWN'
        # At least one actual paint trace must corroborate a structural boundary at this row.
        corroborated=any(p.top-.02<=y<=p.bottom and abs(p.x(y)-edge.x(y))<.015
                         for p in s.boundaries for edge in (a,b))
        return 'EGO' if corroborated else 'UNKNOWN'

    def assign(self, point):
        return self.explain(point)['laneId']

    def side(self, point):
        side=self.structural.side(point)
        if side!='UNKNOWN':
            return side
        s=self.painted
        if s.ego_pair is not None and (self.structural.ego_pair is None or self.compatible):
            a,b=s.boundaries[s.ego_pair:s.ego_pair+2]
            x,y=point
            if s._valid_pair(a,b,y):
                if x<a.x(y)-.008: return 'LEFT_OF_EGO'
                if x>b.x(y)+.008: return 'RIGHT_OF_EGO'
        return 'UNKNOWN'

    def draw(self, frame):
        # Show both evidence sources; painted recovery can reach beyond the structural range.
        return self.structural.draw(self.painted.draw(frame))
