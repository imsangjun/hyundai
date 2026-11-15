# 녹화 영상 → YOLO → V2V → 준비 안내

## 실행 방법

최초 실행에는 uv가 필요하다. Run-Vision.ps1이 프로젝트 .tools 내부에 Python 3.11과 의존성을 설치한다. 추론은 PC에서 실행하고, Android 앱은 관측 결과를 재생한다.

```powershell
.\Run-App.ps1
.\Run-Vision.ps1 -Video 'C:\videos\driving.mp4' -Seconds 60 -InstallReplay
```

앱의 시연 설정에서 ‘YOLO 분석 결과 재생 / 다시 시작’을 누른다. 분석 결과는 기본적으로 verification/vision의 annotated.mp4, summary.json, replay.json에 저장한다. 영상은 로컬에서 처리하며 첫 실행 때 YOLO11n, 공식 YOLOP ONNX, UFLDv2 CULane ResNet18 가중치를 다운로드한다. UFLDv2 가중치는 약 825 MB다. YOLOP는 OpenCV DNN, UFLDv2는 PyTorch CPU로 실행한다. 모델 다운로드 외에 영상·위치를 외부로 전송하지 않는다.

```powershell
# 거리/차로 보정 정보를 함께 사용
.\Run-Vision.ps1 -Video 'C:\videos\driving.mp4' -Config 'C:\videos\calibration.json' -Node V4 -InstallReplay
# 이미 분석한 파일 설치
.\Run-Vision.ps1 -Replay verification/vision-public/replay.json -InstallReplay
```

## 판단 로직

YOLO11n은 입력 크기 960으로 car, motorcycle, bus, truck을 검출하고 BoT-SORT는 ID를 추적한다. UFLDv2가 차선 구조를 추정한다. 존재 점수 0.7, 유효 점 개수·곡선 잔차·교차·폭·범위 검사 후 경계를 사용한다. 내 차로 경계를 확보하지 못한 프레임은 YOLOP 차선·주행 가능 영역 분할로 대체한다. 이 점수는 실제 차로 정답 확률이 아니다. 누락 경계의 슬롯을 유지해 인접 차로 번호가 당겨지지 않게 한다. 좌우 경계가 확인된 영역에 차량 상자 하단 중앙점을 대응한다. EGO는 내 차로, LEFT_1/RIGHT_1은 화면상 인접 차로, UNKNOWN은 차로 미확정이다. 이 표기는 도로의 영구 차로 ID나 회전 전용 여부를 뜻하지 않는다. 경계가 없는 곳, 차선 위, 화면 하단에 잘린 차량은 미확정으로 남긴다.

보정된 지면 좌표의 전방 거리 변화율에 같은 시간의 자차 속도를 더해 차량 종방향 속도를 추정한다. 이 모델은 직선·국소 평면 도로와 정합된 카메라 자세를 전제로 한다. BoT-SORT의 영상 흔들림 보정 자체가 실제 미터 단위 자차 이동 보정은 아니다. 회전·경사·피칭에서는 시간별 보정이 필요하다.

같은 차로에서 속도 5 km/h 이하인 차량 3대 이상이 15 m 이하 간격으로 이어지고, 그 상태가 5초 지속되면 LOW_SPEED_QUEUE로 기록한다. 신호 대기도 포함하는 저속 대기열이며 신호 원인 분류는 구현하지 않았다. 속도 15 km/h 이상인 차량 3대 이상이 5초 유지되면 FLOWING_OBSERVED다. 문턱값은 검증 전의 초기 설정이다.

대기열의 후미가 보이고 거리 보정이 유효할 때에만 교차로까지 거리에서 후미 차량까지 거리를 빼서 후미 구간을 만든다. 가려졌거나 보정이 없으면 camera=null이다. 원활 관측도 전체 해당 블록의 가시 범위가 확인된 경우에만 후미 0으로 전달한다. ‘검출 없음’을 원활로 바꾸지 않는다.

