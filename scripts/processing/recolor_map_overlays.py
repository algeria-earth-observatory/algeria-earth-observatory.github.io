"""Recolour the AEO map overlays (PNG) for light basemaps, without changing any class.

The precipitation and SPEI overlays are classified images: every pixel holds exactly one
class colour. This script swaps each class colour for its light-surface equivalent
(exact RGB match), so class boundaries and values are unchanged. Hyper-arid SPEI pixels
get a light sand with diagonal hatching, so that they are distinguished from the
near-normal class without relying on colour alone.

The new palettes are the ones now used by the pipelines (build_precip.py, build_spei.py):
  - sequential (annual precipitation): blue ramp, light (dry) -> dark (wet)
  - diverging (anomaly, SPEI): red <-> blue with a light grey neutral midpoint #f0efec
(steps from the AEO dataviz reference palette).

Usage: python scripts/processing/recolor_map_overlays.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PRECIP = ROOT / "public/data/aeo/products/precipitation/v1.0.0/map"
SPEI = ROOT / "public/data/aeo/products/spei/v1.0.0/map"

OLD_SEQ = ["#132a4a", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"]
NEW_SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
OLD_DIV = ["#6b1515", "#9e2424", "#d03b3b", "#ee8d81", "#4a5260", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
NEW_DIV = ["#6b1515", "#9e2424", "#d03b3b", "#ee8d81", "#f0efec", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
OLD_SPEI = ["#6b1515", "#d03b3b", "#ee8d81", "#4a5260", "#86b6ef", "#3987e5", "#0d366b"]
NEW_SPEI = ["#6b1515", "#d03b3b", "#ee8d81", "#f0efec", "#86b6ef", "#3987e5", "#0d366b"]
OLD_ARID = (92, 83, 64, 170)
ARID_BG, ARID_HATCH = "#e8dcc4", "#b49d72"

rgb = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def recolor(path: Path, old: list[str], new: list[str], arid: bool = False) -> None:
    a = np.array(Image.open(path).convert("RGBA"))
    out = a.copy()
    done = np.zeros(a.shape[:2], bool)
    for o, n in zip(old, new):
        m = (a[..., 0] == rgb(o)[0]) & (a[..., 1] == rgb(o)[1]) & (a[..., 2] == rgb(o)[2]) & (a[..., 3] > 0) & ~done
        out[m, :3] = rgb(n)
        done |= m
    if arid:
        m = np.all(a == OLD_ARID, axis=-1)
        yy, xx = np.indices(a.shape[:2])
        hatch = ((xx + yy) % 7) < 2
        out[m] = (*rgb(ARID_BG), 235)
        out[m & hatch] = (*rgb(ARID_HATCH), 235)
        done |= m
    left = (a[..., 3] > 0) & ~done
    if left.any():
        raise SystemExit(f"{path.name}: {int(left.sum())} pixels with an unexpected colour; nothing written")
    Image.fromarray(out).save(path, optimize=True)


def main() -> None:
    n = 0
    for p in sorted(PRECIP.glob("annual_*.png")):
        recolor(p, OLD_SEQ, NEW_SEQ); n += 1
    for p in sorted(PRECIP.glob("anomaly_*.png")):
        recolor(p, OLD_DIV, NEW_DIV); n += 1
    for p in sorted(SPEI.glob("spei*_*.png")):
        recolor(p, OLD_SPEI, NEW_SPEI, arid=True); n += 1
    pm = json.loads((PRECIP / "map.json").read_text(encoding="utf-8"))
    pm["annual"]["colors"], pm["anomaly"]["colors"] = NEW_SEQ, NEW_DIV
    (PRECIP / "map.json").write_text(json.dumps(pm, ensure_ascii=False) + "\n", encoding="utf-8")
    sm = json.loads((SPEI / "map.json").read_text(encoding="utf-8"))
    sm["colors"] = NEW_SPEI
    sm["hyper_arid"]["color"] = ARID_HATCH
    sm["hyper_arid"]["pattern"] = f"diagonal hatching {ARID_HATCH} on {ARID_BG}"
    (SPEI / "map.json").write_text(json.dumps(sm, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"recoloured {n} overlays")


if __name__ == "__main__":
    main()
