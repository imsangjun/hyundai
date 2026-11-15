"""Reproducible limited visual audit. Unknown predictions count against coverage."""
import json
import argparse
from pathlib import Path
import cv2
import analyze  # Apply the same local runtime settings before importing Ultralytics.
from ultralytics import YOLO
from lanes import LaneDetector


def match_vehicle(label, boxes, height):
    """Full-box labels prevent a nearby foreground car from impersonating a distant bus."""
    if 'referenceBox' in label:
        a=label['referenceBox']
        candidates=[]
        for b in boxes:
            intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
            union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
            iou=intersection/union if union>0 else 0
            if iou>=.35: candidates.append((iou,b))
        return max(candidates,key=lambda p:p[0])[1] if candidates else None
    x,y=label['point']
    candidates=[(abs((b[0]+b[2])/2-x)+abs(b[3]-y),b) for b in boxes
                if b[0]-8<=x<=b[2]+8 and abs(b[3]-y)<=max(15,height*.035)]
    return min(candidates,key=lambda p:p[0])[1] if candidates else None


def run(args):
    import torch
    torch.set_num_threads(4)
    cv2.setNumThreads(4)
    labels = json.loads(Path(args.labels).read_text())
    if args.engine in ('hybrid','hybrid-v1'):
        from structural_lanes import HybridLaneDetector
        lane_model = HybridLaneDetector('.tools/vision-data/culane_res18.pth','.tools/vision-data/yolop-640-640.onnx',fuse=args.engine=='hybrid')
    elif args.engine == 'ufld':
        from structural_lanes import StructuralLaneDetector
        lane_model = StructuralLaneDetector('.tools/vision-data/culane_res18.pth')
    else:
        lane_model = LaneDetector(".tools/vision-data/yolop-640-640.onnx")
    vehicle_model = YOLO(args.model)
    frames, rows = {}, []
    for label in labels["vehicles"]:
        key = label["source"],label["time"]
        if key not in frames:
            capture = cv2.VideoCapture(labels["sources"][key[0]])
            capture.set(cv2.CAP_PROP_POS_MSEC,key[1]*1000)
            ok,frame = capture.read(); capture.release()
            if not ok:
                raise ValueError(f"Missing audit frame {key}")
            geometry = lane_model.detect(frame)
            detection = vehicle_model.predict(frame,classes=[2,3,5,7],conf=.35,imgsz=args.imgsz,device="cpu",verbose=False,
                                              agnostic_nms=args.engine!='hybrid-v1')[0]
            frames[key] = frame,geometry,detection.boxes.xyxy.cpu().tolist()
        frame,geometry,boxes = frames[key]
        x,y = label["point"]
        h,w = frame.shape[:2]
        # Match annotated vehicle ground contact to a nearby detector box's bottom edge.
        box = match_vehicle(label,boxes,h)
        predicted = geometry.assign(((box[0]+box[2])/(2*w),box[3]/h)) if box else "MISSED_VEHICLE"
        coarse = predicted if predicted in ("EGO","UNKNOWN","MISSED_VEHICLE") else "OTHER"
        side = geometry.side(((box[0]+box[2])/(2*w),box[3]/h)) if box and hasattr(geometry,'side') else 'UNKNOWN'
        explanation = geometry.explain(((box[0]+box[2])/(2*w),box[3]/h)) if box and hasattr(geometry,'explain') else {}
        rows.append({**label,"predicted":predicted,"sideEvidence":side,"coarsePrediction":coarse,"correct":coarse==label["expected"],
                     "matchedBox":box,"diagnosis":explanation})
    known = [r for r in rows if r["coarsePrediction"] in ("EGO","OTHER")]
    exact = [r for r in rows if 'exact' in r]
    report = {"method":labels["method"],"engine":args.engine,"model":args.model,"imgsz":args.imgsz,"samples":len(rows),"assigned":len(known),
              "correct":sum(r["correct"] for r in rows),
              "wrong":sum(not r["correct"] for r in known),
              "unknown":sum(r["predicted"]=="UNKNOWN" for r in rows),
              "missedVehicle":sum(r["predicted"]=="MISSED_VEHICLE" for r in rows),
              "assignmentCoverage":len(known)/len(rows),
              "conditionalAccuracy":sum(r["correct"] for r in known)/len(known) if known else None,
              "exactLaneSamples":len(exact),"exactLaneCorrect":sum(r['predicted']==r['exact'] for r in exact),
              "provisionalAssigned":sum(r['predicted'] not in ('UNKNOWN','MISSED_VEHICLE') and r['diagnosis'].get('metricEligible') is False for r in rows),
              "rows":rows,"queueReview":[]}
    # Queue reviews must reference the matching video run explicitly, never an old default run.
    for review in labels["queue_review"] if args.video_results else []:
        frames_data = json.loads(Path(f"{args.video_results}/{review['source']}/lane-analysis.json").read_text())
        window = [f for f in frames_data if review["from"]*1000 <= f["offsetMs"] <= review["to"]*1000]
        states = [lane["state"] for f in window for lane in f["lanes"] if lane["laneId"]==review["lane"]]
        confirmed = sum(s in ("LOW_SPEED_QUEUE","FLOWING_OBSERVED") for s in states)
        report["queueReview"].append({**review,"sampledFrames":len(window),"lanePresentFrames":len(states),
                                      "confirmedDecisions":confirmed,"states":sorted(set(states)),
                                      "verdict":"NOT_VALIDATED_NO_METRIC_GROUND_TRUTH"})
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("rows","queueReview")},indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument('--engine',choices=['yolop','ufld','hybrid','hybrid-v1'],default='hybrid')
    parser.add_argument('--model',default='.tools/vision-data/yolo11s.pt')
    parser.add_argument('--imgsz',type=int,default=1280)
    parser.add_argument('--labels',default='vision/lane-audit-labels.json')
    parser.add_argument('--output',default='verification/improvements/audit.json')
    parser.add_argument('--video-results',help='Matching full-video output root; omit to audit frames only')
    run(parser.parse_args())
