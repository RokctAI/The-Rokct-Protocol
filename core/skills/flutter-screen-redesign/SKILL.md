---
name: flutter-screen-redesign
description: Ray points at store or tour screenshots and says "redesign".
version: 1.0.0
---

# Redesign a set of app screens in one design language
**When:** Ray points at store or tour screenshots and says "redesign".

1. Pull the current store PNGs (e.g. RokctAI/sticks `marketing/tour/store/NN-*.png`) and render the current screens (procedure 1). Find the widget and route behind each tour step in `templates/tour/<app>.tour.yaml`.
2. Read the product's rules first. For Sticks, that is the call contract ("asks, never takes"). Use Remixicon only, Dart only, and the bundled fonts.
3. Pick one structure shared by every screen and keep it consistent. For Sticks:
   - a colour band with the Stick on top;
   - the decision on an ink-edged slip with a hard shadow;
   - answer buttons pinned at the bottom.
4. Keep the tour step keys and routes unchanged, so the tour still captures them. Fix captions that describe the wrong thing.
5. Privacy states default to hidden, with an opt-in setting. Persist per install via base_sdk `LocalStorage.setJson`.
6. Add widget tests per screen and setting value, plus one test that asserts icons are Remixicon. Run `flutter analyze`.
7. A public API added (new export or constructor param) means a minor SDK bump in three places: pubspec, manifest `version` plus `_comment_version_X_Y_Z`, and the CHANGELOG top entry. The gatekeeper rejects a PR without it.
