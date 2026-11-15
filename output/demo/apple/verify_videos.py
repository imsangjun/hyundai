from pathlib import Path
import subprocess,json,cv2,imageio_ffmpeg
from PIL import Image
p=Path(__file__).resolve().parent
results=[]
for item in json.loads((p/'manifest.json').read_text(encoding='utf-8')):
    file=p/item['file']
    check=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(file),'-f','null','-'],capture_output=True)
    assert check.returncode==0 and not check.stderr,check.stderr.decode(errors='replace')
    cap=cv2.VideoCapture(str(file))
    w,h,fps,n=[cap.get(v) for v in [cv2.CAP_PROP_FRAME_WIDTH,cv2.CAP_PROP_FRAME_HEIGHT,cv2.CAP_PROP_FPS,cv2.CAP_PROP_FRAME_COUNT]]
    assert (w,h,fps)==(1920,1080,24)
    assert abs(n/fps-item['duration'])<.05
    # Validate representative full-strength frames in the encoded stream.
    elapsed=0
    for i,s in enumerate(item['scenes']):
        cap.set(cv2.CAP_PROP_POS_MSEC,(elapsed+min(3,s['duration']/2))*1000)
        ok,frame=cap.read();assert ok
        assert frame.mean()>10
        if i==2:Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)).save(p/(file.stem+'-encoded-preview.jpg'))
        elapsed+=round(s['duration']*24)/24
    cap.release()
    results.append(dict(file=file.name,width=w,height=h,fps=fps,duration=n/fps,size=file.stat().st_size,full_decode='passed'))
(p/'verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=True,indent=2))