속도 보정이 없어도 같은 확정 차로에서 신뢰도 0.5 이상인 추적 차량 3대가 영상상 가까이 이어지면 밀집 근거를 쌓는다. 하단 접점 간격이 두 상자 평균 높이의 1.5배 이하여야 한다. 최근 5초 이상·30회 이상 관측 중 80% 이상에서 조건을 만족하고 현재도 만족할 때 `DENSE_TRAFFIC_CANDIDATE`를 보낸다. 단위가 픽셀이므로 실제 차간 거리나 정체 확정이 아니다. 0.5초 초과 관측 단절·장면 전환은 이력을 초기화하고 UNKNOWN 차량을 모아 후보를 만들지 않는다. 이 후보는 camera=null이며 수치 안내를 만들지 않는다.

## 보정 JSON 계약

보정값은 영상마다 직접 측정해야 한다. 아래는 구조 설명용 가상 수치이며 공개 예제에 적용하지 않는다.

```json
{
  "fixed_camera": false,
  "calibration": [{
    "time_s": 0.0,
    "image_points": [[0.3,0.9],[0.7,0.9],[0.55,0.5],[0.45,0.5]],
    "ground_points": [[-2,5],[2,5],[2,50],[-2,50]],
    "auto_lane": "EGO",
    "ego_mps": 5.0,
    "junction_m": 100.0,
    "error_m": 5.0,
    "quality": 0.8,
    "block": 1,
    "lane": "RIGHT",
    "tail_visible": false,
    "full_block_visible": false
  }]
}
```

image_points는 영상 너비·높이에 대한 0~1 좌표다. 차로 영역은 모델이 자동으로 인식한다. auto_lane은 실제 경로의 관심 차로에 대응시킬 카메라 상대 차로를 명시한다. ground_points는 대응하는 지면의 (가로 m, 카메라 전방 m) 좌표다. junction_m은 해당 시각의 카메라에서 교차로까지 전방 거리다. block=0은 이번 블록, 1은 다음 블록이다. quality와 error_m은 검출 점수와 별개인 외부 보정 품질과 거리 오차다.

움직이는 카메라의 보정 샘플은 시각순으로 제공하고 0.5초가 지나면 사용하지 않는다. 회전 방향과 실제 경로 차로의 대응은 외부 설정이다. GPS 차로 매칭·깊이 모델은 구현하지 않았다. 자동 차선 인식만으로 실제 거리와 속도를 알 수 없으므로 미터 단위 보정과 자차 속도는 계속 필요하다. 고정 카메라는 fixed_camera=true와 ego_mps=0으로 정적인 보정을 사용할 수 있다. 관측이 끊기거나 차로가 바뀌면 지속 시간 판정을 다시 시작한다.

## V2V 연결

replay.json의 origin은 입력 영상 SHA-256이다. 한 영상의 차량 검출 10개를 독립 관측 차량 10대로 취급하지 않는다. 앱은 합성 발신을 끄고 영상 발신만 기존 최대 4홉 네트워크에 넣는다. 재생 시작 때 영상 시각을 단조 시계에 한 번 대응하고, 종료 후에는 원래 시각을 유지한 채 12초 만료 규칙을 적용한다. null 관측도 전송해 이전 유효 관측을 갱신한다.

기존 안내는 각 블록에 유효한 독립 출처 2대가 있어야 수치 준비 지점을 표시한다. 단일 영상은 차로별 차량 검출·대기열 판단·송수신 상태를 볼 수 있고, 다중 출처 조건이 부족하면 준비 지점을 숨긴다. 두 블록 수치 안내는 같은 시각과 도로 기준에 맞춘 독립 녹화 4개를 각각 V1~V4로 분석해서 합칠 수 있다.

