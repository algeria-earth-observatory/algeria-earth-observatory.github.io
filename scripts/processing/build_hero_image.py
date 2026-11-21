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
    ap.add_argument("--style", choices=["overlay", "plate", "pixel"], default="overlay",
                    help="plate: no boundaries or graticule; surroundings faded towards the page colour")
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
    if a.style == "pixel":
        # Pixel Atlas: outside Algeria, imagery is averaged into square cells that thin out
        # and fade into limestone with distance from the border (cell colour = true block mean).
        from scipy.ndimage import distance_transform_edt
        lime = np.array([242, 239, 231], dtype=np.float32)
        m2 = np.asarray(mask).astype(np.float32) / 255.0
        dist = distance_transform_edt(m2 < 0.5)
        B, gap = 30, 2
        out = np.empty_like(arr); out[:] = lime
        rng = np.random.default_rng(7)
        dmax = width * 0.16
        for y in range(0, height, B):
            for x in range(0, width, B):
                blk = arr[y:y + B, x:x + B]
                d = float(dist[y:y + B, x:x + B].min())
                a_ = max(0.0, 1 - d / dmax) ** 1.3
                if a_ <= 0.04 or rng.random() > 0.35 + 0.65 * a_:
                    continue
                col = blk.reshape(-1, 3).mean(0)
                out[y:y + B - gap, x:x + B - gap] = col * a_ + lime * (1 - a_)
        mm = m2[..., None]
        out = np.clip(arr * mm + out * (1 - mm), 0, 255).astype(np.uint8)
        img = Image.fromarray(out)
        dest = ROOT / "public" / "images" / "hero"
        for w in (1800, 1000):
            im = img.resize((w, round(w * height / width)), Image.LANCZOS)
            im.save(dest / f"algeria-pixel-{w}.webp", quality=86, method=6)
            im.save(dest / f"algeria-pixel-{w}.jpg", quality=86, optimize=True, progressive=True)
        (dest / "SOURCE-pixel.json").write_text(json.dumps({
            "imagery": "NASA Blue Marble: Next Generation with shaded relief and bathymetry (GIBS layer " + a.layer + ")",
            "imagery_credit": "NASA Earth Observatory / NASA EOSDIS GIBS", "request": url,
            "projection": "EPSG:3857 (Web Mercator)", "bbox_wgs84": [W, S, E, N],
            "processing": "Pixels inside Algeria unchanged. Outside Algeria: 30-px cells holding the mean colour of the imagery beneath, faded towards limestone #F2EFE7 with distance from the border and thinned at random (seed 7). National outline (AEO boundaries " + a.boundaries + ") used as a mask only, not drawn.",
            "code": "scripts/processing/build_hero_image.py --style pixel",
        }, indent=2) + "\n", encoding="utf-8")
        print("ok pixel", width, height)
        return
    if a.style == "plate":
        chalk = np.array([247, 247, 243], dtype=np.float32)
        faded = 0.22 * grey + 0.78 * chalk
        m = (np.asarray(mask).astype(np.float32) / 255.0)[..., None]
        out = Image.fromarray(np.clip(arr * m + faded * (1 - m), 0, 255).astype(np.uint8))
        dest = ROOT / "public" / "images" / "hero"
        for w in (1800, 1000):
            im = out.resize((w, round(w * height / width)), Image.LANCZOS)
            im.save(dest / f"algeria-plate-{w}.webp", quality=84, method=6)
            im.save(dest / f"algeria-plate-{w}.jpg", quality=86, optimize=True, progressive=True)
        (dest / "SOURCE-plate.json").write_text(json.dumps({
            "imagery": "NASA Blue Marble: Next Generation with shaded relief and bathymetry (GIBS layer " + a.layer + ")",
            "imagery_credit": "NASA Earth Observatory / NASA EOSDIS GIBS",
            "request": url, "projection": "EPSG:3857 (Web Mercator)", "bbox_wgs84": [W, S, E, N],
            "processing": "Pixels inside Algeria unchanged; outside Algeria converted to grey and faded towards #F7F7F3 (national outline: AEO boundaries " + a.boundaries + ", used as a mask only, not drawn).",
            "code": "scripts/processing/build_hero_image.py --style plate",
        }, indent=2) + "\n", encoding="utf-8")
        print("ok plate", width, height)
        return
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
