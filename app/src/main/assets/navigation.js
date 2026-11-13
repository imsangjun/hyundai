/* Packaged offline diagram. Android labels explicit demo and live route modes. */
'use strict';
const $=id=>document.getElementById(id);
const initial={connected:false,offline:true,active:false,parked:false,virtual:true,demoDirection:'RIGHT',scenario:'CLEAR',destination:'목적지를 설정해 주세요',turnType:'',turnMeters:null,turnLabel:'',state:'WAITING',title:'연결 대기',detail:'',low:null,high:null,prepareAt:null,events:[],mode:'미수신',eventCount:0};
let state={...initial},follow=true,lastPosition=null,vehicle=null,destination=null,preparation=null,lastStateAt=Date.now();
// CRS.Simple coordinates are diagram units, never latitude/longitude.
const map=L.map('map',{crs:L.CRS.Simple,zoomControl:false,attributionControl:false,minZoom:-1.5,maxZoom:1.5,zoomSnap:.25,maxBounds:[[-700,-1000],[1600,2600]]});
L.imageOverlay('demo-map.svg',[[0,0],[900,1600]],{interactive:false,className:'offline-map-image'}).addTo(map);
map.fitBounds([[0,0],[900,1600]]);
const demoRoute=[[100,930],[500,930],[500,1320]];
const routeHalo=L.polyline(demoRoute,{color:'#ffffff',weight:19,opacity:.95,interactive:false});
const routeLine=L.polyline(demoRoute,{color:'#3979ed',weight:11,interactive:false});
const queueLine=L.polyline([[310,942],[480,942]],{color:'#e9ac4d',weight:7,dashArray:'8 6',interactive:false});
const preparationGuide=L.polyline([],{color:'#147e72',weight:3,dashArray:'4 4',interactive:false});
// Fictional approach-road scale keeps vehicle, queue and preparation marker consistent.
// These are diagram units; the marker is never projected onto a real road.
const diagramScale=280/650;
const approachPoint=(meters,x=930)=>[500-meters*diagramScale,x];
const isLeft=()=>['TURN_LEFT','TURN_SHARP_L'].includes(state.turnType);
const turnName=()=>isLeft()?'좌회전':'우회전';
map.on('dragstart',()=>{follow=false; $('recenter').classList.remove('following')});
const arrowSvg='<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 3 L35 34 L20 27 L5 34 Z" fill="#3576ed" stroke="white" stroke-width="2" stroke-linejoin="round"/></svg>';
function mapStatus(){
  $('map-status').hidden=false;
  $('map-status').textContent='오프라인 시연 지도 · 실제 지형 아님';
}
function toast(message){$('toast').textContent=message;$('toast').hidden=false;setTimeout(()=>$('toast').hidden=true,2200)}
function send(name,value=''){
  if(!state.parked){toast('정차 후 사용할 수 있어요');return}
  if(window.MergeWindow && typeof window.MergeWindow.action==='function') window.MergeWindow.action(name,String(value));
  else toast('Pleos 에뮬레이터에서 사용할 수 있어요');
}
function closePanels(){ $('drawer').hidden=true;$('explanation').hidden=true;$('scrim').hidden=true;document.querySelector('main').inert=false; }
function openPanel(id){if(!state.parked)return;closePanels();$(id).hidden=false;$('scrim').hidden=false;document.querySelector('main').inert=true;$(id).querySelector('.close').focus();}
$('settings').onclick=()=>openPanel('drawer');
$('scrim').onclick=closePanels;
document.querySelectorAll('.close').forEach(b=>b.onclick=closePanels);
document.addEventListener('keydown',e=>{if(e.key==='Escape')closePanels()});
document.querySelectorAll('[data-scenario]').forEach(b=>b.onclick=()=>{send('scenario',b.dataset.scenario);closePanels()});
document.querySelectorAll('[data-direction]').forEach(b=>b.onclick=()=>{send('direction',b.dataset.direction);closePanels()});
$('actual-turn').onchange=e=>send('actual',e.target.checked);
$('offline-demo').onchange=e=>send('offline',e.target.checked);
$('start-example').onclick=()=>{send('start');closePanels();toast('Pleos에서 42dot 경로를 찾고 있어요')};
$('cancel-route').onclick=()=>{send('cancel');closePanels()};
$('reconnect').onclick=()=>send('reconnect');
$('route-action').onclick=()=>openPanel('drawer');
$('zoom-in').onclick=()=>{if(state.parked)map.zoomIn()};
$('zoom-out').onclick=()=>{if(state.parked)map.zoomOut()};
$('recenter').onclick=()=>{if(!state.parked)return;follow=true;centerOn(lastPosition||[220,930])};
$('advisory').onclick=()=>openPanel('explanation');
function centerOn(point){
  // Leave room for the left guidance card: the vehicle remains visible on the map.
  const size=map.getSize(),left=document.querySelector('.guidance-stack').getBoundingClientRect().right;
  const anchor=L.point(Math.max(size.x*.58,left+(size.x-left)*.42),size.y*.56);
  const projected=map.project(point,map.getZoom()).subtract(anchor.subtract(size.divideBy(2)));
  map.panTo(map.unproject(projected,map.getZoom()),{animate:false});
}
function updateMap(){
  const visible=state.active && state.virtual && Number.isFinite(state.turnMeters);
  const left=isLeft(),end=[500,left?610:1320],point=approachPoint(state.turnMeters||0);
  const path=[approachPoint(800),[500,930],end];
  routeHalo.setLatLngs(path);routeLine.setLatLngs(path);
  if(visible){
    if(!vehicle)vehicle=L.marker(point,{icon:L.divIcon({className:'vehicle',html:arrowSvg,iconSize:[46,46],iconAnchor:[23,23]}),interactive:false,zIndexOffset:1000}).addTo(map);
    vehicle.setLatLng(point);
    if(follow && (!lastPosition || lastPosition[0]!==point[0]))centerOn(point);
    lastPosition=point;
  }else{if(vehicle){vehicle.remove();vehicle=null}lastPosition=null}
  if(visible){
    if(!destination)destination=L.marker(end,{icon:L.divIcon({className:'destination-pin',html:'⚑',iconSize:[34,34],iconAnchor:[17,17]}),interactive:false}).addTo(map);
    destination.setLatLng(end);
  }else if(destination){destination.remove();destination=null}
  for(const layer of [routeHalo,routeLine]){if(visible){if(!map.hasLayer(layer))layer.addTo(map)}else layer.remove()}
  const precise=visible && Number.isFinite(state.low) && Number.isFinite(state.high) && Number.isFinite(state.prepareAt) && ['NORMAL','PREPARE','ALTERNATIVE'].includes(state.state);
  if(precise){
    const laneX=left?918:942;
    queueLine.setLatLngs([approachPoint(state.high,laneX),approachPoint(state.low,laneX)]);
    if(!map.hasLayer(queueLine))queueLine.addTo(map);
    preparationGuide.setLatLngs([approachPoint(state.prepareAt,laneX),approachPoint(state.prepareAt,1000)]);
    if(!map.hasLayer(preparationGuide))preparationGuide.addTo(map);
    if(!preparation)preparation=L.marker(approachPoint(state.prepareAt,1000),{icon:L.divIcon({className:'preparation-point',html:'<span>◇</span>',iconSize:[28,28],iconAnchor:[14,14]}),interactive:false,zIndexOffset:900}).bindTooltip('',{permanent:true,direction:'right',offset:[20,0],className:'preparation-label'}).addTo(map);
    preparation.setLatLng(approachPoint(state.prepareAt,1000));
    const remaining=Math.round(state.turnMeters-state.prepareAt);
    const progress=remaining>0?`${remaining} m 앞`:remaining<0?`${Math.abs(remaining)} m 지남`:'준비 기준 도달';
    preparation.setTooltipContent(`${left?'↰ 좌측':'↱ 우측'} 차로 변경 준비 예상<br><b>교차로 전 ${state.prepareAt} m</b> · ${progress}<br><small>가상 기준 · 변경 가능 여부 아님</small>`);
  }else if(preparation){preparation.remove();preparation=null}
  if(!precise){queueLine.remove();preparationGuide.remove()}
  mapStatus();
}
function turn(type){
  if(type.includes('UTURN'))return ['↶','유턴'];
  if(type==='TURN_RIGHT' || type==='TURN_SHARP_R')return ['↱','우회전'];
  if(type==='TURN_LEFT' || type==='TURN_SHARP_L')return ['↰','좌회전'];
  if(type.includes('KEEP_R'))return ['↗','오른쪽 방향'];
  if(type.includes('KEEP_L'))return ['↖','왼쪽 방향'];
  if(type.includes('EXIT'))return ['↗','진출'];
  if(type.includes('ENTER'))return ['↗','진입'];
  if(type.includes('STRAIGHT'))return ['↑','직진'];
  return ['↑','다음 안내'];
}
function render(){
  $('connection').textContent=state.offline?'오프라인 시연':state.connected?'Pleos 연결됨':'Pleos 연결 중';
  $('destination').textContent=state.destination;
  const routeFailed=(state.mode||'').startsWith('경로 요청 오류');
  $('route-status').textContent=state.offline?'가상 경로 · 네트워크 없이 시연':routeFailed?'경로 탐색 실패 · 다시 시도해 주세요':state.active?'Pleos 경로 안내 연결':'시연 설정에서 테스트 경로를 시작하세요';
  $('route-action').innerHTML=state.active?'경로 설정 <span>›</span>':'경로 시작 <span>›</span>';
  const [glyph,label]=turn(state.turnType||'');
  $('turn-arrow').textContent=state.active?glyph:'↗';
  const distance=$('turn-distance'); distance.replaceChildren();
  if(state.active && Number.isFinite(state.turnMeters)){
    const km=state.turnMeters>=1000;
    distance.append(document.createTextNode(km?(state.turnMeters/1000).toFixed(1):String(Math.round(state.turnMeters))));
    const unit=document.createElement('small');unit.textContent=km?'km':'m';distance.append(unit);
  }else distance.textContent=state.active?'안내 대기':'경로 대기';
  $('turn-label').textContent=state.active?(state.turnLabel || label):routeFailed?'경로를 찾지 못했습니다':'목적지를 설정해 주세요';
  $('turn-source').textContent=state.offline?'오프라인 · 지도 / 경로 / 혼잡 가상':state.active?(state.virtual?`Pleos 경로 활성 · ${turnName()} 시연`:'Pleos 실제 회전 · 지도 / 혼잡 가상'):'Pleos 경로와 함께 시작됩니다';
  const show=state.active && ['PREPARE','CAUTION','EXPIRED','ALTERNATIVE'].includes(state.state);
  $('advisory').hidden=!show;$('advisory').className='advisory '+state.state.toLowerCase();
  $('advice-title').textContent=state.title;
  const captions={PREPARE:`앞쪽 ${turnName()} 차로에 대기열이 예상돼요.`,CAUTION:'관측이 부족해 후미 위치를 표시하지 않아요.',EXPIRED:'새 혼잡 정보를 기다리고 있어요.',ALTERNATIVE:'지나쳤다면 기존 경로에서 다음 길을 확인하세요.'};
  $('advice-short').textContent=captions[state.state]||'';
  document.querySelector('.lane-strip').hidden=state.high==null;
  for(const [id,selected,glyph] of [['lane-left',isLeft(),'↰'],['lane-right',!isLeft(),'↱']]){
    const lane=$(id);lane.classList.toggle('turn-lane',selected);lane.firstChild.textContent=selected?glyph:'↑';
  }
  $('normal-chip').hidden=!state.active || !['NORMAL','WAITING'].includes(state.state);
  $('normal-chip').querySelector('span').textContent=state.state==='WAITING'?'다음 회전 정보 확인 중':'추가 준비 안내 없음';
  $('explain-title').textContent=state.title;$('explain-detail').textContent=state.detail;
  $('explain-numbers').textContent=state.low!=null?`가상 대기열 ${state.low}–${state.high} m · 시연 준비 기준 ${state.prepareAt} m`:'';
  $('data-caption').textContent=state.offline?'지도·경로·혼잡은 모두 가상입니다':state.virtual?'지도·회전 거리·혼잡은 가상입니다':'회전 정보는 Pleos · 지도·혼잡은 가상입니다';
  $('diagnostics').textContent=`${state.mode} · ${state.eventCount}건 수신`;
  $('events').textContent=(state.events||[]).join('\n');
  $('actual-turn').checked=!state.virtual;
  $('offline-demo').checked=state.offline;
  document.querySelectorAll('[data-scenario]').forEach(b=>{b.classList.toggle('selected',b.dataset.scenario===state.scenario);b.setAttribute('aria-pressed',String(b.dataset.scenario===state.scenario))});
  $('lock').hidden=state.parked;
  document.querySelectorAll('button,input').forEach(b=>b.disabled=!state.parked);
  document.querySelectorAll('[data-direction]').forEach(b=>{b.disabled=!state.parked || !state.virtual;b.classList.toggle('selected',b.dataset.direction===state.demoDirection);b.setAttribute('aria-pressed',String(b.dataset.direction===state.demoDirection))});
  if(!state.parked)closePanels();
  $('actual-turn').disabled=!state.parked || state.offline;
  $('start-example').disabled=!state.parked || state.offline || !state.connected;
  $('cancel-route').disabled=!state.parked || state.offline || !state.active;
  $('reconnect').disabled=!state.parked || state.offline;
  for(const handler of ['dragging','touchZoom','doubleClickZoom','scrollWheelZoom','boxZoom','keyboard']){if(map[handler])state.parked?map[handler].enable():map[handler].disable()}
  updateMap();
}
window.renderState=s=>{lastStateAt=Date.now();state={...initial,...s};render()};
window.resetNavigation=()=>{state={...initial};render()};
// Fail closed even if the bridge stops delivering updates while the WebView remains visible.
setInterval(()=>{if(Date.now()-lastStateAt>16000 && (state.active || state.connected)){window.resetNavigation()}},1000);
window.addEventListener('resize',()=>{map.invalidateSize();if(follow && lastPosition)centerOn(lastPosition)});
render();