```powershell
.tools/vision-env/Scripts/python.exe vision/merge_replays.py a/replay.json b/replay.json c/replay.json d/replay.json --output verification/combined.json
.\Run-Vision.ps1 -Replay verification/combined.json -InstallReplay
```

입력 영상의 시작 시각은 미리 동기화해야 한다. 같은 영상의 해시나 동일 전송 노드를 중복 지정하면 거부한다. 영상 재인코딩에 대한 출처 인증은 없으므로 실제 배포에는 차량 인증이 필요하다. V1~V4 위치와 지도 경로는 시연용이며 영상의 실제 도로 위치로 자동 매핑하지 않는다.

## 검증 범위와 자료

2026-11-15 Ultralytics 공개 주행 예제 kitti-inference-vid.mp4로 YOLO11n/BoT-SORT를 실행했다. 검출 프레임 166개, 프레임당 최대 차량 10대, 관측 메시지 18개를 생성했다. 거리/차로/자차 속도 보정이 없어 metricObservations=0, VEHICLES_DETECTED로 출력됐다. 공개 예제에는 기존 추론 시각화가 포함될 수 있어 정확도 평가용 데이터셋으로 사용하지 않았다.

정체 판정·자차 속도 보정·후미 가림·관측 단절은 Python 결정론 테스트로 검증한다. Android의 보정 관측 → 중계 → 두 블록 준비 전환은 합성 계약 테스트로 검증하며 실제 도로 정답 대비 성능 검증은 남아 있다.

- 모델/추적 API https://docs.ultralytics.com/modes/track/
- 설치 https://docs.ultralytics.com/quickstart/
- 공개 영상 https://github.com/ultralytics/assets/releases/download/v0.0.0/kitti-inference-vid.mp4
- Ultralytics 라이선스 https://www.ultralytics.com/license

최종 확인에서 Python 판정 테스트 6개, Android 영상 재생·중계·안내 계약 테스트 3개가 통과했다. 공개 영상의 실제 분석 파일을 운전자 프로필 10에 설치해 화면 브리지까지 수신을 확인했다. 설치 스크립트는 현재 활성 운전자 프로필을 자동 조회한다. 기존 Kotlin 단위 테스트 19개 및 V2V 시연 화면 테스트도 통과했다.

## 자동 차로 분석 결과

lane-analysis.json에는 매 관측 시점의 차량 상자, 추적 ID, 자동 차로 배정, 차로별 차량 수·판단 상태가 담긴다. replay.json의 laneObservations로 이 결과를 V2V 중계하고 앱 수신 기록에서 확인할 수 있다. 구형 replay.json도 계속 읽는다. 모든 관측 차로에서 속도 보정이 있으면 대기열 상태를 계산하고, auto_lane으로 지정한 차로만 기존 회전 안내의 후미 구간에 대응한다.

정확도 검증의 범위와 결과는 LANE_VALIDATION.md를 참고한다. 공개 영상에는 동기화된 자차 속도와 실제 거리 정답이 없어 실제 km/h 기반 정체 정확도는 아직 검증하지 못했다.

- YOLOP 공식 모델 및 코드 https://github.com/hustvl/YOLOP
- 추가 실제 주행 영상 https://github.com/hustvl/YOLOP/blob/main/inference/videos/1.mp4

## 2026-11-15 개선 검증

최신 비교는 [IMPROVEMENT_RESULTS.md](IMPROVEMENT_RESULTS.md)에 기록했다. 기존 결과 문서는 YOLOP 단독 기준선이다. 개선된 혼잡 영상 재생 파일은 `verification/improvements/continuous/replay.json`이다. 앱 화면 검사는 이 파일을 설치한 뒤 실행한다.

- UFLDv2 공식 소스·모델: https://github.com/cfzd/Ultra-Fast-Lane-Detection-v2
- 추론부 MIT 고지: [THIRD_PARTY_UFLD_LICENSE.txt](THIRD_PARTY_UFLD_LICENSE.txt)
