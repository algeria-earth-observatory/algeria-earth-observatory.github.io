"""AEO evapotranspiration and soil-moisture product for Algeria from FAO WaPOR v3 (Level 1).

Inputs (data-work/wapor/, from fetch_wapor.py; open FAO WaPOR v3 rasters, no login):
  L1-AETI-M  actual evapotranspiration and interception, monthly, mm/month (300 m, read at the 1.17 km overview)
  L1-RET-M   reference evapotranspiration (FAO-56 Penman–Monteith), monthly, mm/month (~30 km)
  L1-RSM-D   relative soil moisture, dekadal (300 m, read at the 1.17 km overview); the catalogue
             unit is "%" with scale 0.001, but the scaled values are fractions 0–1, converted to %
  data-work/cropland/stable_cropland_v1.npz (AEO stable cropland from GACED30, build_stable_cropland.py)

Method:
  * Monthly relative soil moisture = mean of the month's dekads (at least 2 of 3 required).
  * RET is resampled bilinearly to the 1.17 km grid.
  * Unit statistics are area-weighted means over communes (coverage fractions), merged exactly into
    wilayas and Algeria. "Cropland" statistics weight each cell by its stable-cropland area, so they
    describe only land that GACED30 maps as cropland in at least 20 of 25 years; they are left empty
    where a unit has under 1,000 ha (10 km²) of stable cropland.
  * Departures use the 2018–2025 mean of the same calendar month (8 years — a short baseline, not a
    climate normal): AETI as % of that mean, soil moisture as percentage points.

Output: public/data/aeo/products/et-soil-moisture/v1.0.0/
Usage:  python scripts/pipelines/wapor/build_wapor.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import Resampling, reproject

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/pipelines"))
from aeo.product import MercatorPNG, Units, r, sha256, write_json, write_manifest, write_table  # noqa: E402
from aeo.stats import Grid  # noqa: E402

VERSION = "1.0.0"
SRC = ROOT / "data-work/wapor"
CROP = ROOT / "data-work/cropland/stable_cropland_v1.npz"
if not CROP.exists():  # automated builds: the published AEO cropland mask holds the same grids
    CROP = ROOT / "public/data/aeo/products/stable-cropland/v1.0.0/mask/aeo_stable_cropland_grids_v1.0.0.npz"
OUT = ROOT / f"public/data/aeo/products/et-soil-moisture/v{VERSION}"
SITE = f"/data/aeo/products/et-soil-moisture/v{VERSION}"
GRID = Grid(west=-8.75390625, north=37.25390625, res=0.01171875, ncol=1771, nrow=1566)
BASE = (2018, 2025)
MIN_CROP_HA = 1000.0
# ColorBrewer GnBu-7 (the WaPOR AETI palette family), class breaks in mm/month
AETI_BREAKS = [2, 5, 10, 20, 40, 80]
AETI_COLORS = ["#f0f9e8", "#ccebc5", "#a8ddb5", "#7bccc4", "#4eb3d3", "#2b8cbe", "#08589e"]
# ColorBrewer BrBG-7, dry (brown) to wet (teal), relative soil moisture %
RSM_BREAKS = [10, 20, 30, 40, 50, 60]
RSM_COLORS = ["#8c510a", "#d8b365", "#f6e8c3", "#f5f5f5", "#c7eae5", "#5ab4ac", "#01665e"]


def read(path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as s:
        a = s.read(1).astype("float32")
        tags = s.tags()
        nod = s.nodata
        t = s.transform
        shape = a.shape
        crs = s.crs
    a[a == nod] = np.nan
    a *= float(tags.get("scale", 0.1))
    return a, {"transform": t, "shape": shape, "crs": crs, **tags}


def on_grid(a: np.ndarray, meta: dict, resampling=Resampling.bilinear) -> np.ndarray:
    if meta["shape"] == (GRID.nrow, GRID.ncol) and np.allclose(tuple(meta["transform"])[:6], tuple(GRID.transform)[:6]):
        return a
    out = np.full((GRID.nrow, GRID.ncol), np.nan, np.float32)
    reproject(a, out, src_transform=meta["transform"], src_crs=meta["crs"], src_nodata=np.nan,
              dst_transform=GRID.transform, dst_crs="EPSG:4326", dst_nodata=np.nan, resampling=resampling)
    return out


def main() -> None:
    cat = json.loads((SRC / "catalog.json").read_text(encoding="utf-8"))
    aeti_items = {it["start"][:7]: it for it in cat["L1-AETI-M"]}
    ret_items = {it["start"][:7]: it for it in cat["L1-RET-M"]}
    rsm_by_month = defaultdict(list)
    for it in cat["L1-RSM-D"]:
        rsm_by_month[it["start"][:7]].append(it)
    months = sorted(set(aeti_items) & set(ret_items) & {m for m, v in rsm_by_month.items() if len(v) >= 2})
    print("months", months[0], "→", months[-1], len(months), flush=True)

    units = Units(GRID)
    crop = np.load(CROP)
    gdef = crop["grid_wapor1km_def"]
    assert np.allclose(gdef, [GRID.west, GRID.north, GRID.res, GRID.ncol, GRID.nrow]), gdef
    cell_ha = np.broadcast_to(GRID.cell_area_km2() * 100.0, (GRID.nrow, GRID.ncol))
    stable_share = np.clip(crop["grid_wapor1km_stable_ha"] / cell_ha, 0, 1)
    inside = crop["grid_wapor1km_valid_ha"] > 0

    levels = ["admin0", "admin1", "admin2"]
    W = {lv: units.weights(lv) for lv in levels}
    Wc = {lv: Units.reweight(W[lv], stable_share) for lv in levels}
    crop_ha = {lv: np.array([float(w.sum()) for w in Wc[lv].weights]) * 100.0 for lv in levels}  # km² → ha
    res = {lv: {k: np.full((len(units.meta[lv]), len(months)), np.nan) for k in
                ("aeti", "ret", "rsm", "aeti_crop", "rsm_crop", "valid")} for lv in levels}

    mp = MercatorPNG(GRID, 2500, inside)
    (OUT / "map").mkdir(parents=True, exist_ok=True)
    for j, m in enumerate(months):
        aeti, ma = read(SRC / "L1-AETI-M" / f"{aeti_items[m]['code']}.tif")
        aeti = on_grid(aeti, ma, Resampling.nearest)
        ret, mr = read(SRC / "L1-RET-M" / f"{ret_items[m]['code']}.tif")
        ret = on_grid(ret, mr)
        stack = []
        for it in rsm_by_month[m]:
            a, md = read(SRC / "L1-RSM-D" / f"{it['code']}.tif")
            # The WaPOR catalogue lists RSM in "%" with scale 0.001, but scaled values are fractions
            # (0–1; raw 0–1000), so they are converted to percent here.
            stack.append(100.0 * on_grid(a, md, Resampling.nearest))
        with np.errstate(all="ignore"):
            rsm = np.nanmean(np.stack(stack), 0)
            rsm[np.sum(~np.isnan(np.stack(stack)), 0) < 2] = np.nan
        for lv in levels:
            res[lv]["aeti"][:, j], res[lv]["valid"][:, j] = W[lv].mean(aeti)
            res[lv]["ret"][:, j], _ = W[lv].mean(ret)
            res[lv]["rsm"][:, j], _ = W[lv].mean(rsm)
            res[lv]["aeti_crop"][:, j], _ = Wc[lv].mean(aeti)
            res[lv]["rsm_crop"][:, j], _ = Wc[lv].mean(rsm)
        mp.write(OUT / "map" / f"aeti_{m}.png", aeti, AETI_BREAKS, AETI_COLORS)
        mp.write(OUT / "map" / f"rsm_{m}.png", rsm, RSM_BREAKS, RSM_COLORS)
        if j % 12 == 0:
            print(m, "national AETI", round(res["admin0"]["aeti"][0, j], 1), "RET", round(res["admin0"]["ret"][0, j], 1),
                  "RSM", round(res["admin0"]["rsm"][0, j], 1), "crop AETI", round(res["admin0"]["aeti_crop"][0, j], 1), flush=True)

    mon = np.array([int(m[5:7]) for m in months])
    yr = np.array([int(m[:4]) for m in months])
    base = (yr >= BASE[0]) & (yr <= BASE[1])
    assets, web_assets, qc = [], {}, []
    for lv in levels:
        d = res[lv]
        for k in ("aeti_crop", "rsm_crop"):
            d[k][crop_ha[lv] < MIN_CROP_HA] = np.nan
        clim = {k: np.full_like(d[k], np.nan) for k in ("aeti", "rsm", "aeti_crop", "rsm_crop")}
        for mm in range(1, 13):
            sel = mon == mm
            for k in clim:
                with np.errstate(all="ignore"):
                    clim[k][:, sel] = np.nanmean(d[k][:, sel & base], 1, keepdims=True)
        with np.errstate(all="ignore"):
            d["aeti_dep_pct"] = np.where(clim["aeti"] >= 1, 100 * (d["aeti"] - clim["aeti"]) / clim["aeti"], np.nan)
            d["aeti_crop_dep_pct"] = np.where(clim["aeti_crop"] >= 1, 100 * (d["aeti_crop"] - clim["aeti_crop"]) / clim["aeti_crop"], np.nan)
            d["rsm_dep_pp"] = d["rsm"] - clim["rsm"]
            d["rsm_crop_dep_pp"] = d["rsm_crop"] - clim["rsm_crop"]
            d["et_ratio"] = np.where(d["ret"] > 1, d["aeti"] / d["ret"], np.nan)
        meta = units.meta[lv]
        rows = []
        for i, u in enumerate(meta):
            for j, m in enumerate(months):
                rows.append((u["code"], u["name"], u["parent"], int(m[:4]), int(m[5:7]),
                             d["aeti"][i, j], d["ret"][i, j], d["et_ratio"][i, j], d["rsm"][i, j],
                             d["aeti_dep_pct"][i, j], d["rsm_dep_pp"][i, j],
                             d["aeti_crop"][i, j], d["rsm_crop"][i, j], d["aeti_crop_dep_pct"][i, j], d["rsm_crop_dep_pp"][i, j],
                             crop_ha[lv][i], d["valid"][i, j]))
        df = pd.DataFrame(rows, columns=["unit_code", "unit_name", "parent_code", "year", "month",
                                         "aeti_mm", "ret_mm", "aeti_ret_ratio", "rsm_pct", "aeti_departure_pct", "rsm_departure_pp",
                                         "aeti_cropland_mm", "rsm_cropland_pct", "aeti_cropland_departure_pct", "rsm_cropland_departure_pp",
                                         "stable_cropland_ha", "valid_fraction"])
        for c in df.columns[5:]:
            df[c] = df[c].round(3 if c in ("aeti_ret_ratio", "valid_fraction") else 2)
        assets += write_table(df, OUT, "aeo_et_sm_monthly", lv, VERSION, "Monthly ET and soil moisture (WaPOR v3)", csv=lv != "admin2")
        web_units = [{**u, "cropland_ha": round(float(crop_ha[lv][i]))} for i, u in enumerate(meta)]
        series = {k: r(d[k], 1) for k in ("aeti", "ret", "rsm", "aeti_crop", "rsm_crop", "aeti_dep_pct", "rsm_dep_pp", "rsm_crop_dep_pp", "aeti_crop_dep_pct")}
        payload = {"product": "aeo-dza-et-soil-moisture-wapor3", "version": VERSION, "level": lv, "months": months,
                   "baseline": f"{BASE[0]}-{BASE[1]}", "min_cropland_ha": MIN_CROP_HA}
        if lv == "admin2":
            for wc in sorted({u["parent"] for u in meta}):
                idx = [i for i, u in enumerate(meta) if u["parent"] == wc]
                write_json(OUT / "web/admin2" / f"{wc}.json", {**payload, "units": [web_units[i] for i in idx],
                                                               "series": {k: [v[i] for i in idx] for k, v in series.items()}})
            web_assets["admin2"] = f"{SITE}/web/admin2/{{wilaya_code}}.json"
        else:
            write_json(OUT / "web" / f"{lv}.json", {**payload, "units": web_units, "series": series})
            web_assets[lv] = f"{SITE}/web/{lv}.json"

    # QC: national = weighted mean of wilayas (exact nesting)
    w1 = np.array([w.sum() for w in units.w1.weights])
    j = len(months) - 1
    a1 = res["admin1"]["aeti"][:, j]
    ok = ~np.isnan(a1)
    recon = float((a1[ok] * w1[ok]).sum() / w1[ok].sum())
    nat = float(res["admin0"]["aeti"][0, j])
    qc.append(f"National AETI {months[j]} {nat:.3f} mm vs wilaya-weighted {recon:.3f} mm")
    assert abs(recon - nat) < 0.05 * max(1, nat), (recon, nat)
    assert np.nanmin(res["admin1"]["rsm"]) >= 0 and np.nanmax(res["admin1"]["rsm"]) <= 100
    stable_total = float(crop_ha["admin0"][0])
    qc.append(f"Stable cropland weight in Algeria: {stable_total:,.0f} ha")

    map_meta = {"coordinates": mp.coordinates, "months": months,
                "aeti": {"breaks": AETI_BREAKS, "colors": AETI_COLORS, "units": "mm/month", "palette": "ColorBrewer GnBu-7 (WaPOR AETI colour family)"},
                "rsm": {"breaks": RSM_BREAKS, "colors": RSM_COLORS, "units": "%", "palette": "ColorBrewer BrBG-7"},
                "resampling": "nearest neighbour from the 1.17 km WaPOR overview to 2.5 km Web Mercator pixels (display only)"}
    (OUT / "map" / "map.json").write_text(json.dumps(map_meta, indent=1), encoding="utf-8")
    web_assets["map"] = f"{SITE}/map/map.json"
    inputs = {m: [{"code": it["code"], "url": it["url"]} for it in v] for m, v in cat.items()}
    write_manifest(OUT, {
        "product_id": "aeo-dza-et-soil-moisture-wapor3",
        "title": "Algeria evapotranspiration and soil moisture (FAO WaPOR v3), monthly: national, wilaya and commune, all land and stable cropland",
        "status": "available", "version": VERSION, "geographic_scope": "Algeria",
        "available_levels": levels, "spatial_products_levels": [],
        "source_product": "FAO WaPOR v3 Level 1 (L1-AETI-M, L1-RET-M, L1-RSM-D)", "source_version": "WaPOR v3",
        "source_doi": None, "source_license": "CC BY 4.0 (FAO WaPOR data licence)", "license": "CC BY 4.0",
        "temporal_coverage": {"monthly": [months[0], months[-1]]}, "reference_period": list(BASE),
        "spatial_resolution": "Administrative units (from WaPOR 300 m rasters read at the 1.17 km average overview)",
        "crs": "not applicable (tables by administrative unit; boundaries EPSG:4326)",
        "units": "AETI and RET mm/month; relative soil moisture %; departures % (AETI) and percentage points (soil moisture) from the 2018–2025 mean",
        "formats": ["CSV", "PARQUET"], "processing_code": "scripts/pipelines/wapor/build_wapor.py",
        "methodology_url": "/docs/method-et-soil-moisture/",
        "cropland_mask": "AEO stable cropland v1 (GACED30, cropland in ≥ 20 of 25 years 2000–2024)",
        "download_assets": assets, "web_assets": web_assets, "qc": qc,
    }, {"product": "aeo-dza-et-soil-moisture-wapor3", "version": VERSION, "inputs": inputs,
        "cropland_mask": {"file": CROP.name, "sha256": sha256(CROP)},
        "method": __doc__, "qc": qc})
    print("\n".join(qc))
    print("written", OUT)


if __name__ == "__main__":
    main()
