# 차로 인식·밀집 후보 개선 결과

2026-11-15. 기존 YOLOP 단독 방식의 낮은 차로 배정률을 개선하고, 실제 영상 분석 결과가 Pleos 앱의 V2V 수신 기록까지 전달되는 것을 확인했다. 아직 실제 속도 기반 정체 정확도를 검증한 결과는 아니다.

## 개선 계획과 반영 내용

| 문제 | 반영한 개선 | 확인 방법 |
|---|---|---|
| 차량 가림으로 차선 페인트가 사라짐 | UFLDv2 CULane ResNet18의 구조 추정 사용. 내 차로 경계를 확보하지 못한 프레임은 YOLOP로 대체 | 동일 표본에서 모델별 비교 |
| 멀리 있는 차량의 검출 대응 실패 | YOLO11n 입력 크기 640 → 960 | 차선 모델을 그대로 둔 비교도 함께 실행 |
| 빠진 경계 때문에 차로 번호가 밀릴 위험 | 구조 모델의 경계 슬롯 유지, 교차·폭·수직 범위 검사 | 누락 슬롯·교차·경계 접점 테스트 |
| 속도 보정이 없으면 영상상 밀집도 표현하지 못함 | `DENSE_TRAFFIC_CANDIDATE` 추가 | 실제 밀집 영상과 비교 영상, 시간·공간 조건 테스트 |
| 밀집 후보를 실제 정체 거리로 오인할 위험 | 후보의 `camera=null` 유지, 앱에서 수치 queue 동반 입력 거부 | Android 계약 및 실제 화면 브리지 검사 |

UFLDv2의 차선 존재 점수는 0.7 이상을 사용한다. 공식 모델의 내부 4개 경계 슬롯을 유지하며, 충분한 관측점과 수직 범위·곡선 잔차 조건을 만족한 곡선만 사용한다. 차량 접점이 두 경계 안쪽에 있을 때만 정확한 상대 차로를 배정한다. 단지 내 차로 바깥임을 아는 경우 `sideEvidence`로 따로 남기고, 이를 LEFT_1 등의 정확한 차로 배정이나 밀집 집계로 승격하지 않는다. 모델의 추정 경계는 실제 도로 경계의 보장이 아니다.

## 표본 비교

기존 19개는 개발 비교 표본이다. 추가 17개는 개선 모델 출력을 보기 전에 원본의 다른 5개 프레임에 표시했다. 두 표본 모두 동일한 공개 영상 2개에서 가져왔으며, 독립적인 도로 데이터셋·전문가 정답·학습 미사용 데이터는 아니다. 원본 차량의 하단 접점과 검출 상자를 대응시켜 평가했다. 대응 실패는 detector의 공식 FN 지표와 같지 않다.

| 표본 | 방식 | 맞는 내/다른 차로 배정 | 틀린 배정 | 차로 미확정 | 검출 대응 실패 | 배정률 |
|---|---|---:|---:|---:|---:|---:|
| 개발 19개 | YOLOP / 640 | 5 | 0 | 11 | 3 | 26.3% |
| 개발 19개 | YOLOP / 960 | 5 | 0 | 13 | 1 | 26.3% |
| 개발 19개 | UFLDv2 / 960 | 8 | 0 | 10 | 1 | 42.1% |
| 개발 19개 | **혼합 / 960** | **10** | **0** | **8** | **1** | **52.6%** |
| 추가 17개 | YOLOP / 640 | 2 | 0 | 14 | 1 | 11.8% |
| 추가 17개 | YOLOP / 960 | 2 | 0 | 15 | 0 | 11.8% |
| 추가 17개 | **혼합 / 960** | **8** | **0** | **9** | **0** | **47.1%** |

추가 표본 중 정확한 EGO/LEFT_1까지 표시한 11건에서는 맞는 차로 번호가 **1/11 → 7/11**로 늘었다. 나머지 4건은 모두 미확정이다. 전체 표본을 탐지하거나 모든 차로 번호를 검증한 것은 아니다. 배정한 표본에서 오분류가 0건이어도 이를 일반적인 정확도 100%라고 해석하지 않는다.

입력 크기만 높인 비교에서는 검출 대응 실패가 줄었지만 차로 배정은 늘지 않았다. 이번 표본의 차로 배정 개선은 주로 구조 모델을 결합한 효과였다. 추가 표본 결과를 보고 임계값을 다시 조정하지 않았다.

## 전체 영상 실행과 밀집 후보

| 영상 | 기존 배정 관측 / 전체 관측 | 개선 배정 관측 / 전체 관측 | 개선된 최대 동시 검출 | 속도·거리 기반 queue |
|---|---:|---:|---:|---:|
| KITTI 주행 예제 | 18 / 101 | 20 / 111 | 13대 | 0 |
| YOLOP 혼잡 주행 예제 | 1 / 63 | 38 / 84 | 12대 | 0 |

약 1초마다 저장한 관측으로, 같은 차량이 반복 포함된다. 이 표는 배정된 관측의 양이며 정답 대비 정확도는 아니다. 표본 정답 비교는 정지 프레임 `predict`, 전체 영상은 BoT-SORT `track`을 사용하므로 두 집계의 검출 결과도 완전히 동일하지 않다.

혼잡 영상에서는 LEFT_1에 차량 3~5대가 배정됐다. 저장 시점 5.7초, 6.7초, 8.7초에 밀집 후보를 표시했다. 7.7초에는 현재 신뢰도·밀집 조건이 부족해 판단 보류로 돌아갔다. KITTI 비교 영상 18개 저장 시점에는 밀집 후보가 없었다. 이는 육안상 혼잡 장면을 일부 포착한 사례이며, 일반적인 정체 재현율이나 오탐률 평가가 아니다.

