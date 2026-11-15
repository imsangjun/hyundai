from pathlib import Path
import subprocess,cv2,numpy as np,json
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'output/demo'; FPS=24; W,H=1280,720
font=lambda size,bold=False:ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf' if bold else 'C:/Windows/Fonts/malgun.ttf',size)
BG='#0B1423';INK='#F3F7FC';MUTED='#B2C2D4';ACC='#58E0BF'
F={s:font(s) for s in [16,19,22,26,32]};B={s:font(s,True) for s in [24,28,38,50]}
def wrap(d,text,f,width):
 lines=[];line=''
 for char in text:
  if char=='\n':lines.append(line);line='';continue
  if d.textlength(line+char,font=f)>width:lines.append(line);line=char
  else:line+=char
 if line:lines.append(line)
 return lines

def slide(title,tag,lines,media=None,start=0,duration=7,credit='',subtitle=''):
 return dict(title=title,tag=tag,lines=lines,media=media,start=start,duration=duration,credit=credit,subtitle=subtitle)
raw=str(ROOT/'.tools/vision-data/yolop-driving.mp4');analysis=str(ROOT/'verification/refinement/continuous/annotated.mp4')
shot=lambda name:str(OUT/f'demo-{name}.png')
record=str(OUT/'pleos_capture.mp4')
demo=[
 slide('차선변경알리미','MERGEWINDOW · 기능 데모',['지금 준비할까?','다음 블록에서 준비할까?','경로와 차로별 관측을 함께 보는 준비 안내'],duration=6,subtitle='차로 변경을 명령하지 않고, 준비할 구간을 이해하도록 돕습니다.'),
 slide('같은 정체, 다른 준비 시점','문제 정의',['현재 블록만 봐서는','다음 회전 차로의 대기열을','알기 어렵습니다.'],raw,duration=8,credit='영상 출처: YOLOP 공식 예제 · 1.mp4',subtitle='실제 주행 영상 예시 · 이 영상의 위치를 시연 지도와 연결한 것은 아닙니다.'),
 slide('상황 1 · 두 블록 모두 혼잡','가상 시나리오 / 실제 앱 화면',['현재 블록부터','미리 준비할 구간을','지도에 표시합니다.'],shot('both'),duration=8,subtitle='지도·경로·교통 상태와 거리 수치는 시연용 가상 데이터입니다.'),
 slide('상황 2 · 다음 블록은 원활','가상 시나리오 / 실제 앱 화면',['현재 교차로를 지난 뒤','다음 블록에서 준비하는','안내로 바뀝니다.'],shot('next'),duration=8,subtitle='차로 연결과 변경 가능한 구간이 있다는 가정 아래 비교합니다.'),
 slide('좌회전도 같은 원리','가상 시나리오 / 실제 앱 화면',['회전 방향을 바꾸면','준비 안내도','왼쪽 차로 기준으로 전환됩니다.'],shot('left'),duration=7,subtitle='주변 차량 확인과 실제 차로 변경 판단은 운전자가 수행합니다.'),
 slide('영상에서 차로별 관측으로','실제 녹화 영상 / PC 분석',['차량 검출 + 추적','차선 경계와 차로 배정','왼쪽 차로의 밀집 후보'],analysis,duration=8.9,credit='YOLO11s + BoT-SORT / UFLDv2 + YOLOP',subtitle='밀집 후보는 저속 정체 확정이 아닙니다. 실제 속도·거리 보정이 필요합니다.'),
 slide('근거가 부족하면 판단 보류','구현 범위',['잠정 배정은 별도로 표시','잠정 차량은 정체 계산에서 제외','실제 무선 V2V는 시뮬레이션'],duration=7,subtitle='Pleos 에뮬레이터 구현 · 실제 도로 정확도와 차량 내 실시간 성능은 검증 전입니다.'),
]
walk=[
 slide('원본부터 앱 수신까지','MERGEWINDOW · 실제 동작 시연',['01 원본 영상','02 검출·차로·밀집 후보','03 Pleos 앱과 V2V 시뮬레이션'],duration=6,subtitle='한국어 자막 시연 · PC 영상 분석과 에뮬레이터 실행을 편집했습니다.'),
 slide('01  입력 영상','공개 주행 영상 · 8.9초',['차량이 줄지어 있는','왼쪽 인접 차로를','관찰합니다.'],raw,duration=8.9,credit='출처: github.com/hustvl/YOLOP / inference/videos/1.mp4',subtitle='모델 출력 전 원본입니다. 촬영 차량의 실제 위치·속도 정보는 없습니다.'),
 slide('02  YOLO 차량 검출','녹화 영상 분석 · 실시간 추론 아님',['상자: 검출 차량','#번호: 추적 ID','소수: 차량 검출 신뢰도'],analysis,duration=8.9,subtitle='YOLO11s가 검출하고 BoT-SORT가 추적합니다. 숫자는 차로 판단의 정답 확률이 아닙니다.'),
 slide('03  차로와 밀집 후보','분석 결과 설명',['EGO: 내 차로','LEFT_1: 왼쪽 인접 차로','UNKNOWN: 차로 미확정'],analysis,start=5.7,duration=7,subtitle='5.7초부터 LEFT_1 밀집 후보 표시 · 구간 끝은 정지 화면으로 유지합니다.'),
 slide('04  두 블록 비교','PLEOS 에뮬레이터 실제 녹화',['두 블록 혼잡 →','다음 블록 원활','준비 안내의 변화 확인'],record,start=2,duration=14,subtitle='이 구간은 가상 지도·경로·교통 데이터를 이용한 앱 기능 시연입니다.'),
 slide('05  좌회전으로 전환','PLEOS 에뮬레이터 실제 녹화',['좌회전에서도','동일한 준비 원리를','적용합니다.'],record,start=16,duration=7,subtitle='앱의 시연 설정을 자동 조작한 화면 녹화입니다.'),
 slide('06  영상 관측을 앱으로','PLEOS 에뮬레이터 실제 녹화',['PC 분석 JSON 재생','V4 → V3 → V2 → V1 → EGO','밀집 후보·잠정 배정 표시'],record,start=23,duration=13,subtitle='5G NR-V2X PC5를 가정한 소프트웨어 중계입니다. 실제 무선 통신은 아닙니다.'),
 slide('수신 기록 확대','실제 앱 캡처 · 확대 정지 화면',['4홉 중계 경로','LEFT_1 밀집 후보','잠정 배정과 속도 미확인'],shot('vision-close'),duration=8,subtitle='중계 차량 수를 독립 관측 수로 세지 않습니다. 유효 출처는 이 시연에서 1개입니다.'),
 slide('확인한 것과 남은 것','검증 범위',['확인: 검출·차로 배정·중계·앱 표시','보류: 실제 속도 기반 정체 확정','미검증: 일반 도로 정확도·실시간 성능'],duration=8,subtitle='단일 영상과 미보정 관측만으로 미터 단위 준비 지점을 만들지 않습니다.'),
]
def make(name,scenes):
 total=sum(s['duration'] for s in scenes);elapsed=0
 args=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-vcodec','rawvideo','-s',f'{W}x{H}','-pix_fmt','rgb24','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/name)]
 with (OUT/(name+'.log')).open('w') as log:
  proc=subprocess.Popen(args,stdin=subprocess.PIPE,stderr=log)
  for index,s in enumerate(scenes):
   base=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(base)
   d.text((40,24),s['tag'],font=F[19],fill=ACC);d.text((40,55),s['title'],font=B[38],fill=INK)
   d.line((40,115,1240,115),fill='#29415A',width=2)
   media=s['media'];cap=None;still=None
   if media:
    if media.endswith('.png'):still=Image.open(media).convert('RGB')
    else:
     cap=cv2.VideoCapture(media);cap.set(cv2.CAP_PROP_POS_MSEC,s['start']*1000)
     source_fps=cap.get(cv2.CAP_PROP_FPS);current_index=-1;last=None
    x,y,boxw,boxh=40,140,870,440
    d.rounded_rectangle((925,140,1240,580),radius=16,fill='#13243A')
    ty=168
    for line in s['lines']:
     for part in wrap(d,line,F[22],280):d.text((945,ty),part,font=F[22],fill=INK);ty+=34
     ty+=18
   else:
    y=190
    for j,line in enumerate(s['lines']):
     d.text((65,y),f'{j+1:02}',font=B[28],fill=ACC)
     for part in wrap(d,line,B[28],1050):d.text((140,y),part,font=B[28],fill=INK);y+=45
     y+=28
   d.text((40,590),s['credit'],font=F[16],fill=MUTED)
   for k,line in enumerate(wrap(d,s['subtitle'],F[22],1190)):d.text((40,623+k*30),line,font=F[22],fill=INK)
   d.text((1170,28),f'{index+1:02}/{len(scenes):02}',font=F[19],fill=MUTED)
   for frame_index in range(round(s['duration']*FPS)):
    image=base.copy()
    if media:
     picture=still
     if cap:
      wanted=int(frame_index*source_fps/FPS)
      while current_index<wanted:
       ok,f=cap.read();current_index+=1
       if ok:last=Image.fromarray(cv2.cvtColor(f,cv2.COLOR_BGR2RGB))
       else:break
      picture=last
     if picture is not None:
      fitted=picture.copy()
      if media==record or (media.endswith('.png') and 'close' not in media): fitted=fitted.crop((int(fitted.width/3),int(fitted.height*.0625),int(fitted.width*.99),int(fitted.height*.65)))
      fitted.thumbnail((boxw,boxh),Image.Resampling.LANCZOS)
      image.paste(fitted,(x+(boxw-fitted.width)//2,y+(boxh-fitted.height)//2))
    draw=ImageDraw.Draw(image);draw.rectangle((0,710,int(W*(elapsed+frame_index/FPS)/total),719),fill=ACC)
    proc.stdin.write(np.asarray(image).tobytes())
    if frame_index==int(min(3,s['duration']/2)*FPS):image.save(OUT/f'{Path(name).stem}-scene{index+1}.jpg')
   if cap:cap.release()
   elapsed+=s['duration'];print(name,index+1,'/',len(scenes),flush=True)
  proc.stdin.close();assert proc.wait()==0
 return {'file':name,'duration':total,'scenes':scenes}
if __name__=='__main__':
 manifest=[make('차선변경알리미_기능데모.mp4',demo),make('차선변경알리미_분석과앱_시연.mp4',walk)]
 (OUT/'video_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
