"""Rebuild web/index.html from the sources in tools/src/.

    python tools/build_web.py

Run tools/export_models.py first if you retrained the models.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "src"

html = (SRC / "template.html").read_text(encoding="utf-8")
html = (html.replace("/*MODELS_JSON*/", (SRC / "models.json").read_text(encoding="utf-8").strip())
            .replace("/*CORE_JS*/", (SRC / "core.js").read_text(encoding="utf-8"))
            .replace("/*UI_JS*/", (SRC / "ui.js").read_text(encoding="utf-8")))
(ROOT / "web" / "index.html").write_text(html, encoding="utf-8")
print(f"wrote web/index.html ({len(html) // 1024} KB)")

earth = (SRC / "earth_template.html").read_text(encoding="utf-8")
earth = (earth.replace("/*MODELS_JSON*/", (SRC / "models.json").read_text(encoding="utf-8").strip())
              .replace("/*CORE_JS*/", (SRC / "core.js").read_text(encoding="utf-8")))
(ROOT / "web" / "earth.html").write_text(earth, encoding="utf-8")
print(f"wrote web/earth.html ({len(earth) // 1024} KB)")
