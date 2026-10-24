---
name: tour-store-image-fix
description: Fix store or tour images whose colours, fonts, icons or faces do not match the app render (orange canvas, Roboto, emoji).
version: 1.0.0
---

# Fix tour or store images that don't match the app's render
**When:** store images show the wrong colours, fonts or icons.

1. Canvas colour: shared-workflows `scripts/tour/assemble.py` (~L1418) reads `video.brand_color` and `accent_color` from the app's `tour/app.tour.yaml`. If they are missing, it falls back to the theme primary, which defaults to #FF6600 (orange). Set them in the shell repo.
2. Fonts: if the SDK sets no font, the captures render Roboto. Bundle the fonts as package fonts (with their OFL licence) and reference them in the theme.
3. Icons: replace emoji and Material icons with Remixicon.
4. Faces and moods: check the state-to-face mapping (a "waiting" state was drawn worried).
5. The store PNGs are committed by the shell's Guided Tour workflow from the release tour APK. Code changes reach them only on the next run, so never dispatch a release without Ray's go.
