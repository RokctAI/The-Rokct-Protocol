---
name: render
description: The one shared render pipeline. Render real or proposal app screens to PNG (real fonts and icons, light/dark, phone/tablet), frame them in our phone/tablet frame, and build animated PowerPoint decks.
version: 1.0.0
---

# Render pipeline (standing rule, Ray 2026-11-28)
**When:** any render, mockup or deck picture of an app screen. Never hand-draw a screen or write your own render script.

1. Read `README.md` in this folder.
2. Real screen: the shared-workflows render harness, plus `scripts/load_package_fonts.dart` so package icons are not squares.
3. Screen not built yet: a throwaway proposal widget from the app's real theme, components, trkeys and demo data, rendered the same way (README "Proposals").
4. `python3 scripts/render.py frame IN.png OUT.png [--device tablet] [--proposal]`
5. `python3 scripts/render.py deck spec.json out.pptx`, then `render.py preview out.pptx` to look at the slides.
6. Improve this skill instead of forking it.
