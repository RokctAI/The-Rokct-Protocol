#!/usr/bin/env python3
# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD. AGPL-3.0-only.
"""One command for the shared render pipeline.

  python3 tools/render/render.py frame SCREEN.png OUT.png [--device phone|tablet] [--bg ...]
  python3 tools/render/render.py deck SPEC.json OUT.pptx
  python3 tools/render/render.py preview DECK.pptx            # slide PNGs (needs LibreOffice)
  python3 tools/render/render.py screen                         # how to render a real Flutter screen
Needs: pip install pillow python-pptx lxml
"""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "frame":
        return subprocess.call([sys.executable, str(HERE / "phone_frame.py"), *rest])
    if cmd == "deck":
        return subprocess.call([sys.executable, str(HERE / "deck.py"), *rest])
    if cmd == "preview":
        pptx = Path(rest[0]).resolve()
        rc = subprocess.call(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(pptx.parent), str(pptx)])
        if rc: return rc
        return subprocess.call(["pdftoppm", "-png", "-r", "80", str(pptx.with_suffix(".pdf")), str(pptx.with_suffix("")) + "-slide"])
    if cmd == "screen":
        print((HERE / "README.md").read_text().split("## 2.")[0]); return 0
    print(f"unknown command {cmd}\n{__doc__}"); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
