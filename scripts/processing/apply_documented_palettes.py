"""Switch the AEO precipitation, SPEI and SPI maps to documented palettes (exact class-colour swap).

Palettes (sources):
  * SPEI and SPI (7 classes, breaks ±1, ±1.5, ±2): ColorBrewer RdBu-7, the palette documented by the
    Copernicus Global Drought Observatory in its SPEI factsheet (factsheet_spei.pdf, Table 2):
    #b2182b #ef8a62 #fddbc7 #f7f7f7 #d1e5f0 #67a9cf #2166ac (dry → wet).
  * Annual precipitation (7 classes): ColorBrewer YlGnBu-7 (dry yellow → wet blue).
  * Precipitation anomaly (9 classes): ColorBrewer BrBG-9 (brown drier → teal wetter), the
    convention of rainfall-anomaly maps (dry = brown, wet = green/blue).
ColorBrewer: Brewer, Harrower & Penn State (colorbrewer2.org), Apache 2.0 licence.

Every overlay pixel holds exactly one class colour; each is replaced by its new colour, so class
boundaries and values are unchanged. Pixels with any other colour stop the script (nothing written).
The pipelines' palette constants and the map.json files are updated in the same run.

Usage: python scripts/processing/apply_documented_palettes.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "public/data/aeo/products"

OLD_SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
NEW_SEQ = ["#ffffcc", "#c7e9b4", "#7fcdbb", "#41b6c4", "#1d91c0", "#225ea8", "#0c2c84"]
OLD_DIV = ["#6b1515", "#9e2424", "#d03b3b", "#ee8d81", "#f0efec", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
NEW_DIV = ["#8c510a", "#bf812d", "#dfc27d", "#f6e8c3", "#f5f5f5", "#c7eae5", "#80cdc1", "#35978f", "#01665e"]
OLD_IDX = ["#6b1515", "#d03b3b", "#ee8d81", "#f0efec", "#86b6ef", "#3987e5", "#0d366b"]
NEW_IDX = ["#b2182b", "#ef8a62", "#fddbc7", "#f7f7f7", "#d1e5f0", "#67a9cf", "#2166ac"]
ARID = ["#e8dcc4", "#b49d72"]  # SPEI hyper-arid hatch (unchanged)

rgb = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def recolor(path: Path, old: list[str], new: list[str], keep: list[str] = ()) -> bool:
    a = np.array(Image.open(path).convert("RGBA"))
    if not (a[..., 3] > 0).any():
        return False
    out = a.copy()
    done = a[..., 3] == 0
    for o, n in zip(old, new):
        m = (a[..., 0] == rgb(o)[0]) & (a[..., 1] == rgb(o)[1]) & (a[..., 2] == rgb(o)[2]) & ~done
        out[m, :3] = rgb(n)
        done |= m
    for k in keep:
        done |= (a[..., 0] == rgb(k)[0]) & (a[..., 1] == rgb(k)[1]) & (a[..., 2] == rgb(k)[2])
    # already converted (re-run): accept the new colours
    for n in new:
        done |= (a[..., 0] == rgb(n)[0]) & (a[..., 1] == rgb(n)[1]) & (a[..., 2] == rgb(n)[2])
    left = ~done
    if left.any():
        raise SystemExit(f"{path}: {int(left.sum())} pixels with an unexpected colour; stopped")
    Image.fromarray(out).save(path, optimize=True)
    return True


def sub_file(path: Path, old: list[str], new: list[str]) -> None:
    s = path.read_text(encoding="utf-8")
    s2 = s.replace(json.dumps(old), json.dumps(new)).replace(", ".join(f'"{c}"' for c in old), ", ".join(f'"{c}"' for c in new))
    if s2 == s and not all(c in s for c in new):
        raise SystemExit(f"{path}: palette not found")
    path.write_text(s2, encoding="utf-8")


def main() -> None:
    n = 0
    pm = P / "precipitation/v1.0.0/map"
    for f in sorted(pm.glob("annual_*.png")):
        n += recolor(f, OLD_SEQ, NEW_SEQ)
    # normal.png was never converted by the earlier light-surface recolouring: it still has the
    # original palette (same class order, driest first)
    n += recolor(pm / "normal.png", ["#132a4a", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"], NEW_SEQ)
    for f in sorted(pm.glob("anomaly_*.png")):
        n += recolor(f, OLD_DIV, NEW_DIV)
    for f in sorted((P / "spei/v1.0.0/map").glob("spei*.png")):
        n += recolor(f, OLD_IDX, NEW_IDX, ARID)
    print("recoloured", n, "images")
    # map.json files
    for mj, pairs in ((pm / "map.json", [(OLD_SEQ, NEW_SEQ), (OLD_DIV, NEW_DIV)]),
                      (P / "spei/v1.0.0/map/map.json", [(OLD_IDX, NEW_IDX)]),
                      (P / "spi/v1.0.0/map/map.json", [(OLD_IDX, NEW_IDX)])):
        m = json.loads(mj.read_text(encoding="utf-8"))
        txt = json.dumps(m)
        for o, nw in pairs:
            txt = txt.replace(json.dumps(o), json.dumps(nw))
        m = json.loads(txt)
        m["palette_source"] = "ColorBrewer (colorbrewer2.org); SPEI/SPI classes as documented by the Copernicus Global Drought Observatory (RdBu-7)"
        mj.write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    # pipeline constants and the browser class table
    sub_file(ROOT / "scripts/pipelines/precip/build_precip.py", OLD_SEQ, NEW_SEQ)
    sub_file(ROOT / "scripts/pipelines/precip/build_precip.py", OLD_DIV, NEW_DIV)
    sub_file(ROOT / "scripts/pipelines/spei/build_spei.py", OLD_IDX, NEW_IDX)
    sub_file(ROOT / "scripts/pipelines/spi/build_spi.py", OLD_IDX, NEW_IDX)
    ts = ROOT / "src/lib/spei.ts"
    s = ts.read_text(encoding="utf-8")
    for o, nw in zip(OLD_IDX, NEW_IDX):
        s = re.sub(re.escape(o), nw, s)
    ts.write_text(s, encoding="utf-8")
    print("constants updated")


if __name__ == "__main__":
    main()
