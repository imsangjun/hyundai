"""Apple-inspired editorial re-cut; original evidence remains unmodified."""
from pathlib import Path
import json, subprocess, sys, os
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import imageio_ffmpeg
from build_demo import demo, walk, record

OUT=Path(__file__).resolve().parent/'apple'
OUT.mkdir(exist_ok=True)
W,H,FPS=1920,1080,24
BG='#000000'; CARD='#1F1F21'; WHITE='#FFFFFF'; GRAY='#8B8B91'; BLUE='#4C95F7'
FONT=Path(os.environ.get('PAPERLOGY_FONT_DIR', str(Path.home()/'AppData/Local/Microsoft/Windows/Fonts')))
FONTS={}
def font(size,weight=5):
    key=(size,weight)
    if key not in FONTS:
        name={4:'Regular',5:'Medium',6:'SemiBold',7:'Bold'}[weight]
        FONTS[key]=ImageFont.truetype(str(FONT/f'Paperlogy-{weight}{name}.ttf'),size)
    return FONTS[key]

def lines(text,size,width,weight=5):
    d=ImageDraw.Draw(Image.new('RGB',(1,1)))
    result=[]
    for para in text.split('\n'):
        line=''
        for word in para.split(' '):
            new=(line+' '+word).strip()
            if d.textlength(new,font=font(size,weight))>width and line:
                result.append(line);line=word
            else:line=new
        result.append(line)
    return result

def text(im,value,x,y,size=30,color=WHITE,width=None,weight=5,leading=1.4):
    d=ImageDraw.Draw(im)
    ls=lines(value,size,width,weight) if width else value.split('\n')
    for line in ls:
        d.text((x,y),line,font=font(size,weight),fill=color,anchor='lt')
        y+=round(size*leading)
    return y

TITLES=[
 ['차선변경알리미','기능 소개'],
 ['현재 블록과 다음 블록의','혼잡 상태 비교'],
 ['두 블록 모두 혼잡','현재 블록에서 준비'],
 ['다음 블록은 원활','다음 블록에서 준비'],
 ['좌회전 상황의','차로 변경 준비 안내'],
 ['영상 속 차량 검출과','차로별 밀집 분석'],
 ['정보가 부족한 경우','정체 판단 보류'],
]
WTITLES=[
 ['주행 영상 분석과','앱 연동 시연'],
 ['분석에 사용한','주행 영상'],
 ['YOLO 차량 검출과','BoT-SORT 추적'],
 ['차량의 차로 배정과','밀집 후보 표시'],
 ['두 가지 혼잡 조건에서','앱 안내 비교'],
 ['우회전에서 좌회전으로','설정 변경'],
 ['영상 분석 결과를','앱에서 수신'],
 ['앱에서 받은','데이터 확인'],
 ['테스트한 기능과','아직 확인하지 못한 항목'],
]

