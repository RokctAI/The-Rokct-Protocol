---
name: html-mockup-first
description: Build static HTML mockups of every screen and state for approval before a large Dart redesign.
version: 1.0.0
---

# HTML mockups before building (design first)
**When:** a large redesign where Ray should see the direction before Dart work.

1. Generate a static HTML page of every screen and state with `scripts/build2.py` (styles in `style2.css`; `build.py` and `style.css` are the older v1 mockup, kept for reference).
2. Shoot individual screens with `node scripts/shoot.mjs page.html <element ids>`. It uses Playwright with /opt/pw-browsers/chromium.
3. Publish as an Artifact for Ray, then build the Dart version against it, keeping the palette tokens identical. Polaris pine light values: surface #EEF3EE, card #FBFCFA, alt #F2F5F1, stroke #D6DDD6, sub #E3E9E3, sec #5B6660, faint #8B958F, ink #15201B.
