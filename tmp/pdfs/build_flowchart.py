from pathlib import Path
from math import atan2, cos, sin, pi
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/pdf/MergeWindow_Lane_Preparation_Flowchart.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('KR', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KRB', 'C:/Windows/Fonts/malgunbd.ttf'))
W,H=A4
NAVY='#183541'; TEAL='#137F70'; MUTE='#647A80'; LINE='#839B9F'
PALE='#EDF7F3'; GOLD='#FFF5DF'; GREY='#F1F4F5'; RED='#FBECE5'
c=canvas.Canvas(str(OUT),pagesize=A4)
c.setTitle('MergeWindow 차로 준비 예측 로직 플로우차트')
c.setAuthor('MergeWindow')
c.setSubject('좌·우회전 준비 기준과 오프라인 예상 지점 표시 - 구현 기준 122edbe')

def txt(x,y,s,size=10,color=NAVY,bold=False,align='left'):
    c.setFillColor(HexColor(color));c.setFont('KRB' if bold else 'KR',size)
    fn={'left':c.drawString,'center':c.drawCentredString,'right':c.drawRightString}[align]
    fn(x,H-y,s)

def lines(x,y,ss,size=11,leading=18,align='center',bold=False,color=NAVY):
    for i,s in enumerate(ss):txt(x,y+i*leading,s,size,color,bold,align)

def box(x,y,w,h,ss,fill=PALE,size=11,bold=False,stroke='#C5DCD4'):
    c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(stroke));c.setLineWidth(.8)
    c.roundRect(x,H-y-h,w,h,10,fill=1,stroke=1)
    lead=size*1.55
    for s in ss:
        assert pdfmetrics.stringWidth(s,'KRB' if bold else 'KR',size) < w-14,(s,w)
    lines(x+w/2,y+(h-(len(ss)-1)*lead)/2+size*.33,ss,size,lead,bold=bold)

def diamond(x,y,w,h,ss,size=10.5):
    p=c.beginPath();p.moveTo(x+w/2,H-y);p.lineTo(x+w,H-y-h/2);p.lineTo(x+w/2,H-y-h);p.lineTo(x,H-y-h/2);p.close()
    c.setFillColor(HexColor(GOLD));c.setStrokeColor(HexColor('#DFCAA3'));c.setLineWidth(.9);c.drawPath(p,stroke=1,fill=1)
    lead=16
    lines(x+w/2,y+h/2-(len(ss)-1)*lead/2+3.3,ss,size,lead,bold=True)

def arrow(points,label=None,lx=None,ly=None,color=LINE):
    c.setStrokeColor(HexColor(color));c.setFillColor(HexColor(color));c.setLineWidth(1.2)
    p=c.beginPath();p.moveTo(points[0][0],H-points[0][1])
    for x,y in points[1:]:p.lineTo(x,H-y)
    c.drawPath(p)
    x,y=points[-1];px,py=points[-2];a=atan2(y-py,x-px)
    q=c.beginPath();q.moveTo(x,H-y)
    for d in [-.45,.45]:q.lineTo(x-6*cos(a+d),H-(y-6*sin(a+d)))
    q.close();c.drawPath(q,fill=1,stroke=0)
    if label:txt(lx,ly,label,9,TEAL,True)

def header(n,title,subtitle):
    c.setFillColor(HexColor('#F8FAF9'));c.rect(0,0,W,H,fill=1,stroke=0)
    txt(40,40,'MERGEWINDOW  /  LOGIC FLOW',10,TEAL,True)
    txt(40,77,title,24,NAVY,True)
    txt(40,99,subtitle,10,MUTE)
    c.setStrokeColor(HexColor('#DCE5E2'));c.line(40,H-790,W-40,H-790)
    txt(40,808,'구현 기준 122edbe  |  2026-11-13  |  정차·가상 혼잡 시연',8,MUTE)
    txt(W-40,808,f'{n} / 3',9,TEAL,True,'right')

def note(y,ss):
    lines(40,y,ss,9,15,'left',color=MUTE)

