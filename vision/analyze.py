"""Local YOLO11 + BoT-SORT video analysis, producing the Android replay contract."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

config_directory = Path(__file__).resolve().parent.parent / ".tools/yolo-config"
config_directory.mkdir(parents=True,exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(config_directory))
os.environ.setdefault("YOLO_AUTOINSTALL", "false")

import cv2
import numpy as np
from traffic import QueueJudge, Track, longitudinal_speed
from lanes import LaneDetector
from visual_traffic import VisualDensityJudge


def calibration_at(config, time):
    samples = config.get("calibration", [])
    before = [sample for sample in samples if sample["time_s"] <= time]
    if not before:
        return None
    sample = before[-1]
    if not config.get("fixed_camera", False) and time - sample["time_s"] > 0.5:
        return None
    if config.get("fixed_camera", False) and sample["ego_mps"] != 0:
        raise ValueError("Fixed-camera calibration requires ego_mps=0")
    return sample


def validate_config(config):
    previous_time = -1
    for c in config.get("calibration", []):
        for key in ("time_s", "ego_mps", "junction_m", "error_m", "quality"):
            if not math.isfinite(c[key]):
                raise ValueError(f"Invalid {key}")
        if not (0 <= c["ego_mps"] <= 70 and 0 < c["error_m"] <= 100 and 0 <= c["quality"] <= 1):
            raise ValueError("Invalid calibration range")
        if c["time_s"] < 0 or c["time_s"] <= previous_time or not 0 < c["junction_m"] <= 10000:
            raise ValueError("Calibration times must increase and junction distance must be positive")
        previous_time = c["time_s"]
        if c["block"] not in (0, 1) or c["lane"] not in ("LEFT", "RIGHT"):
            raise ValueError("Invalid lane/block")
        image = np.asarray(c["image_points"], dtype=np.float32)
        ground = np.asarray(c["ground_points"], dtype=np.float32)
        polygon = np.asarray(c.get("lane_polygon", [[0,0],[1,0],[1,1],[0,1]]), dtype=np.float32)
        if image.shape != (4, 2) or ground.shape != (4, 2) or polygon.ndim != 2 or polygon.shape[1] != 2 or len(polygon) < 3:
            raise ValueError("Calibration needs four correspondences and a lane polygon")
        if not all(np.isfinite(a).all() for a in (image, ground, polygon)) or any(np.any(a < 0) or np.any(a > 1) for a in (image, polygon)):
            raise ValueError("Invalid calibration points")
        if abs(cv2.contourArea(image)) < 0.001 or abs(cv2.contourArea(ground)) < 0.01:
            raise ValueError("Degenerate calibration")


def analyze(args):
    import torch
    from ultralytics import YOLO, settings
    torch.set_num_threads(4)
    cv2.setNumThreads(4)
    settings.update({"sync": False})
    source = Path(args.video).resolve(strict=True)
    config = json.loads(Path(args.config).read_text(encoding="utf-8-sig")) if args.config else {}
    validate_config(config)
    with source.open("rb") as video_file:
        digest = hashlib.file_digest(video_file, "sha256").hexdigest()
    origin = "video-" + digest
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(source))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or not math.isfinite(fps) or fps <= 0:
        raise ValueError("Video could not be opened or FPS is unavailable")
    stride = max(1, round(fps / 10))
    model = YOLO(args.model)
    if args.lane_engine == 'hybrid':
        from structural_lanes import HybridLaneDetector
        lane_model = HybridLaneDetector(args.structural_model,args.lane_model)
    else:
        lane_model = LaneDetector(args.lane_model)
    judges, previous, observations = {}, {}, []
    visual_judges = {}
    lane_frames = []
    previous_scene = None
    frame_number, detected_frames, maximum_vehicles = 0, 0, 0
    writer = None
    last_emitted = -1.0
    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            time = frame_number / fps
            frame_number += 1
            if time >= args.seconds:
                break
            if (frame_number - 1) % stride:
                continue
            scene = cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),(64,36))
            cut = previous_scene is not None and np.mean(cv2.absdiff(scene,previous_scene)) > 45
            previous_scene = scene
            if cut:
                previous.clear(); judges.clear(); visual_judges.clear()
                if model.predictor is not None:
                    for tracker in getattr(model.predictor,"trackers",[]):
                        tracker.reset()
            geometry = lane_model.detect(frame)
            result = model.track(frame, persist=True, tracker="botsort.yaml", classes=[2, 3, 5, 7],
                                 conf=0.35, imgsz=args.imgsz, device=args.device, verbose=False,agnostic_nms=True)[0]
            count = len(result.boxes)
            detected_frames += count > 0
            maximum_vehicles = max(maximum_vehicles, count)
            c = calibration_at(config, time)
            assignments = []
            height,width = frame.shape[:2]
            ids = result.boxes.id.int().cpu().tolist() if result.boxes.id is not None else [-1]*count
            for box, track_id, confidence in zip(result.boxes.xyxy.cpu().tolist(), ids, result.boxes.conf.cpu().tolist()):
                point = ((box[0]+box[2])/(2*width),box[3]/height)
                lane_id = geometry.assign(point)
                side = geometry.side(point) if hasattr(geometry,'side') else 'UNKNOWN'
                evidence=geometry.explain(point) if hasattr(geometry,'explain') else dict(
                    laneId=lane_id,reason='PAINT_BOUNDARIES' if lane_id!='UNKNOWN' else 'GEOMETRY_UNAVAILABLE',metricEligible=lane_id!='UNKNOWN')
                assignments.append(dict(id=track_id,box=box,confidence=confidence,sideEvidence=side,**evidence))
            lane_ids = sorted(set(a["laneId"] for a in assignments) | {"EGO"})
            metric_tracks = {lane: [] for lane in lane_ids}
            current = {}
            if c and result.boxes.id is not None:
                matrix = cv2.getPerspectiveTransform(np.float32(c["image_points"]), np.float32(c["ground_points"]))
                if not np.isfinite(matrix).all() or np.linalg.cond(matrix) > 1e8:
                    raise ValueError("Unstable calibration")
                for assignment in assignments:
                    box,track_id,confidence = assignment["box"],assignment["id"],assignment["confidence"]
                    lane_id = assignment["laneId"]
                    point = ((box[0] + box[2]) / (2 * width), box[3] / height)
                    if lane_id == "UNKNOWN" or track_id < 0 or not assignment['metricEligible']:
                        continue
                    projected = cv2.perspectiveTransform(np.float32([[point]]), matrix)[0, 0]
                    distance = float(projected[1])
                    current[track_id] = (time, distance, c["ego_mps"], c["block"], lane_id)
                    old = previous.get(track_id)
                    if old and 0 < time - old[0] <= 0.5 and old[3:] == (c["block"], lane_id):
                        # Straight-road longitudinal model. Ground y is forward distance from camera.
                        speed = longitudinal_speed(distance, old[1], time-old[0], c["ego_mps"], old[2])
                        if speed >= -0.5:
                            metric_tracks[lane_id].append(Track(track_id, distance, max(0, speed), confidence))
            previous = current
            state, camera = "VEHICLES_DETECTED" if count else "INSUFFICIENT_DATA", None
            lane_observations = []
            for lane in lane_ids:
                # Geometry labels are camera-relative. Mapping to a route turn requires explicit metadata.
                is_target = c is not None and lane == c.get("auto_lane", "EGO")
                lane_config = c if c and lane != "UNKNOWN" else None
                if lane_config and not is_target:
                    lane_config = {**c,"tail_visible":False,"full_block_visible":False}
                judge = judges.setdefault(lane, QueueJudge())
                lane_state, lane_camera = judge.evaluate(time, metric_tracks[lane],lane_config)
                visual_state = visual_judges.setdefault(lane,VisualDensityJudge()).evaluate(time,assignments,lane)
                if lane_state == 'INSUFFICIENT_DATA' and visual_state == 'DENSE_TRAFFIC_CANDIDATE':
                    lane_state = visual_state
                lane_observations.append(dict(laneId=lane, vehicleCount=sum(a["laneId"]==lane for a in assignments),
                                              provisionalCount=sum(a['laneId']==lane and not a['metricEligible'] for a in assignments) if lane!='UNKNOWN' else 0,
                                              state=lane_state, speedAvailable=bool(metric_tracks[lane])))
                if is_target:
                    state,camera = lane_state,lane_camera
            if state in ('INSUFFICIENT_DATA','VEHICLES_DETECTED') and any(l['state']=='DENSE_TRAFFIC_CANDIDATE' for l in lane_observations):
                state = 'DENSE_TRAFFIC_CANDIDATE'
            for missing_lane in set(judges)-set(lane_ids):
                judges[missing_lane].evaluate(time,[],None)
                visual_judges[missing_lane].evaluate(time,[],missing_lane)
            if time - last_emitted >= 0.9:
                observations.append({"offsetMs": round(time * 1000), "origin": origin, "node": args.node,
                                     "sequence": len(observations) + 1, "visionState": state,
                                     "vehicleCount": count, "camera": camera, "laneObservations":lane_observations})
                lane_frames.append(dict(offsetMs=round(time*1000), sceneCut=bool(cut), vehicles=assignments,
                                        lanes=lane_observations, laneSource=getattr(geometry,'source','YOLOP'),
                                        egoBoundariesFound=geometry.ego_pair is not None))
                last_emitted = time
            annotated = geometry.draw(result.plot(labels=False,line_width=2))
            for assignment in assignments:
                x1,y1,x2,y2 = assignment["box"]
                label = f"#{assignment['id']} {assignment['laneId']} {assignment['confidence']:.2f}"
                if assignment['laneId']!='UNKNOWN' and not assignment['metricEligible']: label+=' (provisional)'
                cv2.putText(annotated,label,(int(x1),min(height-5,int(y2)+16)),
                            cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,255),1)
            cv2.putText(annotated, f"{time:.1f}s  vehicles={count}  {state}", (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            for i,lane in enumerate(lane_observations):
                label = f"{lane['laneId']}: {lane['vehicleCount']} vehicles | {lane['state']}"
                cv2.putText(annotated,label,(10,52+i*22),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,255,255),1)
            if writer is None:
                h, w = annotated.shape[:2]
                writer = cv2.VideoWriter(str(output / "annotated.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps / stride, (w, h))
                if not writer.isOpened():
                    raise ValueError("Video writer unavailable")
            writer.write(annotated)
    finally:
        cap.release()
        if writer:
            writer.release()
    if not observations:
        raise ValueError("No frames analyzed")
    replay = {"version": 1, "kind": "YOLO_VIDEO", "observations": observations}
    (output / "replay.json").write_text(json.dumps(replay, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    (output / "lane-analysis.json").write_text(json.dumps(lane_frames, allow_nan=False),encoding="utf-8")
    summary = {"model": args.model, "tracker": "BoT-SORT", "videoSha256": digest,
               "detectedFrames": detected_frames, "maximumVehicles": maximum_vehicles,
               "observations": len(observations), "metricObservations": sum(o["camera"] is not None for o in observations),
               "states": sorted(set(o["visionState"] for o in observations))}
    summary["laneModel"] = args.lane_engine
    summary["vehicleImageSize"] = args.imgsz
    summary["assignedVehicleObservations"] = sum(a["laneId"] != "UNKNOWN" for f in lane_frames for a in f["vehicles"])
    summary["totalVehicleObservations"] = sum(len(f["vehicles"]) for f in lane_frames)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--config")
    parser.add_argument("--node", choices=["V1", "V2", "V3", "V4"], default="V4")
    parser.add_argument("--model", default=".tools/vision-data/yolo11s.pt")
    parser.add_argument("--lane-model", default=".tools/vision-data/yolop-640-640.onnx")
    parser.add_argument("--lane-engine", choices=['hybrid','yolop'],default='hybrid')
    parser.add_argument("--structural-model",default='.tools/vision-data/culane_res18.pth')
    parser.add_argument("--imgsz",type=int,choices=[640,960,1280],default=1280)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seconds", type=float, default=60)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 3600:
        parser.error("seconds must be between 0 and 3600")
    analyze(args)
