# MergeWindow — 오프라인 내비게이션 시연 (0.2)

지도 중심의 내비게이션 화면에 우회전 차로 준비 안내를 더한 정차 시연용 Android 앱입니다. 큰 회전 안내와 목적지를 기본으로 표시하고, 혼잡 상황에 따라 보조 안내 카드가 나타납니다. 시나리오 선택과 수신 로그는 우측 `시연 설정`에 모았습니다.

기본값은 **오프라인 시연**입니다. 앱에 포함된 가상 지도·경로·혼잡을 사용하며, 실제 지형이나 실제 주행 경로가 아닙니다. 외부 지도 요청과 실제 위치 조회를 하지 않습니다. Pleos 기본 내비 앱 내부에 삽입하는 방식이 아닌 독립 앱입니다.

## 실행

Android Studio에서 이 폴더를 열고 Gradle Sync 후 `app`을 Pleos AVD에서 실행합니다.

```powershell
.\Run-App.ps1
# 이미 빌드한 APK 설치·실행
.\Run-App.ps1 -SkipBuild
```

- Android Studio JBR / Gradle 9.1.0 / AGP 9.0.1
- compileSdk 36 / targetSdk 34 / minSdk 28
- Pleos Connect Emulator 2.1.0 / NaviHelper 3.0.5
- `local.properties`의 `sdk.dir`에 설치된 Android SDK 경로를 지정합니다.
- 한글 경로의 Windows Java 인자 파일을 읽도록 Gradle JVM 인코딩을 `COMPAT`로 지정했습니다.
- Pleos 2.1은 `android.car-module`을 boot class path로 제공합니다. Manifest의 `android.car` shared library는 선택 사항입니다.

## 오프라인 시연 순서

1. Pleos 에뮬레이터를 정차 상태로 두고 앱을 실행합니다. 차량 제한 상태를 확인할 때까지 조작이 잠깁니다.
2. `오프라인 시연` 표시와 가상 도로·파란 경로선을 확인합니다.
3. 우측 톱니바퀴 → `혼잡`을 선택하면 패널이 닫히고 회전 안내 아래에 준비 카드와 주황색 가상 대기열이 나타납니다.
4. 카드에서 안내 근거를 확인하거나 다른 혼잡 상황을 선택합니다.

| 상황 | 가상 우회전 거리 | 가상 대기열 | 안내 |
|---|---:|---:|---|
| 원활 | 650 m | 60–120 m | 추가 준비 안내 없음 |
| 혼잡 | 650 m | 430–520 m | 우측 차로 미리 준비 |
| 관측 부족 | 650 m | 미표시 | 정확한 후미를 알 수 없음 |
| 데이터 만료 | 650 m | 미표시 | 새 관측 대기 |
| 진입 기회 상실 | 350 m | 430–520 m | 무리한 변경 회피 |

준비 기준은 대기열 상한 + 150 m입니다. 보정된 확률 예측이나 차선 변경 허가가 아닙니다. 그림의 도로 길이는 실제 축척이 아닙니다.

## 선택 기능: 실제 Pleos 경로 이벤트

`시연 설정`에서 `오프라인 시연`을 끄면 NaviHelper에 연결합니다. 이 모드에서는 실제 활성 경로 상태를 받아야 안내가 켜지며, 연결 성공이나 경로 이벤트를 가짜로 대체하지 않습니다. `42dot`은 실제 경로 요청을 보냅니다. Pleos 서비스 자체의 통신과 초기 설정이 필요할 수 있습니다.

`실제 다음 회전 사용`을 켜면 실제 TBT의 첫 회전 종류·거리를 사용합니다. 우회전이 아니면 우회전 혼잡 준비 안내를 적용하지 않습니다. **지도와 혼잡은 계속 가상**이며, 실제 회전 모드에서는 오해를 피하도록 가상 경로선·차량 마커를 숨깁니다. 실제 경로선·ETA는 아직 연동하지 않았습니다.

오프라인 모드는 SDK 어댑터를 생성하지 않고, 별도의 명시적인 시연 상태를 사용합니다. 실제 SDK 이벤트 기록에 가상 이벤트를 넣지 않습니다.

## 구조와 데이터 처리

- `GuidanceEngine`: 순수 Kotlin 안내 로직. 경로 15초, 관측 12초 유효기간과 비정상 거리·미래 시각 처리.
- `DrivingGate`: 차량 UX 제한 구독. 제한 또는 연결 미확인 시 조작 잠금.
- `PleosRouteSource`: 선택한 경우에만 실제 경로 상태·TBT를 구독하고 3초마다 갱신. 현재 위치 조회 없음.
- `MainActivity`: 로컬 자산과 제한된 브리지로 UI 구성. 백그라운드 전환 시 구독·타이머 해제 및 안내 초기화.
- `assets/demo-map.svg`: 앱에 포함된 창작 가상 도로 그림. Leaflet의 평면 좌표계로 표시하며 위경도를 사용하지 않습니다.

앱에는 INTERNET 권한이 없으며 WebView의 네트워크 로드를 차단합니다. 로컬 자산 이외 요청은 거절하고, CSP도 외부 이미지와 통신을 차단합니다. 좌표와 인증 정보를 로그에 기록하지 않습니다. 브라우저 검수용 데이터는 `.tools`에만 있고 APK에는 포함하지 않습니다.

Leaflet 1.9.4는 로컬 번들이며 BSD-2-Clause 라이선스를 `app/src/main/assets/vendor/LICENSE`에 포함했습니다.

## 검증

```powershell
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat assembleDebug testDebugUnitTest lintDebug
# 오프라인 Android WebView 렌더링 검사
.\gradlew.bat connectedDebugAndroidTest '-Pandroid.testInstrumentationRunnerArguments.class=com.mergewindow.app.NavigationRenderingTest'
# 선택: 실제 Pleos 서비스에 42dot 경로를 요청하는 검사
.\gradlew.bat connectedDebugAndroidTest '-Pandroid.testInstrumentationRunnerArguments.class=com.mergewindow.app.PleosIntegrationTest'
```

단위 테스트는 다섯 시나리오, 경로 없음, 만료·미래 시각, 회전 종류, 거리 경계와 주행 제한을 검사합니다. 오프라인 렌더링 검사는 실제 Android WebView에서 로컬 SVG와 가상 차량, 브리지, 숨겨진 설정 패널, 네트워크 차단 및 INTERNET 권한 부재를 확인합니다.

2026-11-13 검증: APK 빌드 성공, 단위 테스트 5개 및 Pleos 에뮬레이터 오프라인 렌더링 테스트 1개 통과, lint 오류 0개(경고 6개). 브라우저에서도 지도 배치와 혼잡·진입 기회 상실 안내 전환을 확인했습니다. 오프라인 APK 설치·실행을 완료했습니다.

실제 SDK 경로 통합 검사는 0.1에서 통과했습니다. 0.2의 최근 재검사에서는 Pleos가 `CAUSE_SEARCH_ROUTE`를 반환해 경로 활성화 단계가 실패했습니다. 오프라인 시연은 해당 경로 서비스에 의존하지 않습니다.

## 범위

정차 중 개발·대회 시연용입니다. 실제 차로별 혼잡 측정, 차선 인식, V2V, 실차 주행 검증, 음성 안내, 자동 재탐색과 도로 주행용 승인은 포함하지 않습니다.

## 공식 참고

- [NaviHelper 이벤트](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/NaviHelper/event-listeners)
- [Pleos 주행 규제](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/driving-restriction-development-guide)
- [내비게이션 개발 가이드](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/navigation-app-development-guide)
