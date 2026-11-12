# MergeWindow — 첫 번째 목표

Pleos NaviHelper가 보내는 **실제 경로 이벤트**를 받아, **가상 우회전 혼잡**에 따라 준비 안내가 달라지는 정차 시연용 Android 앱입니다.

## 실행

Android Studio에서 이 폴더를 열고 Gradle Sync 후 `app`을 Pleos AVD에서 실행합니다. 이 PC에서는 PowerShell에서 다음 명령도 가능합니다.

```powershell
.\Run-App.ps1
# 이미 빌드한 APK만 설치·실행
.\Run-App.ps1 -SkipBuild
```

- JDK: Android Studio 내장 JBR (이 PC: Java 25)
- Gradle 9.1.0 / AGP 9.0.1 (Kotlin 내장)
- compileSdk 36 / targetSdk 34 / minSdk 28
- Pleos Connect Emulator 2.1.0, NaviHelper 3.0.5
- `local.properties`의 `sdk.dir`은 각 PC의 Android SDK 경로를 사용합니다.
- 한글 경로에서 Windows Java launcher의 클래스 경로 인자 파일을 읽도록 Gradle JVM 인코딩을 `COMPAT`로 지정했습니다.
- `android.car`는 Pleos 2.1의 boot class path에 포함됩니다. Manifest의 shared library 요구는 선택 사항이며, 앱은 차량 UX 제한 API를 직접 사용합니다.

## 시연 순서

1. Pleos 에뮬레이터를 정차 상태로 둡니다. 차량 제한 상태가 확인되지 않으면 조작이 잠깁니다.
2. MergeWindow를 실행하고 `PLEOS 연결됨` 및 실제 수신 이벤트를 확인합니다.
3. `테스트 목적지 · 42dot`을 눌러 Pleos에 실제 경로 요청을 보냅니다. 경로 요청 성공만으로 안내를 켜지 않으며, SDK가 활성 경로 상태를 보내야 합니다. 내비 초기 설정·약관 동의가 필요한 경우 사용자가 완료해야 합니다.
4. `원활`, `혼잡`, `관측 부족`, `데이터 만료`, `진입 기회 상실`을 선택합니다.
5. `실제 다음 회전 사용`을 켜면 실제 TBT의 첫 번째 회전 종류·거리를 씁니다. 다음 회전이 우회전이 아니면 혼잡 준비 안내를 적용하지 않습니다.

| 시나리오 | 가상 우회전 거리 | 가상 대기열 범위 | 예상 안내 |
|---|---:|---:|---|
| 원활 | 650 m | 60–120 m | 아직 준비 구간 전 |
| 혼잡 | 650 m | 430–520 m | 우측 차로 미리 준비 |
| 관측 부족 | 650 m | 표시하지 않음 | 혼잡 가능성, 정확한 후미 알 수 없음 |
| 데이터 만료 | 650 m | 표시하지 않음 | 새 관측 대기 |
| 진입 기회 상실 | 350 m | 430–520 m | 무리한 변경 회피, 기존 내비 확인 |

가상 모드에서도 경로의 활성 여부는 항상 실제 Pleos 서비스에서 받습니다. 앱 안에 가짜 경로 연결 성공이나 대체 이벤트 발생기는 없습니다. 거리·대기열은 화면에 가상이라고 명시됩니다. 대기열 상한 + 150 m가 시연 준비 기준이며, 확률 모델이나 보정된 Q50/Q90 값이 아닙니다.

## 구조와 실패 처리

- `PleosRouteSource`: SDK 연결·이벤트 리스너, 3초마다 상태 조회, 종료 시 리스너 해제. 경로 시작/재탐색/취소/도착/오류 및 TBT 처리.
- `GuidanceEngine`: Android에 의존하지 않는 결정 로직. 실제 경로 정보 15초, 혼잡 관측 12초 유효기간.
- `DrivingGate`: `CarUxRestrictionsManager`를 구독하고 제한·연결 미확인 상태에서 조작을 잠금.
- `MainActivity`, `LaneView`: 실제 데이터와 가상 데이터를 구분한 화면, 시나리오 선택, 이벤트 수신 기록. 화면이 백그라운드로 가면 구독·타이머를 해제합니다.

경로 없음·종료·취소·연결 실패 시 숫자 안내를 제거합니다. 오래된 정보나 미래 타임스탬프도 유효하지 않습니다. 관측 부족·만료 시 대기열 그림과 준비 거리를 표시하지 않습니다. 좌표·인증 정보는 앱 로그에 기록하지 않습니다.

## 검증

```powershell
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat assembleDebug testDebugUnitTest lintDebug
# 실제 Pleos 서비스가 필요하며 42dot 테스트 경로를 요청합니다.
.\gradlew.bat connectedDebugAndroidTest
```

단위 테스트는 다섯 시나리오, 경로 없음, 경로/관측 만료, 미래 시각, 실제 회전 종류, 경계 거리, 비정상 거리, 주행 제한을 검증합니다. 통합 테스트는 가짜 SDK 없이 연결·활성 경로·TBT 수신을 확인한 후 같은 실제 경로에 시나리오를 적용합니다.

2026-11-12 검증 결과: APK 빌드 성공, 단위 테스트 5개 통과, 실제 Pleos 통합 테스트 1개 통과. 통합 테스트는 기존 경로 취소 → 실제 42dot 요청 → 활성 경로와 TBT 수신 → 다섯 시나리오 → 실제 취소 시 안내 제거를 확인했으며, 차량 UX 제한 API도 정차 시연 허용 상태를 반환했습니다. Lint는 오류 0개, 경고 22개(버전 업데이트 권고, 한국어 문자열 리소스화, KTX 권고 등)입니다. 앱 실행 및 지속적인 경로 이벤트 수신을 확인했습니다. 데스크톱 캡처 도구가 에뮬레이터 창을 화면 밖으로 인식하여 화면 배치의 시각 검수는 완료하지 못했습니다.

## 범위

현재 버전은 정차 중 개발·대회 시연용입니다. 실제 차로별 혼잡 측정, 차선 인식, V2V, 실차 주행 검증, 음성 안내, 도로 주행용 승인, 자동 재탐색은 포함하지 않습니다. 기존 내비와 함께 주행 중 사용하는 제품으로 출시하려면 내비 포커스·주행 규제 정책과 심사를 별도로 해결해야 합니다.

## 공식 참고

- [NaviHelper 이벤트](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/NaviHelper/event-listeners)
- [NaviHelper 권한](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/NaviHelper/declaring-permissions)
- [Pleos 주행 규제](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/driving-restriction-development-guide)
- [내비게이션 개발 가이드](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/navigation-app-development-guide)
