---
name: flutter-render-screens
description: before and after any screen change, so Ray and the gatekeeper see real pixels. Without Flutter in the container this is the only way to show a Dart UI.
version: 1.0.0
---

# Render Flutter screens locally for review
**When:** before and after any screen change, so Ray and the gatekeeper see real pixels. Without Flutter in the container this is the only way to show a Dart UI.

1. Install Flutter if missing: download `flutter_linux_3.44.9-stable.tar.xz` from storage.googleapis.com into /opt and add it to PATH. Run `git config --global --add safe.directory '*'`, or pub get fails as root.
2. In the SDK package (e.g. `agent/dart`), put a throwaway test like `scripts/shots_test.dart` under `test/`. Do not commit it. The test:
   - feeds the screens from the demo fixtures (`templates/assets/demo/<sdk>/<cmd>.json`), resolving `$demo_select` and `$now_iso` the way the demo gateway does;
   - loads the real fonts with `FontLoader`, or text renders as boxes or Roboto;
   - pumps each screen at the phone size the tour uses and writes a PNG through `RepaintBoundary.toImage`.
3. Render light and dark, and both before (on `origin/main`) and after.
4. Stitch them with `python3 scripts/montage.py out.png a.png b.png ...`.
5. Look at every image yourself and iterate until it is agency-grade. A test that passes is not a design review.
6. Save the images to `/mnt/project-files/<area>/<task>/`. If the thread is near its attachment cap, publish them as an Artifact page with base64-embedded images.
