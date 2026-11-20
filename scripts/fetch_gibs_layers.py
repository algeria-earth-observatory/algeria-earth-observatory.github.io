"""Extract metadata for the NASA GIBS layers used by the AEO map explorer.

Reads the public GIBS WMTS GetCapabilities document (EPSG:3857, "best" endpoint)
and writes src/data/gibs-layers.json with, for each selected layer: title,
tile matrix set (max zoom), format, time dimension (default + available
periods) and the official legend / colour-map URLs.

Run:  python scripts/fetch_gibs_layers.py
No third-party dependencies.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

CAPS_URL = (
    "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/wmts.cgi"
    "?SERVICE=WMTS&REQUEST=GetCapabilities"
)
LAYERS = [
    "BlueMarble_NextGeneration",
    "VIIRS_SNPP_CorrectedReflectance_TrueColor",
    "ASTER_GDEM_Greyscale_Shaded_Relief",
    "MODIS_Terra_L3_NDVI_16Day",
    "MODIS_Terra_L3_Land_Surface_Temp_Monthly_Day",
    "IMERG_Precipitation_Rate",
    "SMAP_L3_Passive_Enhanced_Day_Soil_Moisture",
    "MERRA2_Dust_Surface_Mass_Concentration_Monthly",
]
OUT = Path(__file__).resolve().parents[1] / "src" / "data" / "gibs-layers.json"


def main() -> int:
    with urllib.request.urlopen(CAPS_URL, timeout=120) as r:
        caps = r.read().decode("utf-8").replace('"', "'")
    blocks = re.findall(r"<Layer>(.*?)</Layer>", caps, re.S)
    by_id = {}
    for b in blocks:
        m = re.search(r"<ows:Identifier>([^<]+)</ows:Identifier>", b)
        if m:
            by_id[m.group(1)] = b
    out = {"source": CAPS_URL, "retrieved": date.today().isoformat(), "layers": {}}
    missing = []
    for lid in LAYERS:
        b = by_id.get(lid)
        if b is None:
            missing.append(lid)
            continue
        tms = re.findall(r"<TileMatrixSet>([^<]+)</TileMatrixSet>", b)[0]
        fmt = re.findall(r"<Format>([^<]+)</Format>", b)[0]
        dflt = re.search(r"<Default>([^<]+)</Default>", b)
        values = re.findall(r"<Value>([^<]+)</Value>", b)
        legends = [
            re.search(r"xlink:href='([^']+)'", tag).group(1)
            for tag in re.findall(r"<LegendURL[^>]*>", b)
            if "horizontal" in tag
        ]
        cmaps = re.findall(r"xlink:href='([^']+colormaps/v1\.3/[^']+)'", b)
        templates = re.findall(r"<ResourceURL[^>]*template='([^']+)'", b)
        out["layers"][lid] = {
            "template": templates[0] if templates else None,
            "title": re.search(r"<ows:Title[^>]*>([^<]+)", b).group(1),
            "tile_matrix_set": tms,
            "max_zoom": int(tms.rsplit("Level", 1)[-1]),
            "format": fmt,
            "ext": "png" if fmt == "image/png" else "jpg",
            "time_default": dflt.group(1) if dflt else None,
            "time_periods": values,
            "legend_url": legends[0] if legends else None,
            "colormap_url": cmaps[0] if cmaps else None,
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(out['layers'])} layers)")
    if missing:
        print("MISSING:", missing, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