# PAGE 1: input provenance and validation
header(1,'입력 선택과 유효성 검사','차로 준비 예측은 현재 규칙 기반 시연 로직입니다. 학습된 혼잡 예측 모델이 아닙니다.')
box(40,124,165,92,['오프라인 시연','가상 활성 경로','선택한 좌·우회전 / D','혼잡 시나리오'],size=10)
box(215,124,165,92,['Pleos + 가상 회전','실제 경로 활성 상태','선택한 좌·우회전 / D','혼잡 시나리오'],size=10)
box(390,124,165,92,['Pleos + 실제 회전','실제 경로 활성 상태','다음 TBT 방향 / D','혼잡 시나리오'],size=10)
for x in [122.5,297.5,472.5]:arrow([(x,216),(x,232),(195,232),(195,252)])
diamond(65,252,260,82,['차량·경로 사용 가능?','① 정차 허용  ② 연결됨','③ 상태 최신  ④ 활성 경로'],10)
arrow([(325,293),(384,293)],'실패',341,285)
box(384,245,171,151,['검사 순서대로 즉시 반환','① 아니오: RESTRICTED','② 아니오: WAITING','③ 아니오: EXPIRED','④ 아니오: WAITING','정밀 준비 지점 없음'],GREY,9.4)
arrow([(195,334),(195,382)],'모두 통과',205,360)
diamond(65,382,260,64,['가상 회전을 사용하는가?'])
arrow([(195,446),(195,465),(150,465),(150,492)],'예',154,460)
arrow([(325,414),(355,414),(355,465),(445,465),(445,492)],'아니오',365,455)
box(40,492,220,115,['가상 입력 사용','사용자가 선택한 LEFT / RIGHT','D = 시나리오의 회전 거리','650 m 또는 350 m'],size=10.6)
box(335,492,220,115,['실제 TBT 검사 후 사용','① 수신 후 15초 이내','② 좌·우회전 또는 급좌·우회전','③ 유한 거리, 0~100,000 m','D = 정수로 변환한 거리'],size=10)
arrow([(150,607),(150,635),(297.5,635),(297.5,659)])
arrow([(445,607),(445,635),(297.5,635),(297.5,659)],'검사 통과',449,628)
box(167.5,659,260,44,['방향·거리 D 확정 → 2페이지'],PALE,12,True)
note(729,['상태 최신 조건: 0 ≤ 현재 시각 - 수신 시각 ≤ 15초. 미래 시각도 무효입니다.',
          '실제 TBT 검사 실패: ①·③ WAITING / ② NORMAL로 반환하며 정밀 준비 지점을 만들지 않습니다.',
          '좌·우회전 이외 직진·유턴 등은 제외합니다. 혼잡 데이터는 모든 모드에서 가상입니다.'])
c.showPage()

# PAGE 2: decision tree, matching GuidanceEngine order
header(2,'준비 기준 계산과 안내 상태 결정','좌회전과 우회전은 같은 수식을 사용하며, 안내하는 차로 방향만 달라집니다.')
box(40,122,515,63,['D: 회전까지 거리   L/U: 가상 대기열 하한/상한   P: 준비 기준 거리',
                     'R: 시나리오의 혼잡 위험 여부   |   거리 단위: m'],GREY,10.2)
box(40,205,280,35,['1페이지에서 확정한 방향·거리 입력'],PALE,10.5)
arrow([(180,240),(180,258)])
diamond(40,258,280,60,['혼잡 관측이 12초 이내인가?'])
arrow([(320,288),(385,288)],'아니오',330,279)
box(385,258,170,62,['EXPIRED','새 관측 대기','대기열·예상 지점 숨김'],GREY,10)
arrow([(180,318),(180,349)],'예',190,338)
diamond(40,349,280,60,['하한 L과 상한 U가 있는가?'])
arrow([(320,379),(385,379)],'아니오',330,370)
box(385,349,170,62,['CAUTION','회전 차로 혼잡 가능성','정확한 후미·지점 미표시'],GOLD,10)
arrow([(180,409),(180,440)],'예',190,430)
box(40,440,280,52,['준비 기준 P = U + 150 m','150 m는 시연용 준비 여유'],PALE,11,True)
arrow([(180,492),(180,523)])
diamond(40,523,280,60,['R = 참 AND D ≤ U ?'])
arrow([(320,553),(385,553)],'예',342,544)
box(385,522,170,64,['ALTERNATIVE','가상 후미 구간에 도달','무리한 차선 변경 회피'],RED,10)
arrow([(180,583),(180,612)],'아니오',190,602)
diamond(40,612,280,60,['R = 참 AND D ≤ P ?'])
arrow([(320,642),(385,642)],'예',342,633)
box(385,610,170,66,['PREPARE','좌회전: 좌측 차로 준비','우회전: 우측 차로 준비'],PALE,10)
arrow([(180,672),(180,707)],'아니오',190,692)
box(40,707,280,42,['NORMAL  |  추가 준비 안내 없음'],GREY,10.5,True)
note(770,['판정 순서: 후미 도달 → 준비 구간 → 일반. 결과는 3페이지의 지도 표시 조건으로 전달됩니다.'])
c.showPage()