# Plain explanatory copy. Keep the original footage and test scope.
DEMO_COPY=[
 (['현재 블록에서 준비','다음 블록에서 준비','경로와 차로별 상태 비교'], '차로 변경을 준비할 구간을 표시해요. 실제 변경 여부는 운전자가 판단해요.'),
 (['현재 블록의 대기열','다음 블록의 혼잡 상태는','이 화면만으로 알 수 없어요.'], '실제 주행 영상이에요. 영상의 위치와 시연 지도는 연결하지 않았어요.'),
 (['현재 블록부터 준비','준비할 구간을','지도에 표시해요.'], '지도·경로·교통 상태·거리 수치는 모두 시연용 가상 데이터예요.'),
 (['현재 교차로를 지난 뒤','다음 블록에서 준비하도록','안내가 바뀌어요.'], '다음 블록에 차로를 변경할 수 있는 구간이 있다고 가정했어요.'),
 (['좌회전 설정','왼쪽 차로를 기준으로','준비 구간을 표시해요.'], '실제 차로 변경 전에는 운전자가 주변 차량과 도로 상황을 확인해야 해요.'),
 (['차량 검출과 추적','차량이 어느 차로에 있는지','차량이 모여 있는지 확인해요.'], '차량 밀집만으로 정체를 확정하지 않아요. 실제 속도와 거리 정보가 더 필요해요.'),
 (['불확실한 차로 배정은 별도 표시','잠정 배정 차량은 정체 계산에서 제외','V2V 통신은 소프트웨어로 재현'], 'Pleos 에뮬레이터에서 테스트했어요. 일반 도로 정확도와 차량 내 실시간 성능은 아직 확인하지 못했어요.'),
]
WALK_COPY=[
 (['원본 영상 확인','차량 검출과 차로별 분석','Pleos 앱 수신 결과 확인'], 'PC에서 분석한 영상과 에뮬레이터 녹화를 편집했어요.'),
 (['왼쪽 차로에 차량이 모인 구간','왼쪽 인접 차로의','차량을 확인해요.'], '분석 전 원본 영상이에요. 촬영 차량의 실제 위치와 속도 정보는 없어요.'),
 (['상자: 검출한 차량','#번호: 추적 ID','소수: 차량 검출 신뢰도'], 'YOLO11s로 검출하고 BoT-SORT로 추적해요. 신뢰도는 차로 배정의 정확도를 뜻하지 않아요.'),
 (['EGO: 내 차로','LEFT_1: 왼쪽 인접 차로','UNKNOWN: 차로 미확정'], '5.7초부터 LEFT_1에 밀집 후보가 표시돼요. 영상이 끝나면 마지막 화면을 유지해요.'),
 (['두 블록 혼잡 → 다음 블록 원활','조건을 바꾸면','준비 안내도 바뀌어요.'], '이 구간은 가상 지도·경로·교통 데이터를 사용한 앱 시연이에요.'),
 (['좌회전으로 설정 변경','왼쪽 차로를 기준으로','안내가 바뀌어요.'], '에뮬레이터에서 앱의 시연 설정을 자동으로 조작해 녹화했어요.'),
 (['PC 분석 결과를 앱에서 재생','V4 → V3 → V2 → V1 → EGO','밀집 후보와 잠정 배정 표시'], '5G NR-V2X PC5를 가정한 소프트웨어 중계예요. 실제 무선 통신은 아니에요.'),
 (['4홉 중계 경로','LEFT_1 밀집 후보','잠정 배정과 속도 미확인'], '같은 데이터를 중계한 차량은 별도 출처로 세지 않아요. 이 시연의 출처는 1개예요.'),
 (['확인: 검출·차로 배정·중계·앱 표시','보류: 실제 속도를 반영한 정체 판단','미확인: 일반 도로 정확도·실시간 성능'], '단일 영상과 거리 보정이 없는 데이터만으로는 미터 단위 준비 지점을 정하지 않아요.'),
]
for scenes,copies in [(demo,DEMO_COPY),(walk,WALK_COPY)]:
    for scene,(body,note) in zip(scenes,copies):
        scene['lines']=body
        scene['subtitle']=note

def icon(im,x,y,kind):
    d=ImageDraw.Draw(im); c=WHITE
    if kind==0:
        d.rounded_rectangle((x,y+8,x+62,y+47),radius=10,outline=c,width=3)
        d.line((x+12,y+8,x+20,y,x+44,y,x+53,y+8),fill=c,width=3)
        d.ellipse((x+9,y+39,x+20,y+50),fill=c);d.ellipse((x+43,y+39,x+54,y+50),fill=c)
    elif kind==1:
        for dx in (0,26,52):d.line((x+dx,y+50,x+dx+12,y),fill=c,width=3)
    else:
        for j in range(3):
            d.ellipse((x+j*23,y+20,x+j*23+14,y+34),outline=c,width=3)
            if j<2:d.line((x+j*23+14,y+27,x+(j+1)*23,y+27),fill=c,width=3)

