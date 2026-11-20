"""Render the AEO hero/preview image of Algeria from NASA GIBS imagery.

Imagery: NASA Blue Marble: Next Generation (MODIS-based monthly composite, 2004),
served by NASA GIBS WMS (EPSG:3857). The image is masked so that Algeria
(AEO OSM-derived national boundary) is shown at full brightness while
surrounding areas are dimmed; wilaya boundaries and a 5-degree graticule are
drawn on top. No pixel values are altered inside Algeria other than JPEG/WebP
compression.

Run with a Python that has Pillow + numpy:
  python scripts/processing/build_hero_image.py --boundaries 2026-11-19
"""
from __future__ import annotations

import argparse
import io
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
R = 6378137.0
W, E, S, N = -11.5, 15.5, 17.0, 38.6
WMS = "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi"


def mx(lon: float) -> float:
    return R * math.radians(lon)


def my(lat: float) -> float:
    return R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boundaries", required=True, help="boundary version folder, e.g. 2026-11-19")
    ap.add_argument("--layer", default="BlueMarble_ShadedRelief_Bathymetry")
    ap.add_argument("--width", type=int, default=2400)
    a = ap.parse_args()

    x0, x1, y0, y1 = mx(W), mx(E), my(S), my(N)
    width = a.width
    height = round(width * (y1 - y0) / (x1 - x0))
    params = {
        "SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0", "LAYERS": a.layer,
        "STYLES": "", "CRS": "EPSG:3857", "BBOX": f"{x0},{y0},{x1},{y1}",
        "WIDTH": width, "HEIGHT": height, "FORMAT": "image/jpeg",
    }
    url = WMS + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=300) as r:
        base = Image.open(io.BytesIO(r.read())).convert("RGB")

    def px(lon: float, lat: float) -> tuple[float, float]:
        return ((mx(lon) - x0) / (x1 - x0) * width, (y1 - my(lat)) / (y1 - y0) * height)

    bdir = ROOT / "public" / "data" / "aeo" / "boundaries" / a.boundaries
    adm0 = json.loads((bdir / "dza_adm0_display.geojson").read_text(encoding="utf-8"))
    adm1 = json.loads((bdir / "dza_adm1_wilayas_display.geojson").read_text(encoding="utf-8"))

    def rings(geom):
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            for ring in poly:
                yield [px(lon, lat) for lon, lat in ring]

    mask = Image.new("L", (width, height), 0)
    md = ImageDraw.Draw(mask)
    for f in adm0["features"]:
        polys = f["geometry"]["coordinates"] if f["geometry"]["type"] == "MultiPolygon" else [f["geometry"]["coordinates"]]
        for poly in polys:
            md.polygon([px(lo, la) for lo, la in poly[0]], fill=255)
            for hole in poly[1:]:
                md.polygon([px(lo, la) for lo, la in hole], fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))

    arr = np.asarray(base).astype(np.float32)
    grey = arr.mean(axis=2, keepdims=True)
    dim = (0.35 * arr + 0.65 * grey) * 0.42 + np.array([20, 59, 86], dtype=np.float32) * 0.22
    m = (np.asarray(mask).astype(np.float32) / 255.0)[..., None]
    out = Image.fromarray(np.clip(arr * m + dim * (1 - m), 0, 255).astype(np.uint8))

    over = Image.new("RGBA", out.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    for lon in range(-10, 16, 5):
        d.line([px(lon, S), px(lon, N)], fill=(247, 249, 250, 46), width=1)
    for lat in range(20, 40, 5):
        d.line([px(W, lat), px(E, lat)], fill=(247, 249, 250, 46), width=1)
    for f in adm1["features"]:
        for ring in rings(f["geometry"]):
            d.line(ring + [ring[0]], fill=(247, 249, 250, 80), width=1)
    for f in adm0["features"]:
        for ring in rings(f["geometry"]):
            d.line(ring + [ring[0]], fill=(247, 249, 250, 230), width=3)
    out = Image.alpha_composite(out.convert("RGBA"), over).convert("RGB")

    dest = ROOT / "public" / "images" / "hero"
    dest.mkdir(parents=True, exist_ok=True)
    for w in (1600, 960):
        im = out.resize((w, round(w * height / width)), Image.LANCZOS)
        im.save(dest / f"algeria-bluemarble-{w}.webp", quality=82, method=6)
        im.save(dest / f"algeria-bluemarble-{w}.jpg", quality=84, optimize=True, progressive=True)
    (dest / "SOURCE.json").write_text(json.dumps({
        "imagery": "NASA Blue Marble: Next Generation with shaded relief and bathymetry (GIBS layer " + a.layer + ")",
        "imagery_credit": "NASA Earth Observatory / NASA EOSDIS GIBS",
        "request": url,
        "boundaries": f"AEO OSM-derived boundaries, version {a.boundaries} (ODbL 1.0, © OpenStreetMap contributors)",
        "projection": "EPSG:3857 (Web Mercator)",
        "bbox_wgs84": [W, S, E, N],
        "code": "scripts/processing/build_hero_image.py",
    }, indent=2) + "\n", encoding="utf-8")
    print("ok", width, height)


if __name__ == "__main__":
    main()
