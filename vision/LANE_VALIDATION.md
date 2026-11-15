# 자동 차로 인식 및 실제 영상 검증 결과

2026-11-15 기준, 자동 차선 분할과 차량 차로 배정을 구현했다. 실제 주행 영상에서 동작을 확인했지만 차로별 정체가 정확하다는 검증은 통과하지 못했다. 차량이 빽빽하게 늘어선 장면에서 차선 가림으로 배정률이 낮고, 동기화된 실제 속도와 거리 정답이 없다.

## 구현

YOLO11n + BoT-SORT 차량 추적에 YOLOP 640 ONNX 차선·주행 가능 영역 분할을 연결했다. 실행은 OpenCV DNN CPU다. ONNX Runtime은 이 PC의 DLL 의존성 문제로 사용하지 않는다.

차선 마스크의 중심을 아래에서 위로 추적한다. 행별 후보를 거리순으로 함께 대응하여 작은 잡음이 기존 차선을 가로채지 않게 한다. 충분한 길이와 작은 잔차를 갖는 곡선만 채택한다. 차량이 가리는 지면 대신 하단 접점 바로 아래의 주행 가능 영역을 확인한다.

차량 하단 중앙점이 확인된 두 경계 사이에 있으면 EGO 또는 LEFT_1/RIGHT_1 등 카메라 기준 차로를 부여한다. 경계가 없는 영역, 차선 위, 화면 하단에 잘린 차량은 UNKNOWN이다. 경계가 없어진 뒤 장시간 외삽하거나 과거 경계를 계속 재사용하지 않는다. 이 상대 차로 표시는 진행 방향, 회전 전용 여부, 실제 도로 차로 ID를 확정하지 않는다. LEFT_1이 반대 방향 차로일 수도 있다.

차로별 차량 수와 상태는 laneObservations로 기존 V2V 중계를 통과한다. 앱 수신 기록에 내 차로·차로 미확정 수와 판단 보류 상태가 표시된다. 보정된 속도가 있으면 차로마다 QueueJudge를 실행하고, 경로에 명시적으로 대응한 auto_lane만 준비 안내의 후미 범위에 사용한다.

## 실제 영상 실행

| 영상 | 차량 검출 프레임 | 최대 동시 차량 수 | 표본 차량-시점 관측 수 | 차로 배정 관측 수 | 거리 기반 정체 관측 |
|---|---:|---:|---:|---:|---:|
| Ultralytics KITTI 주행 예제 | 166 | 10 | 101 | 18 | 0 |
| YOLOP 공식 주행 예제 | 89 | 9 | 63 | 1 | 0 |

표본 관측은 약 1초마다 저장하며, 같은 차량이 여러 시점에 반복 포함된다. 따라서 독립 차량 수나 정확도 분모로 해석하지 않는다. 첫 영상은 여러 장면이 이어진 영상이다. 큰 영상 변화 시 추적·속도 이력과 판정 지속 시간을 초기화하는 처리를 추가했다. 이는 장면 전환 검출의 완전한 보장을 의미하지 않는다.

## 직접 표시한 차량 표본 비교

모델 출력과 별도로 원본 8개 프레임에서 차량 19건의 접점과 내 차로/다른 차로를 육안으로 표시했다. 개발자가 직접 선정한 소규모 표본으로 독립 전문가의 공식 정답 데이터가 아니다. 첫 영상의 0초 프레임은 후처리 개발에도 사용했으므로 별도 테스트 세트 성능이라고 주장하지 않는다. 추적 ID의 장기 일관성, 모든 인접 차로 번호, 상대 진행 방향은 이 비교의 평가 범위에 포함하지 않았다.

| 결과 | 건수 |
|---|---:|
| 배정했고 내 차로/다른 차로 구분이 맞음 | 5 |
| 배정했으나 구분이 틀림 | 0 |
| 차로 미확정 | 11 |
| 정답 접점과 검출 상자의 대응을 찾지 못함 | 3 |
| 전체 | 19 |

