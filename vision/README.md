# 녹화 영상 → YOLO → V2V → 준비 안내

## 실행 방법

최초 실행에는 uv가 필요하다. Run-Vision.ps1이 프로젝트 .tools 내부에 Python 3.11과 의존성을 설치한다. 추론은 PC에서 실행하고, Android 앱은 관측 결과를 재생한다.

```powershell
.\Run-App.ps1
.\Run-Vision.ps1 -Video 'C:\videos\driving.mp4' -Seconds 60 -InstallReplay
```

앱의 시연 설정에서 ‘YOLO 분석 결과 재생 / 다시 시작’을 누른다. 분석 결과는 기본적으로 verification/vision의 annotated.mp4, summary.json, replay.json에 저장한다. 영상은 로컬에서 처리하며 첫 실행 때 모델 가중치를 다운로드한다.

```powershell
# 거리/차로 보정 정보를 함께 사용
.\Run-Vision.ps1 -Video 'C:\videos\driving.mp4' -Config 'C:\videos\calibration.json' -Node V4 -InstallReplay
# 이미 분석한 파일 설치
.\Run-Vision.ps1 -Replay verification/vision-public/replay.json -InstallReplay
```

## 판단 로직

YOLO11n은 car, motorcycle, bus, truck을 검출하고 BoT-SORT는 ID를 추적한다. 차량 지면 접점인 상자 하단 중앙을 정규화된 차로 다각형에 대응한다. 보정값이 없을 때 전체 영상의 차량 수를 기록하며 해당 차량을 내 차로 또는 정체 차량이라고 확정하지 않는다.

보정된 지면 좌표의 전방 거리 변화율에 같은 시간의 자차 속도를 더해 차량 종방향 속도를 추정한다. 이 모델은 직선·국소 평면 도로와 정합된 카메라 자세를 전제로 한다. BoT-SORT의 영상 흔들림 보정 자체가 실제 미터 단위 자차 이동 보정은 아니다. 회전·경사·피칭에서는 시간별 보정이 필요하다.

같은 차로에서 속도 5 km/h 이하인 차량 3대 이상이 15 m 이하 간격으로 이어지고, 그 상태가 5초 지속되면 LOW_SPEED_QUEUE로 기록한다. 신호 대기도 포함하는 저속 대기열이며 신호 원인 분류는 구현하지 않았다. 속도 15 km/h 이상인 차량 3대 이상이 5초 유지되면 FLOWING_OBSERVED다. 문턱값은 검증 전의 초기 설정이다.

대기열의 후미가 보이고 거리 보정이 유효할 때에만 교차로까지 거리에서 후미 차량까지 거리를 빼서 후미 구간을 만든다. 가려졌거나 보정이 없으면 camera=null이다. 원활 관측도 전체 해당 블록의 가시 범위가 확인된 경우에만 후미 0으로 전달한다. ‘검출 없음’을 원활로 바꾸지 않는다.

## 보정 JSON 계약

보정값은 영상마다 직접 측정해야 한다. 아래는 구조 설명용 가상 수치이며 공개 예제에 적용하지 않는다.

```json
{
  "fixed_camera": false,
  "calibration": [{
    "time_s": 0.0,
    "image_points": [[0.3,0.9],[0.7,0.9],[0.55,0.5],[0.45,0.5]],
    "ground_points": [[-2,5],[2,5],[2,50],[-2,50]],
    "lane_polygon": [[0.3,0.9],[0.7,0.9],[0.55,0.5],[0.45,0.5]],
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

image_points와 lane_polygon은 영상 너비·높이에 대한 0~1 좌표다. ground_points는 대응하는 지면의 (가로 m, 카메라 전방 m) 좌표다. junction_m은 해당 시각의 카메라에서 교차로까지 전방 거리다. block=0은 이번 블록, 1은 다음 블록이다. quality와 error_m은 검출 점수와 별개인 외부 보정 품질과 거리 오차다.

움직이는 카메라의 보정 샘플은 시각순으로 제공하고 0.5초가 지나면 사용하지 않는다. 시간별 차로 영역과 회전 방향도 외부 설정이다. 자동 차선 인식·GPS 차로 매칭·깊이 모델은 구현하지 않았다. 고정 카메라는 fixed_camera=true와 ego_mps=0으로 정적인 보정을 사용할 수 있다. 관측이 끊기거나 차로가 바뀌면 지속 시간 판정을 다시 시작한다.

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