def layout(s,title,index):
    im=Image.new('RGB',(W,H),BG)
    text(im,'\n'.join(title),120,112,64,weight=7,leading=1.17)
    text(im,s['tag'].replace('MERGEWINDOW · ','차선변경알리미 · '),120,287,27,GRAY)
    d=ImageDraw.Draw(im)
    if s['media']:
        d.rounded_rectangle((120,380,1220,960),radius=30,fill=CARD)
        d.rounded_rectangle((1250,380,1800,960),radius=30,fill=CARD)
        text(im,' / '.join(s['lines'][:1]),1290,425,27,BLUE,width=470,weight=6)
        text(im,'\n'.join(s['lines'][1:]),1290,492,38,width=470,weight=6,leading=1.38)
        note=s['subtitle']
        nlines=lines(note,24,470)
        text(im,note,1290,914-len(nlines)*34,24,GRAY,width=470)
        credit=s['credit'] or ('에뮬레이터 실제 화면' if s['media']==record or s['media'].endswith('.png') else 'PC 사전 분석 결과 재생')
        text(im,credit,150,922,20,GRAY,width=1040)
    else:
        for j,line in enumerate(s['lines']):
            x=120+j*570
            d.rounded_rectangle((x,410,x+540,805),radius=30,fill=CARD)
            icon(im,x+40,453,j)
            text(im,f'{j+1:02}',x+40,542,24,BLUE,weight=6)
            text(im,line,x+40,603,38,width=460,weight=6,leading=1.35)
        text(im,s['subtitle'],120,867,28,GRAY,width=1680)
    return im

def paste_media(im,picture,s):
    if s['media']==record or (s['media'].endswith('.png') and 'close' not in s['media']):
        picture=picture.crop((int(picture.width/3),int(picture.height*.0625),int(picture.width*.99),int(picture.height*.65)))
    fitted=ImageOps.contain(picture,(1060,510),Image.Resampling.LANCZOS)
    mask=Image.new('L',fitted.size,0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,fitted.width,fitted.height),radius=15,fill=255)
    im.paste(fitted,(140+(1060-fitted.width)//2,400+(510-fitted.height)//2),mask)

def render(name,scenes,titles,preview=False):
    proc=None
    if not preview:
        log=(OUT/(name+'.log')).open('w')
        proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-vcodec','rawvideo','-s',f'{W}x{H}','-pix_fmt','rgb24','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/name)],stdin=subprocess.PIPE,stderr=log)
    duration=0
    for i,(s,title) in enumerate(zip(scenes,titles)):
        base=layout(s,title,i);cap=None;still=None;last=None;current=-1
        if s['media']:
            if s['media'].endswith('.png'):still=Image.open(s['media']).convert('RGB')
            else:
                cap=cv2.VideoCapture(s['media']);sfps=cap.get(cv2.CAP_PROP_FPS)
                cap.set(cv2.CAP_PROP_POS_MSEC,s['start']*1000)
        count=round(s['duration']*FPS)
        for k in ([min(72,count//2)] if preview else range(count)):
            im=base.copy();picture=still
            if cap:
                wanted=int(k*sfps/FPS)
                while current<wanted:
                    ok,f=cap.read();current+=1
                    if ok:last=Image.fromarray(cv2.cvtColor(f,cv2.COLOR_BGR2RGB))
                    else:break
                picture=last
            if picture is not None:paste_media(im,picture,s)
            if k==min(72,count//2):im.save(OUT/f'{Path(name).stem}-{i+1:02}.jpg',quality=94)
            if proc:
                # Short fades, with a full-strength reading interval for every card.
                alpha=min(1,k/9,(count-1-k)/9)
                if alpha<1:im=Image.blend(Image.new('RGB',(W,H),BG),im,max(0,alpha))
                proc.stdin.write(im.tobytes())
        if cap:cap.release()
        duration+=count/FPS
        print(name,i+1,'/',len(scenes),flush=True)
    if proc:
        proc.stdin.close();assert proc.wait()==0;log.close()
    return dict(file=name,duration=duration,width=W,height=H,fps=FPS,font='Paperlogy (editorial typography)',scenes=scenes)

if __name__=='__main__':
    preview='--preview' in sys.argv
    manifests=[render('차선변경알리미_애플스타일_기능데모.mp4',demo,TITLES,preview),render('차선변경알리미_애플스타일_상세시연.mp4',walk,WTITLES,preview)]
    (OUT/'manifest.json').write_text(json.dumps(manifests,ensure_ascii=False,indent=2),encoding='utf-8')
    shots=list(OUT.glob('*.jpg'))
    sheet=Image.new('RGB',(960,270*((len(shots)+1)//2)),BG)
    for i,p in enumerate(shots):sheet.paste(Image.open(p).resize((480,270)),((i%2)*480,(i//2)*270))
    sheet.save(OUT/'contact-sheet.png')