배정률은 5/19 = 26.3%다. 배정한 5건만 보면 모두 맞았지만, 이를 전체 정확도 100%라고 부를 수 없다. 보류와 대응 실패를 포함하면 전체 19건 중 맞는 배정을 제공한 것은 5건이다. 개발에 사용한 0초 프레임의 2건을 빼면 나머지 17건 중 맞는 배정은 3건이다. 표본 크기와 선정 방식 때문에 일반화 성능을 추정할 수 없다.

## 정체 판단 검증

YOLOP 예제 0~8초의 왼쪽에는 차량이 줄지어 있는 모습을 육안으로 확인했다. 그러나 차선이 차량에 가려져 이 구간의 표본 9개 시점에서 LEFT_1을 확보하지 못했다. 따라서 이 장면의 차로별 정체 판단은 성공했다고 평가할 수 없다.

KITTI 예제 0~3초의 내 차로는 육안상 차량 3대가 이어진 대기열이 확인되지 않는다. 시스템도 4개 표본 시점에서 INSUFFICIENT_DATA를 유지했다. 이 판단 보류는 원활 판정의 정답으로 집계하지 않았다.

두 영상 모두 자차 속도·거리 보정·실측 정체 정답이 없어 속도 5 km/h 이하라는 조건을 검증할 수 없다. 정체 판단의 정확도, 재현율, 오탐률은 계산하지 않았다. 실제 정체 양성·음성 사례를 확인하려면 영상과 동기화된 자차 운동·거리 정보, 차로와 차량 속도 정답이 필요하다. 자동 차선 분할이 이러한 보정을 대신하지 않는다.

## 재현과 파일

```powershell
.tools/vision-env/Scripts/python.exe vision/analyze.py --video .tools/vision-data/driving.mp4 --output verification/lanes/kitti --seconds 20
.tools/vision-env/Scripts/python.exe vision/analyze.py --video .tools/vision-data/yolop-driving.mp4 --output verification/lanes/continuous --seconds 10
.tools/vision-env/Scripts/python.exe vision/audit_lanes.py
.tools/vision-env/Scripts/python.exe -m unittest discover -s vision -p 'test_*.py' -v
.\Run-Vision.ps1 -Replay verification/lanes/kitti/replay.json -InstallReplay
```

- 표본 정답은 vision/lane-audit-labels.json에 있다.
- 세부 비교 결과는 verification/lanes/audit.json에 있다.
- 두 영상의 annotated.mp4와 lane-analysis.json, replay.json, summary.json은 각 출력 폴더에 있다.
- Python 회귀 검사 9개와 기존 Kotlin 단위 검사 19개가 통과했다. 이들은 실제 도로 정확도를 측정한 검사가 아니다.
- YOLOP 모델 SHA-256은 CD66A3E0087A7258AE07768CC02CB742EED93865727AE4C9BAF969B8FA190696이다.

## 출처

- YOLOP 공식 코드와 가중치 https://github.com/hustvl/YOLOP
- 공식 전처리 참고 https://github.com/hustvl/YOLOP/blob/main/test_onnx.py
- KITTI 주행 예제 https://github.com/ultralytics/assets/releases/download/v0.0.0/kitti-inference-vid.mp4
- YOLOP 주행 예제 https://github.com/hustvl/YOLOP/blob/main/inference/videos/1.mp4

가중치와 원본 영상은 저장소에 재배포하지 않는다. 공식 예제 영상의 학습 세트 포함 여부를 확인하지 못했으므로 미사용 테스트 세트라고 가정하지 않는다.

Android 연결 검사 3개도 통과했다. 자동 차로별 차량 수와 판단 보류 상태가 V2V를 거쳐 WebView 화면에 표시됨을 확인했다. 에뮬레이터 무응답을 재시작으로 복구했고, 초기화 직후 Activity 종료로 한 차례 실패한 검사는 프로필 초기화 후 재실행해 통과했다.
