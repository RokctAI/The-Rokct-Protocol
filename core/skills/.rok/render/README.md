# Render pipeline (every thread uses this, nobody rolls their own)

Rule (decision log, "Shared render pipeline"): a picture of an app screen is
always a render of Flutter code with demo data: the real screen, or for a
screen not built yet a proposal widget made from the app's real parts. Frames, mockups and
decks are built AROUND those renders by the tools here. No hand-drawn screens,
no cut-up screenshots.

## 1. Render the real screen (light + dark, phone + tablet) -> PNG

The engine already exists in the public repo `RokctAI/shared-workflows`:

    git clone --depth 1 https://github.com/RokctAI/shared-workflows /tmp/sw
    # read /tmp/sw/scripts/render/README.md  (the full manual)
    # copy /tmp/sw/templates/render-harness/render_screen_test.dart into the
    # app shell's test/render/, fill its 8 TODO markers, then:
    RENDER_TOOLS_DIR=/tmp/sw bash /tmp/sw/scripts/render/run_strip.sh

It pumps the real screen in a widget test at real sizes, waits until it is
ready, and refuses blank / spinner / block-letter frames (`frame_quality.py`).

**Icons show as little squares?** The template only loads MaterialIcons.
Copy `load_package_fonts.dart` (this folder) next to the test and add
`await loadPackageFonts();` as the last line of `loadRealFonts()`. It loads
every font every package declares (Remix, Cupertino, Phosphor, the app's own)
under the exact name Flutter asks for. The Sticks sample in `sample/` shows
the squares this fixes.

Sizes: phone 390x844 logical at dpr 3; tablet 1024x1366 (or the pane rule
widths). Always both themes: copy the app's MaterialApp `theme:` AND
`darkTheme:` verbatim.

## Proposals (screen not built yet: render first, then build)

Most renders are proposals, so there is no real screen yet. Then:

1. Write the proposed screen as a throwaway widget in the app's own render test
   (`test/render/proposals/<name>.dart`), built from the app's REAL theme,
   shared components, trkeys and demo data. Never HTML, never a drawing.
2. Render it with the same harness (same fonts, icons, light + dark, sizes).
3. Frame it with `--proposal`, which stamps an orange PROPOSAL label:
   `render.py frame proposal.png out.png --proposal`
4. When Ray approves, build the real screen; the proposal widget is deleted
   and the real screen is rendered again WITHOUT `--proposal` for the PR.

Because a proposal is built from the app's own parts, what Ray approves is
what can actually be built.

## 2. Frame it (our own phone/tablet frame, drawn in code)

    python3 core/skills/.rok/render/scripts/render.py frame screen.png framed.png --device phone|tablet \
        [--bg "#0E1726"] [--frame "#111418"]

## 3. Put it in a real, animated PowerPoint

    python3 core/skills/.rok/render/scripts/render.py deck spec.json out.pptx      # spec format: top of deck.py

Each slide fades in; each framed screen flies up (or fades) one after the
other, so it plays by itself. Preview without PowerPoint:

    python3 core/skills/.rok/render/scripts/render.py preview out.pptx

Ray's deck rules still apply: PNGs first, PowerPoint only after he approves.

## Files
- `load_package_fonts.dart` icon/package font loader for the harness
- `phone_frame.py` frame helper (Pillow)
- `deck.py` animated deck builder (python-pptx)
- `render.py` one CLI entry: frame, deck, preview, screen
- worked sample: /mnt/project-files/scripts/render/sample/
