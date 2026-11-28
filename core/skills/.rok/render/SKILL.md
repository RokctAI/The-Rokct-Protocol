---
name: render
description: The one shared render pipeline. Render real or proposal app screens to PNG (real fonts and icons, light/dark, phone/tablet), frame them, and build animated PowerPoint decks. The tool lives in RokctAI/shared-workflows.
version: 1.0.0
---

# Render pipeline (standing rule, Ray 2026-11-28)
**When:** any render, mockup or deck picture of an app screen. Never hand-draw a screen or write your own render script.

The tool lives in ONE place, the public `RokctAI/shared-workflows` repo (Ray, 2026-11-28: "All in shared-workflows"):

    git clone --depth 1 https://github.com/RokctAI/shared-workflows /tmp/sw
    # manual: /tmp/sw/scripts/render/README.md

1. Real screen: copy `templates/render-harness/` (with `load_package_fonts.dart`, so icons are not squares) into the app's `test/render/`, fill the TODO markers, run `scripts/render/run_strip.sh`. Light and dark, phone and tablet.
2. Screen not built yet: a throwaway proposal widget from the app's real theme, components, trkeys and demo data, rendered the same way (README "Proposals").
3. `python3 /tmp/sw/scripts/render/render.py frame IN.png OUT.png [--device tablet] [--proposal]`
4. `python3 /tmp/sw/scripts/render/render.py deck spec.json out.pptx`, then `render.py preview out.pptx`.
5. Improve the tool in shared-workflows (public repo, push via the helper thread); never fork a copy.
