"""AEO stable cropland mask for Algeria from GACED30 v1 (annual 30 m cropland, 2000–2024).

Definition: a 30 m pixel is **stable cropland** when GACED30 maps it as cropland in at least
20 of the 25 years 2000–2024 (80 %). GACED30 counts active fallow as cropland, so cereal–fallow
rotations stay in the class; pixels mapped as cropland only in a few years (including the
2003–2006 artefacts between Ghardaïa and Ouargla noted in the AEO GACED30 README) are excluded.
Counts for every threshold (1–25 years) are kept per commune so other definitions can be derived.

Input:  data-work/gaced30/out/gaced30_dza_<year>_v1.tif (AEO clip of GACED30; 0 non-crop, 10 crop, 255 outside)
        public/data/aeo/boundaries/2026-11-20/dza_adm2_communes.geojson
Areas:  every pixel's true area on the WGS 84 sphere-equivalent (authalic radius) — pixel counts are
        never used as areas.
Output: data-work/cropland/stable_cropland_v1.npz with
          years_hist_ha[commune, k]  area (ha) cropland in exactly k of 25 years (k = 0..25)
          grid_<name>_{valid,ever,majority,stable}_ha  area per target grid cell
        and the grid definitions (west, north, res, ncol, nrow).

Usage: python scripts/pipelines/cropland/build_stable_cropland.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window
from shapely import box

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data-work/gaced30/out"
BND = ROOT / "public/data/aeo/boundaries/2026-11-20/dza_adm2_communes.geojson"
OUT = ROOT / "data-work/cropland"
YEARS = list(range(2000, 2025))
STABLE_MIN = 20
MAJORITY_MIN = 13
TILE = 2048
R = 6371007.2  # authalic radius (m)

# target grids: (west edge, north edge, resolution, ncol, nrow)
GRIDS = {
    "chirps005": (-9.0, 37.5, 0.05, 430, 380),          # AEO CHIRPS v3 grid (build_precip.py)
    "wapor1km": (-8.75390625, 37.25390625, 0.01171875, 1771, 1566),  # WaPOR v3 L1 overview level 1, global origin −180/90
    "cmip025": (-8.875, 37.5, 0.25, 84, 75),             # NEX-GDDP-CMIP6 0.25°: lon centres on multiples of 0.25, lat centres at x.125
    "grace025": (-9.0, 37.5, 0.25, 86, 76),              # Li & Kusche GRACE 0.25° (centres at x.125 in lon and lat)
    "nmme1": (-9.5, 37.5, 1.0, 22, 19),                  # NMME / CPT 1° grid (cell centres on whole degrees)
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    srcs = [rasterio.open(SRC / f"gaced30_dza_{y}_v1.tif") for y in YEARS]
    s0 = srcs[0]
    T = s0.transform
    W, H = s0.width, s0.height
    res = T.a
    communes = gpd.read_file(BND).to_crs(4326).reset_index(drop=True)
    codes = communes["commune_code"].astype(str).tolist()
    sidx = communes.sindex
    nC = len(communes)
    hist = np.zeros((nC + 1, len(YEARS) + 1), dtype=np.float64)  # last row: pixels in Algeria but no commune
    acc = {g: {k: np.zeros((d[4], d[3])) for k in ("valid", "ever", "majority", "stable")} for g, d in GRIDS.items()}
    t0 = time.time()
    ntiles = ((H + TILE - 1) // TILE) * ((W + TILE - 1) // TILE)
    done = 0
    for r0 in range(0, H, TILE):
        h = min(TILE, H - r0)
        lat_top = T.f + T.e * np.arange(r0, r0 + h)          # top edge of each row
        lat_bot = lat_top + T.e
        row_area_ha = (R ** 2) * np.deg2rad(res) * np.abs(np.sin(np.deg2rad(lat_top)) - np.sin(np.deg2rad(lat_bot))) / 1e4
        lat_c = lat_top + T.e / 2
        for c0 in range(0, W, TILE):
            w = min(TILE, W - c0)
            done += 1
            win = Window(c0, r0, w, h)
            first = srcs[0].read(1, window=win)
            inside = first != 255
            if not inside.any():
                continue
            count = np.zeros((h, w), dtype=np.uint8)
            for s in srcs:
                count += (s.read(1, window=win) == 10)
            area = np.broadcast_to(row_area_ha[:, None], (h, w))
            # communes
            wt = rasterio.windows.transform(win, T)
            bx = box(*rasterio.windows.bounds(win, T))
            cand = sidx.query(bx, predicate="intersects")
            if len(cand):
                cid = rasterize(((communes.geometry.iloc[i], i + 1) for i in cand), out_shape=(h, w), transform=wt,
                                fill=0, dtype="int32")
            else:
                cid = np.zeros((h, w), dtype="int32")
            cid = np.where(cid == 0, nC + 1, cid) - 1  # 0-based; nC = no commune
            m = inside
            flat = cid[m].astype(np.int64) * (len(YEARS) + 1) + count[m]
            hist += np.bincount(flat, weights=area[m], minlength=hist.size).reshape(hist.shape)
            # grids
            lon_c = T.c + res * (np.arange(c0, c0 + w) + 0.5)
            for g, (gw, gn, gr, gc, grn) in GRIDS.items():
                ci = np.floor((lon_c - gw) / gr).astype(np.int64)
                ri = np.floor((gn - lat_c) / gr).astype(np.int64)
                ok_c = (ci >= 0) & (ci < gc)
                ok_r = (ri >= 0) & (ri < grn)
                mm = m & ok_r[:, None] & ok_c[None, :]
                idx = (ri[:, None] * gc + ci[None, :])[mm]
                a = area[mm]
                cnt = count[mm]
                for key, sel in (("valid", None), ("ever", cnt >= 1), ("majority", cnt >= MAJORITY_MIN), ("stable", cnt >= STABLE_MIN)):
                    wts = a if sel is None else a * sel
                    acc[g][key] += np.bincount(idx, weights=wts, minlength=gc * grn).reshape(grn, gc)
            if done % 50 == 0:
                print(f"{done}/{ntiles} tiles, {time.time() - t0:.0f}s, stable so far {hist[:, STABLE_MIN:].sum():,.0f} ha", flush=True)
    out = {"years_hist_ha": hist, "commune_codes": np.array(codes + ["(none)"]), "years": np.array(YEARS),
           "stable_min": STABLE_MIN, "majority_min": MAJORITY_MIN}
    for g, d in GRIDS.items():
        out[f"grid_{g}_def"] = np.array(d[:3] + (d[3], d[4]), dtype=float)
        for k, v in acc[g].items():
            out[f"grid_{g}_{k}_ha"] = v
    np.savez_compressed(OUT / "stable_cropland_v1.npz", **out)
    tot = hist.sum()
    print(json.dumps({"algeria_ha": round(tot), "ever_ha": round(hist[:, 1:].sum()), "majority_ha": round(hist[:, MAJORITY_MIN:].sum()),
                      "stable_ha": round(hist[:, STABLE_MIN:].sum()), "all25_ha": round(hist[:, 25].sum()),
                      "no_commune_ha": round(hist[nC].sum()), "seconds": round(time.time() - t0)}, indent=1))


if __name__ == "__main__":
    main()