# PAGE 3: renderer gate and demonstrations
header(3,'지도 예상 지점 표시와 시연 예시','표시 지점은 가상 도로 위 준비 기준입니다. 실제 차선 변경 가능 지점의 판단은 포함하지 않습니다.')
diamond(40,127,280,70,['활성 경로 + 가상 회전 모드','+ 유한한 회전 거리 D ?'],10)
arrow([(320,162),(385,162)],'아니오',330,153)
box(385,127,170,70,['가상 경로·차량 숨김','예상 지점도 숨김','실제 TBT 모드 포함'],GREY,10)
arrow([(180,197),(180,230)],'예',190,217)
diamond(40,230,280,76,['L / U / P 모두 유한값이고','NORMAL · PREPARE','· ALTERNATIVE 중 하나인가?'],10)
arrow([(320,268),(385,268)],'아니오',330,259)
box(385,232,170,72,['대기열·예상 지점 숨김','관측 부족 / 만료 / 대기','가상 기본 경로는 유지'],GREY,9.6)
arrow([(180,306),(180,339)],'예',190,326)
box(40,339,280,62,['선택한 방향의 차로에 대기열 표시','교차로 전 P m에 준비 기준 표시','좌회전은 좌측 / 우회전은 우측'],PALE,10.2)
arrow([(180,401),(180,433)])
box(40,433,280,62,['남은 거리 Δ = 반올림(D - P)','Δ > 0: 앞 / Δ = 0: 기준 도달','Δ < 0: 절댓값만큼 지남'],PALE,10.5)
box(385,350,170,134,['혼잡 시연 계산 예','U = 520 m','P = 520 + 150 = 670 m','D = 650 m → Δ = -20 m','“교차로 전 670 m”','“20 m 지남”'],GOLD,9.4)
txt(40,535,'동일한 거리·혼잡 입력이면 좌·우회전의 판정 결과는 같습니다.',11,NAVY,True)
cols=[40,155,220,303,414,555]
headers=['상황','D','대기열 L~U','결과','지도 준비 기준']
rows=[['원활','650','60~120','NORMAL','270 m / 380 m 앞'],
      ['혼잡','650','430~520','PREPARE','670 m / 20 m 지남'],
      ['관측 부족','650','없음','CAUTION','숨김'],
      ['데이터 만료','650','무효','EXPIRED','숨김'],
      ['진입 기회 상실','350','430~520','ALTERNATIVE','670 m / 320 m 지남']]
for rownum,row in enumerate([headers]+rows):
    y=551+rownum*27
    c.setFillColor(HexColor(NAVY if rownum==0 else '#FFFFFF' if rownum%2 else '#EEF4F1'))
    c.rect(40,H-y-27,515,27,fill=1,stroke=0)
    for j,s in enumerate(row):
        txt(cols[j]+8,y+18,s,8.6,'#FFFFFF' if rownum==0 else NAVY,rownum==0)
note(737,['구현 출처: GuidanceEngine.kt / MainActivity.kt / assets/navigation.js',
          '가상 관측은 매초 갱신하며, 만료 시나리오는 갱신하지 않습니다. 원활 시나리오만 R = 거짓입니다.',
          '시연 지도는 평면 도식이며 실제 위치·도로 경로로 투영하지 않습니다. 외부 지도 요청은 없습니다.'])
c.linkURL('https://github.com/imsangjun/hyundai/tree/122edbeabd90a8acfa8502647a9a6731ae30cc65',
          (40,H-743,555,H-726),relative=0,thickness=0)
c.save()
reader=PdfReader(str(OUT))
assert len(reader.pages)==3
text='\n'.join(p.extract_text() for p in reader.pages)
for token in ['좌회전','우회전','150','670','ALTERNATIVE','RESTRICTED','270']:
    assert token in text,token
print(str(OUT))
print(f'Pages: {len(reader.pages)}, bytes: {OUT.stat().st_size}')
