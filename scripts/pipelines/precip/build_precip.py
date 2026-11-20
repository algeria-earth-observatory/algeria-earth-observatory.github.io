"""Steps 2-8 — build the AEO product "Algeria Precipitation (CHIRPS v3.0)".

Input : data-work/precip/raw/chirps3_YYYY.MM.npy + index.json  (fetch_chirps3.py)
        public/data/aeo/boundaries/<BOUNDARY_VERSION>/dza_adm{1,2}_*.geojson
Output: public/data/aeo/products/precipitation/v<VERSION>/
          raster/  Cloud Optimized GeoTIFFs (Algeria, and one per wilaya)
          tables/  CSV and Parquet statistics (admin 0, 1, 2)
          web/     compact JSON used by the website (Analyze, Regions)
          map/     Web Mercator PNG overlays used by the maps
          manifest.json, PROVENANCE.json

Method (also in src/content/docs/method-precipitation.md)
  * Monthly CHIRPS v3.0 final precipitation (mm), 0.05° grid. Annual total = sum of the
    12 months of a calendar year; only complete years are published.
  * Reference period 1991-2020 (WMO standard normal). Anomaly = value - normal (mm);
    relative anomaly = 100 x (value - normal) / normal (%), not computed where the
    normal is below 1 mm.
  * Zonal statistics: area-weighted mean depth (mm) over each unit, weights = fraction
    of the CHIRPS cell inside the unit (10 x 10 supersampling) x geodesic cell area.
    Wilaya and national weights are the union of commune weights (exact nesting).
  * Trend 1981-last complete year: Theil-Sen slope with 95 % Sen interval; Mann-Kendall
    test, with Yue & Wang (2004) correction when lag-1 autocorrelation is significant.

Usage: python scripts/pipelines/precip/build_precip.py
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import unicodedata
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.shutil
from rasterio.io import MemoryFile
from rasterio.transform import array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "pipelines"))
from aeo.stats import Grid, ZonalWeights, mann_kendall, sparse_coverage, theil_sen  # noqa: E402

PRODUCT_ID = "aeo-dza-precipitation-chirps3"
VERSION = "1.0.0"
BOUNDARY_VERSION = "2026-11-20"
BASELINE = (1991, 2020)
# test-only overrides (never used for publication): AEO_PRECIP_OUT, AEO_PRECIP_BASELINE="1981-1982"
import os  # noqa: E402
if os.environ.get("AEO_PRECIP_BASELINE"):
    BASELINE = tuple(int(v) for v in os.environ["AEO_PRECIP_BASELINE"].split("-"))
RAW = Path(os.environ["AEO_PRECIP_RAW"]) if os.environ.get("AEO_PRECIP_RAW") else ROOT / "data-work" / "precip" / "raw"
BDIR = ROOT / "public" / "data" / "aeo" / "boundaries" / BOUNDARY_VERSION
OUT = Path(os.environ["AEO_PRECIP_OUT"]) if os.environ.get("AEO_PRECIP_OUT") else ROOT / "public" / "data" / "aeo" / "products" / "precipitation" / f"v{VERSION}"
SITE_PREFIX = f"/data/aeo/products/precipitation/v{VERSION}"
GRID = Grid(west=-9.0, north=37.5, res=0.05, ncol=430, nrow=380)
NODATA = -9999.0

# map colours (validated with the dataviz palette checks; see docs/METHODS_PRECIPITATION.md)
SEQ_BREAKS = [25, 50, 100, 200, 400, 700]
SEQ_COLORS = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIV_BREAKS = [-60, -40, -25, -10, 10, 25, 40, 60]
DIV_COLORS = ["#6b1515", "#9e2424", "#d03b3b", "#ee8d81", "#e6e4df", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def r1(x):
    """Round to 0.1 for publication; NaN -> None."""
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 1)


# --------------------------------------------------------------------------- load + QC
def load_cube():
    index = json.loads((RAW / "index.json").read_text())
    months = sorted(f["month"] for f in index["files"] if f["status"] in ("downloaded", "cached"))
    qc = []
    # continuity
    expected, (y, m) = [], (1981, 1)
    while f"{y}.{m:02d}" <= months[-1]:
        expected.append(f"{y}.{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    missing = sorted(set(expected) - set(months))
    if missing:
        raise SystemExit(f"missing months: {missing}")
    qc.append(f"Monthly series complete: {months[0]} to {months[-1]} ({len(months)} months, no gaps)")
    cube = np.stack([np.load(RAW / f"chirps3_{mo}.npy") for mo in months]).astype("float32")
    assert cube.shape[1:] == (GRID.nrow, GRID.ncol)
    nan_pattern = np.isnan(cube)
    if not (nan_pattern == nan_pattern[0]).all():
        changing = int((nan_pattern != nan_pattern[0]).any(0).sum())
        qc.append(f"WARNING: land/sea mask varies between months in {changing} cells")
    else:
        qc.append("Same valid-cell mask in every month")
    if np.nanmin(cube) < 0:
        raise SystemExit("negative precipitation")
    qc.append(f"Values within [0, {np.nanmax(cube):.1f}] mm/month; no negative values")
    return months, cube, index, qc


def main() -> None:
    months, cube, index, qc = load_cube()
    years_all = sorted({int(m[:4]) for m in months})
    complete = [y for y in years_all if sum(m.startswith(f"{y}.") for m in months) == 12]
    years = [y for y in complete if y >= 1981]
    ym = np.array([[int(m[:4]), int(m[5:])] for m in months])
    annual = np.stack([cube[ym[:, 0] == y].sum(0) for y in years])  # NaN propagates (sea)
    b0, b1 = years.index(BASELINE[0]), years.index(BASELINE[1])
    normal = annual[b0:b1 + 1].mean(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        anom_pct = np.where(normal >= 1, 100 * (annual - normal) / normal, np.nan)
    qc.append(f"Annual totals for complete years {years[0]}-{years[-1]} ({len(years)} years); "
              f"partial year(s) excluded: {[y for y in years_all if y not in complete]}")

    # ---------------------------------------------------------------- boundaries + weights
    adm2 = gpd.read_file(BDIR / "dza_adm2_communes.geojson").sort_values("commune_code").reset_index(drop=True)
    adm1 = gpd.read_file(BDIR / "dza_adm1_wilayas.geojson").sort_values("wilaya_code").reset_index(drop=True)
    sp, tiny = sparse_coverage(list(adm2.geometry.values), GRID, supersample=10)
    w2 = ZonalWeights(sp, GRID)
    groups1 = [list(adm2.index[adm2.wilaya_code == c]) for c in adm1.wilaya_code]
    w1 = ZonalWeights.merge(w2, groups1)
    w0 = ZonalWeights.merge(w2, [list(adm2.index)])
    qc.append(f"{len(tiny)} commune(s) smaller than a 0.005° sub-cell use their representative-point cell: "
              f"{adm2.loc[tiny, 'commune_code'].tolist()}")
    inside = np.zeros(GRID.nrow * GRID.ncol, bool)
    inside[w0.cells[0]] = True
    inside = inside.reshape(GRID.nrow, GRID.ncol)
    cov_frac = np.zeros(GRID.nrow * GRID.ncol)
    cov_frac[w0.cells[0]] = w0.fractions[0]
    area_check = float((w0.weights[0]).sum())
    qc.append(f"Algeria area from cell weights: {area_check:,.0f} km² (boundary polygon, geodesic: see boundary PROVENANCE)")

    levels = {
        "admin0": {"w": w0, "units": pd.DataFrame([{"code": "DZ", "name": "Algeria", "name_ar": "الجزائر", "parent": None}])},
        "admin1": {"w": w1, "units": pd.DataFrame({"code": adm1.wilaya_code, "name": adm1["name"], "name_ar": adm1.name_ar, "parent": "DZ"})},
        "admin2": {"w": w2, "units": pd.DataFrame({"code": adm2.commune_code, "name": adm2["name"], "name_ar": adm2.name_ar, "parent": adm2.wilaya_code})},
    }

    # ---------------------------------------------------------------- outputs dir
    if OUT.exists():
        shutil.rmtree(OUT)
    for d in ("raster/wilaya", "tables", "web/monthly_admin2", "map"):
        (OUT / d).mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- rasters
    def write_cog(path: Path, data: np.ndarray, descriptions: list[str], transform, tags: dict):
        data = np.where(np.isnan(data), NODATA, np.round(data, 1)).astype("float32")
        prof = dict(driver="GTiff", dtype="float32", count=data.shape[0], height=data.shape[1], width=data.shape[2],
                    crs="EPSG:4326", transform=transform, nodata=NODATA)
        with MemoryFile() as mem:
            with mem.open(**prof) as ds:
                ds.write(data)
                for i, d in enumerate(descriptions, 1):
                    ds.set_band_description(i, d)
                ds.update_tags(**tags)
            rasterio.shutil.copy(mem.name, path, driver="COG", compress="DEFLATE", predictor=3, level=9,
                                 blocksize=256, overview_resampling="average")

    base_tags = {"product": PRODUCT_ID, "version": VERSION, "source": "CHIRPS v3.0 final monthly (doi:10.15780/G2JQ0P), CC BY 4.0",
                 "units": "mm", "processing": "Algeria Earth Observatory", "boundary_version": BOUNDARY_VERSION}
    masked = lambda a: np.where(inside, a, np.nan)  # noqa: E731
    files = {}
    p = OUT / "raster" / f"aeo_dza_precip_annual_{years[0]}_{years[-1]}_v{VERSION}.tif"
    write_cog(p, masked(annual), [f"precip_{y}_mm" for y in years], GRID.transform, {**base_tags, "variable": "annual precipitation total (mm)"})
    files["annual_cog"] = p
    p = OUT / "raster" / f"aeo_dza_precip_normal_{BASELINE[0]}_{BASELINE[1]}_v{VERSION}.tif"
    write_cog(p, masked(normal)[None], [f"normal_{BASELINE[0]}_{BASELINE[1]}_mm"], GRID.transform, {**base_tags, "variable": "mean annual precipitation 1991-2020 (mm)"})
    files["normal_cog"] = p
    p = OUT / "raster" / f"aeo_dza_precip_anomaly_pct_{years[0]}_{years[-1]}_v{VERSION}.tif"
    write_cog(p, masked(anom_pct), [f"anomaly_pct_{y}" for y in years], GRID.transform, {**base_tags, "units": "percent of 1991-2020 normal", "variable": "annual precipitation anomaly (%)"})
    files["anom_cog"] = p

    wilaya_files = {}
    for k, row in adm1.iterrows():
        cells = w1.cells[k]
        rr, cc = cells // GRID.ncol, cells % GRID.ncol
        r0, r1_, c0, c1 = rr.min(), rr.max() + 1, cc.min(), cc.max() + 1
        m = np.zeros((GRID.nrow, GRID.ncol), bool)
        m.flat[cells] = True
        sub = np.where(m, annual, np.nan)[:, r0:r1_, c0:c1]
        tr = GRID.transform * rasterio.Affine.translation(c0, r0)
        p = OUT / "raster" / "wilaya" / f"aeo_precip_annual_w{row.wilaya_code}_{slug(row['name'])}_v{VERSION}.tif"
        write_cog(p, sub, [f"precip_{y}_mm" for y in years], tr, {**base_tags, "wilaya_code": row.wilaya_code, "wilaya": row["name"]})
        wilaya_files[row.wilaya_code] = p

    # ---------------------------------------------------------------- statistics
    mon_idx = {m: i for i, m in enumerate(months)}
    month_labels = [m.replace(".", "-") for m in months]
    cal_month = ym[:, 1]
    tables, web, summaries = {}, {}, {}
    for level, L in levels.items():
        w, units = L["w"], L["units"]
        ann, valid_a = w.mean(annual)
        mon, valid_m = w.mean(cube)
        n_cells, eff = w.support()
        norm = ann[:, b0:b1 + 1].mean(1)
        mon_norm = np.stack([mon[:, (cal_month == k) & (ym[:, 0] >= BASELINE[0]) & (ym[:, 0] <= BASELINE[1])].mean(1)
                             for k in range(1, 13)], 1)  # (units, 12)
        # annual long table
        rows = []
        for i, u in units.iterrows():
            for j, y in enumerate(years):
                v = ann[i, j]
                rows.append({"level": level, "unit_code": u.code, "unit_name": u["name"], "parent_code": u.parent,
                             "year": y, "precip_mm": r1(v), "normal_1991_2020_mm": r1(norm[i]),
                             "anomaly_mm": r1(v - norm[i]),
                             "anomaly_pct": r1(100 * (v - norm[i]) / norm[i]) if norm[i] >= 1 else None,
                             "valid_area_pct": r1(100 * valid_a[i, j])})
        ta = pd.DataFrame(rows)
        # monthly long table
        mrows = {"level": level, "unit_code": np.repeat(units.code.values, len(months)),
                 "unit_name": np.repeat(units["name"].values, len(months)),
                 "parent_code": np.repeat(units.parent.values, len(months)),
                 "year": np.tile(ym[:, 0], len(units)), "month": np.tile(ym[:, 1], len(units)),
                 "precip_mm": np.round(mon.ravel(), 1),
                 "normal_1991_2020_mm": np.round(mon_norm[:, cal_month - 1].ravel(), 1)}
        tm = pd.DataFrame(mrows)
        tm["anomaly_mm"] = (tm.precip_mm - tm.normal_1991_2020_mm).round(1)
        # summaries + trend
        srows, trends = [], []
        for i, u in units.iterrows():
            ts = theil_sen(ann[i], np.array(years, float))
            mk = mann_kendall(ann[i])
            support = "adequate" if eff[i] >= 4 else ("limited" if eff[i] >= 1 else "very limited")
            tr = {"period": f"{years[0]}-{years[-1]}", "n": mk["n"],
                  "slope_mm_per_decade": None if ts["slope"] is None else r1(ts["slope"] * 10),
                  "ci95_low": None if ts["lo"] is None else r1(ts["lo"] * 10),
                  "ci95_high": None if ts["hi"] is None else r1(ts["hi"] * 10),
                  "mk_tau": None if mk["tau"] is None else round(mk["tau"], 3),
                  "mk_p": None if mk["p"] is None else round(mk["p"], 4),
                  "lag1_autocorrelation": None if mk["r1"] is None else round(mk["r1"], 3),
                  "autocorrelation_corrected": mk["corrected"]}
            trends.append(tr)
            srows.append({"level": level, "unit_code": u.code, "unit_name": u["name"], "unit_name_ar": u.name_ar,
                          "parent_code": u.parent, "normal_1991_2020_mm": r1(norm[i]),
                          "weighted_area_km2": round(float(w.weights[i].sum()), 3),
                          "cells_touched": int(n_cells[i]), "effective_cells": round(float(eff[i]), 2),
                          "statistical_support": support, **{f"trend_{k}": v for k, v in tr.items()}})
        ts_df = pd.DataFrame(srows)
        tables[level] = (ta, tm, ts_df)
        summaries[level] = ts_df
        # web JSON
        web[level] = {
            "product": PRODUCT_ID, "version": VERSION, "level": level, "boundary_version": BOUNDARY_VERSION,
            "units_of_measure": "mm", "years": years, "baseline": list(BASELINE),
            "units": [{"code": u.code, "name": u["name"], "name_ar": u.name_ar, "parent": u.parent,
                       "support": srows[i]["statistical_support"], "effective_cells": srows[i]["effective_cells"]}
                      for i, u in units.iterrows()],
            "annual": [[r1(v) for v in ann[i]] for i in range(len(units))],
            "normal": [r1(v) for v in norm],
            "trend": trends,
        }
        mon_payload = lambda idx: {  # noqa: E731
            "product": PRODUCT_ID, "version": VERSION, "level": level, "months": month_labels,
            "units": [units.code.iloc[i] for i in idx],
            "monthly": [[r1(v) for v in mon[i]] for i in idx],
            "normal_monthly": [[r1(v) for v in mon_norm[i]] for i in idx],
        }
        if level == "admin2":
            for wc in sorted(units.parent.unique()):
                idx = list(units.index[units.parent == wc])
                (OUT / "web" / "monthly_admin2" / f"{wc}.json").write_text(json.dumps(mon_payload(idx), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        else:
            (OUT / "web" / f"monthly_{level}.json").write_text(json.dumps(mon_payload(list(units.index)), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (OUT / "web" / f"annual_{level}.json").write_text(json.dumps(web[level], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        ta.to_csv(OUT / "tables" / f"aeo_precip_annual_{level}_v{VERSION}.csv", index=False, encoding="utf-8")
        ta.to_parquet(OUT / "tables" / f"aeo_precip_annual_{level}_v{VERSION}.parquet", index=False)
        tm.to_parquet(OUT / "tables" / f"aeo_precip_monthly_{level}_v{VERSION}.parquet", index=False)
        if level != "admin2":
            tm.to_csv(OUT / "tables" / f"aeo_precip_monthly_{level}_v{VERSION}.csv", index=False, encoding="utf-8")
        ts_df.to_csv(OUT / "tables" / f"aeo_precip_summary_{level}_v{VERSION}.csv", index=False, encoding="utf-8")

    # reconciliation: national mean = area-weighted mean of wilaya means
    a1 = np.array(web["admin1"]["annual"], float)
    wa1 = np.array([w.sum() for w in w1.weights])
    recon = (a1 * wa1[:, None]).sum(0) / wa1.sum()
    nat = np.array(web["admin0"]["annual"][0], float)
    max_diff = float(np.nanmax(np.abs(recon - nat)))
    qc.append(f"National annual mean equals the area-weighted mean of wilaya means (max difference {max_diff:.2f} mm, rounding only)")
    assert max_diff < 0.2, max_diff

    # ---------------------------------------------------------------- map overlays (Web Mercator PNG)
    def colorize(a, breaks, colors):
        rgb = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in colors], np.uint8)
        idx = np.digitize(a, breaks)
        out = np.zeros((*a.shape, 4), np.uint8)
        ok = ~np.isnan(a)
        out[ok, :3] = rgb[idx[ok]]
        out[ok, 3] = 255
        return out

    dst_t, dw, dh = calculate_default_transform("EPSG:4326", "EPSG:3857", GRID.ncol, GRID.nrow,
                                                *array_bounds(GRID.nrow, GRID.ncol, GRID.transform), resolution=5000)
    lon_w, lat_s, lon_e, lat_n = transform_bounds("EPSG:3857", "EPSG:4326", *array_bounds(dh, dw, dst_t))

    def to_merc(a):
        out = np.full((dh, dw), np.nan, np.float32)
        reproject(np.where(inside, a, np.nan).astype("float32"), out, src_transform=GRID.transform, src_crs="EPSG:4326",
                  src_nodata=np.nan, dst_transform=dst_t, dst_crs="EPSG:3857", dst_nodata=np.nan, resampling=Resampling.nearest)
        return out

    def write_png(path, rgba):
        with rasterio.open(path, "w", driver="PNG", width=rgba.shape[1], height=rgba.shape[0], count=4, dtype="uint8") as ds:
            ds.write(np.moveaxis(rgba, 2, 0))
        aux = Path(str(path) + ".aux.xml")
        if aux.exists():
            aux.unlink()

    for j, y in enumerate(years):
        write_png(OUT / "map" / f"annual_{y}.png", colorize(to_merc(annual[j]), SEQ_BREAKS, SEQ_COLORS))
        write_png(OUT / "map" / f"anomaly_{y}.png", colorize(to_merc(anom_pct[j]), DIV_BREAKS, DIV_COLORS))
    write_png(OUT / "map" / "normal.png", colorize(to_merc(normal), SEQ_BREAKS, SEQ_COLORS))
    map_meta = {"coordinates": [[lon_w, lat_n], [lon_e, lat_n], [lon_e, lat_s], [lon_w, lat_s]],
                "years": years, "annual": {"breaks": SEQ_BREAKS, "colors": SEQ_COLORS, "units": "mm"},
                "anomaly": {"breaks": DIV_BREAKS, "colors": DIV_COLORS, "units": "% of 1991-2020 normal"},
                "resampling": "nearest neighbour from the 0.05° grid to 5 km Web Mercator pixels (display only)"}
    (OUT / "map" / "map.json").write_text(json.dumps(map_meta, indent=1))

    # ---------------------------------------------------------------- manifest + provenance
    def asset(path: Path, role: str, fmt: str, level: str | None = None, extra: dict | None = None):
        rel = path.relative_to(OUT).as_posix()
        return {"href": f"{SITE_PREFIX}/{rel}", "role": role, "format": fmt, "level": level,
                "bytes": path.stat().st_size, "sha256": sha256(path), **(extra or {})}

    assets = [
        asset(files["annual_cog"], "data", "COG", "admin0", {"title": f"Annual precipitation {years[0]}–{years[-1]}, Algeria (one band per year)"}),
        asset(files["normal_cog"], "data", "COG", "admin0", {"title": "Mean annual precipitation 1991–2020, Algeria"}),
        asset(files["anom_cog"], "data", "COG", "admin0", {"title": f"Annual anomaly (% of 1991–2020) {years[0]}–{years[-1]}, Algeria"}),
    ]
    for code, p in wilaya_files.items():
        assets.append(asset(p, "data", "COG", "admin1", {"unit_code": code, "title": f"Annual precipitation, wilaya {code}"}))
    for p in sorted((OUT / "tables").iterdir()):
        lvl = re.search(r"admin\d", p.name).group(0)
        kind = "annual" if "_annual_" in p.name else "monthly" if "_monthly_" in p.name else "summary"
        assets.append(asset(p, "statistics", p.suffix[1:].upper(), lvl, {"title": f"{kind.capitalize()} statistics, {lvl}"}))

    source_files = index["files"]
    manifest = {
        "product_id": PRODUCT_ID,
        "title": "Algeria Precipitation (CHIRPS v3.0): annual and monthly, national, wilaya and commune",
        "status": "available",
        "version": VERSION,
        "geographic_scope": "Algeria",
        "available_levels": ["admin0", "admin1", "admin2"],
        "spatial_products_levels": ["admin0", "admin1"],
        "boundary_version": BOUNDARY_VERSION,
        "source_product": "CHIRPS v3.0 final, monthly (Climate Hazards Center, UC Santa Barbara)",
        "source_version": "3.0",
        "source_doi": "10.15780/G2JQ0P",
        "source_paper_doi": "10.1038/s41597-026-07096-4",
        "source_license": "CC BY 4.0",
        "license": "CC BY 4.0",
        "temporal_coverage": {"monthly": [month_labels[0], month_labels[-1]], "annual": [years[0], years[-1]]},
        "reference_period": list(BASELINE),
        "spatial_resolution": "0.05° (about 5.5 km); statistics are area-weighted means over administrative units",
        "crs": "EPSG:4326",
        "units": "mm",
        "formats": sorted({a["format"] for a in assets}),
        "processing_code": "scripts/pipelines/precip/",
        "methodology_url": "/docs/method-precipitation/",
        "created": date.today().isoformat(),
        "download_assets": assets,
        "web_assets": {"annual": {lvl: f"{SITE_PREFIX}/web/annual_{lvl}.json" for lvl in levels},
                       "monthly": {"admin0": f"{SITE_PREFIX}/web/monthly_admin0.json", "admin1": f"{SITE_PREFIX}/web/monthly_admin1.json",
                                   "admin2": f"{SITE_PREFIX}/web/monthly_admin2/{{wilaya_code}}.json"},
                       "map": f"{SITE_PREFIX}/map/map.json"},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    prov = {
        "product_id": PRODUCT_ID, "version": VERSION, "created": date.today().isoformat(),
        "source": {"name": "CHIRPS v3.0 final monthly, global COG", "base_url": index["source"], "retrieved": index["retrieved"],
                   "window": index["window"], "files": len(source_files),
                   "last_modified_range": [min((f["last_modified"] or "") for f in source_files), max((f["last_modified"] or "") for f in source_files)]},
        "boundaries": f"/data/aeo/boundaries/{BOUNDARY_VERSION}/ (aeo-dza-admin-boundaries)",
        "qc": qc,
        "supersample": 10,
        "support_classes": "effective cells = sum of CHIRPS cell fractions inside the unit; adequate >= 4, limited 1-4, very limited < 1",
        "steps": ["fetch_chirps3.py: window read from each monthly COG (HTTP range requests); -9999 -> missing",
                  "build_precip.py: QC, annual totals (complete years), 1991-2020 normals, anomalies, zonal statistics, trends, exports"],
    }
    (OUT / "PROVENANCE.json").write_text(json.dumps(prov, indent=1, ensure_ascii=False), encoding="utf-8")
    total = sum(a["bytes"] for a in assets)
    print(json.dumps({"years": [years[0], years[-1]], "months": [month_labels[0], month_labels[-1]], "assets": len(assets),
                      "asset_MB": round(total / 1e6, 1), "qc": qc}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
