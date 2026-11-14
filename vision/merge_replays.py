"""Combine independently recorded sources on an explicitly aligned playback timeline."""
import argparse
import json
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    observations, origins, nodes = [], set(), set()
    for filename in args.inputs:
        replay = json.loads(Path(filename).read_text(encoding="utf-8-sig"))
        if replay["version"] != 1 or replay["kind"] != "YOLO_VIDEO":
            raise ValueError("Unsupported replay")
        new_origins = {o["origin"] for o in replay["observations"]}
        new_nodes = {o["node"] for o in replay["observations"]}
        if origins & new_origins or nodes & new_nodes:
            raise ValueError("Repeated footage or transport node cannot supply independent evidence")
        origins.update(new_origins)
        nodes.update(new_nodes)
        observations.extend(replay["observations"])
    observations.sort(key=lambda o: o["offsetMs"])
    Path(args.output).write_text(json.dumps(dict(version=1, kind="YOLO_VIDEO", observations=observations), allow_nan=False), encoding="utf-8")
