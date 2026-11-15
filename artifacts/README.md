# Downloadable APK

`mergewindow-debug.apk` is the MergeWindow 0.2.0 debug build for the Pleos Connect emulator.
It is a development-signed demonstration build, not a production release.

The map and congestion scenarios are offline fixtures. V2V transport is simulated.
Recorded-video analysis runs on a PC; the Android app replays the analysis output.

Build the APK from source with `gradlew.bat assembleDebug` (Android SDK and Pleos dependencies required).
The accompanying SHA-256 file identifies the uploaded binary.

Additional local development utilities are checked in at their original paths:
- `output/demo/build_demo.py`: base video storyboard and renderer.
- `output/demo/build_apple_demo.py`: Paperlogy video renderer. Set `PAPERLOGY_FONT_DIR` if needed.
- `output/demo/apple/verify_videos.py`: full video decode and frame checks.
- `tmp/pdfs/build_flowchart.py`: earlier lane-preparation flowchart generator.

These utilities require local source footage/captures and Python libraries; those media files and fonts are not bundled.
Application forms, consent documents, contact information, and generated submission packages are excluded.