후보 조건은 같은 확정 차로의 서로 다른 추적 ID 3대 이상, 검출 신뢰도 0.5 이상, 차량 접점의 영상상 간격이 평균 상자 높이 1.5배 이하인 연속 그룹이다. 최근 5초 이상·30회 이상 중 80% 이상에서 충족하고 현재도 충족해야 한다. 0.5초 초과 단절이나 장면 전환 시 초기화한다. 픽셀 간격은 실제 차간 거리로 환산하지 않는다. 반대편 주행·주차·신호 대기의 원인도 자동 판별하지 않는다.

## 앱 연결과 검사

- Python 검사 **17개 통과**: 기존 속도·대기열 조건 및 추가 차로 슬롯, 경계 불확실성, 밀집 지속 시간, 미확정 차로 혼합 금지, 중복 ID, 관측 단절.
- Kotlin 단위 검사 **19개 통과**, debug 앱과 검사 APK 빌드 성공.
- Pleos 에뮬레이터 Android 검사 **4개 통과**: 보정 관측 중계·안내 전환·만료, 동일 영상 중복 출처 금지, 후보의 수치 queue 금지, 실제 분석 파일의 WebView 수신.
- 혼잡 영상의 실제 분석 파일을 활성 운전자 프로필 10에 설치했다. `V4 → V3 → V2 → V1 → EGO` 중계 후 **차량 밀집 후보 · 속도 미확인** 표시를 확인했다. `prepareAt`과 `high`가 null임도 확인했다.

PC에서 녹화 영상을 오프라인 분석하고 Android는 JSON 관측을 재생한다. Android 실시간 카메라 추론이나 실제 무선 V2V 성능을 검증한 것은 아니다. UFLDv2 가중치가 약 825 MB로 크고 CPU 분석 시간이 영상 길이보다 길다.

## 재현

`Run-Vision.ps1`이 공식 모델을 다운로드하고 SHA-256을 확인한다. 모델과 원본 영상은 Git에 포함하지 않는다. 최초 설치·분석에는 네트워크가 필요하고, 영상 자체는 업로드하지 않는다.

```powershell
.\Run-Vision.ps1 -Video .tools/vision-data/yolop-driving.mp4 -Output verification/improvements/continuous -Seconds 9 -InstallReplay
.tools/vision-env/Scripts/python.exe vision/analyze.py --video .tools/vision-data/driving.mp4 --output verification/improvements/kitti --seconds 17
.tools/vision-env/Scripts/python.exe vision/audit_lanes.py --engine hybrid --imgsz 960 --output verification/improvements/dev-hybrid960.json
.tools/vision-env/Scripts/python.exe vision/audit_lanes.py --engine hybrid --imgsz 960 --labels vision/lane-holdout-labels.json --output verification/improvements/additional-hybrid960.json
.tools/vision-env/Scripts/python.exe -m unittest discover -s vision -p 'test_*.py'
```

비교하려면 `--engine yolop --imgsz 640` 또는 `--engine yolop --imgsz 960`으로 별도 출력을 만든다. 전체 영상의 이전 방식은 `analyze.py --lane-engine yolop --imgsz 640`으로 실행한다. 표본 판정 원자료와 전체 영상 요약은 [validation](validation)에 보관했다. `audit_lanes.py`의 queueReview는 기본적으로 이전 출력 폴더를 참조하므로 개선 영상 검토에는 `--video-results verification/improvements`를 지정한다. 어느 경우든 실제 속도 정답 부재 표시를 유지한다.

## 남은 문제와 다음 데이터

추가 표본에서도 9/17건은 차로를 확정하지 못했다. 먼 버스의 접점이 차선 유효 범위 위에 있거나 페인트가 없는 곡선·도심 구간에서 문제가 남는다. 검출된 차량 0대인 EGO 항목은 빈 차로라는 뜻이 아니다. 미확정 차량이 내 차로에 있을 수 있다.

다음 검증에는 국내 도로의 야간·우천·곡선·차로 변경 영상과, 동기화된 자차 속도·카메라 자세·거리/차로 정답이 필요하다. 이 데이터가 있어야 가림 대응과 시간 추적을 조정하고, 실제 저속 대기열 및 준비 지점 오차를 측정할 수 있다. 현 단계에서는 영상 밀집 후보를 실제 km/h 기반 정체나 미터 단위 차로 변경 지점으로 바꾸지 않는다.

## 출처와 모델 고정

- [UFLDv2 공식 저장소](https://github.com/cfzd/Ultra-Fast-Lane-Detection-v2), `model/model_culane.py`, `demo.py`, `configs/culane_res18.py`를 참고한 CPU 추론부. MIT 고지는 [별도 파일](THIRD_PARTY_UFLD_LICENSE.txt)에 유지했다.
- [공식 CULane ResNet18 가중치](https://drive.google.com/file/d/1oEjJraFr-3lxhX_OXduAGFWalWa6Xh3W/view): SHA-256 `956616371EE758551C455D28C1C8A9732B39D7FBD85BC70B9869424A5121F967`.
- [YOLOP 공식 저장소·영상](https://github.com/hustvl/YOLOP), [Ultralytics 주행 예제](https://github.com/ultralytics/assets/releases/download/v0.0.0/kitti-inference-vid.mp4). 영상 SHA-256은 `validation/*-summary.json`에 기록했다.
