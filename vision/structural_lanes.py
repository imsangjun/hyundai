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
    """Use paint segmentation only when structural ego geometry is unavailable."""
    def __init__(self, structural_path, segmentation_path):
        from lanes import LaneDetector
        self.structural = StructuralLaneDetector(structural_path)
        self.segmentation = LaneDetector(segmentation_path)

    def detect(self, frame):
        geometry = self.structural.detect(frame)
        geometry.source = 'UFLDv2'
        if geometry.ego_pair is None:
            geometry = self.segmentation.detect(frame)
            geometry.source = 'YOLOP_FALLBACK'
        return geometry
