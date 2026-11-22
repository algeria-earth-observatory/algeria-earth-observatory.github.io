"""Steps 2-8 — build the AEO product "Algeria Drought Index SPEI (TerraClimate)".

Input : data-work/spei/raw/tc_{ppt,pet}_<year>.npy + grid.json (fetch_terraclimate.py)
        public/data/aeo/boundaries/<BOUNDARY_VERSION>/dza_adm{1,2}_*.geojson
Output: public/data/aeo/products/spei/v<VERSION>/ (raster/, tables/, web/, map/, manifest.json, PROVENANCE.json)

Method (docs: src/content/docs/method-spei.md)
  * TerraClimate monthly precipitation P and Penman–Monteith reference evapotranspiration
    PET (1/30°, ≈3.7 km), water balance D = P − PET.
  * Units: area-weighted mean of P and PET (cell fraction × geodesic area, nested commune
    weights), D_unit = P_unit − PET_unit; SPEI-1/3/6/12 computed on D_unit.
  * Grid: SPEI-3 and SPEI-12 per cell, for maps and rasters.
  * SPEI: log-logistic (generalised-logistic form) fitted per calendar month by unbiased
    PWMs on 1991–2020 (aeo/spei.py; matches R package SPEI 1.8.1 to 1e-13 except at the
    ±3.09 clip — tests/validation/spei_vs_r).
  * Hyper-arid flag: normal annual P (1991–2020) below 100 mm for units, 50 mm for map
    cells (masked on maps): SPEI there reflects evaporative-demand anomalies, not drought.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
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
from aeo.spei import spei  # noqa: E402
from aeo.stats import Grid, ZonalWeights, sparse_coverage  # noqa: E402

PRODUCT_ID = "aeo-dza-spei-terraclimate"
VERSION = "1.0.0"
BOUNDARY_VERSION = "2026-11-20"
REF = (1991, 2020)
SCALES = (1, 3, 6, 12)
RAW = Path(os.environ.get("AEO_SPEI_RAW", ROOT / "data-work" / "spei" / "raw"))
OUT = Path(os.environ.get("AEO_SPEI_OUT", ROOT / "public" / "data" / "aeo" / "products" / "spei" / f"v{VERSION}"))
SITE = f"/data/aeo/products/spei/v{VERSION}"
BDIR = ROOT / "public" / "data" / "aeo" / "boundaries" / BOUNDARY_VERSION
NODATA = -9999.0
MAP_FROM = 1991
WEB_ADMIN2_FROM = 1981
HYPERARID_UNIT_MM, HYPERARID_CELL_MM = 100, 50
BREAKS = [-2.0, -1.5, -1.0, 1.0, 1.5, 2.0]
COLORS = ["#b2182b", "#ef8a62", "#fddbc7", "#f7f7f7", "#d1e5f0", "#67a9cf", "#2166ac"]  # neutral = light-surface midpoint
CLASS_LABELS = ["extremely dry (≤ −2)", "severely dry (−2 to −1.5)", "moderately dry (−1.5 to −1)", "near normal (−1 to 1)",
                "moderately wet (1 to 1.5)", "very wet (1.5 to 2)", "extremely wet (≥ 2)"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def r2(v):
    return None if v is None or not np.isfinite(v) else round(float(v), 2)


def main() -> None:
    index = json.loads((RAW / "index.json").read_text())
    g = json.loads((RAW / "grid.json").read_text())
    lat, lon = np.array(g["lat"]), np.array(g["lon"])
    res = float(np.round(np.median(np.diff(lon)), 10))
    res_lat = float(np.round(-np.median(np.diff(lat)), 10))
    assert abs(res - 1 / 30) < 1e-6 and abs(res_lat - res) < 1e-6, (res, res_lat)  # TerraClimate: 1/30° (≈3.7 km)
    grid = Grid(west=float(lon[0] - res / 2), north=float(lat[0] + res / 2), res=1 / 30, ncol=len(lon), nrow=len(lat))
    years = sorted({f["year"] for f in index["files"]})
    for y in years:
        assert (RAW / f"tc_ppt_{y}.npy").exists() and (RAW / f"tc_pet_{y}.npy").exists(), y
    P = np.concatenate([np.load(RAW / f"tc_ppt_{y}.npy") for y in years]).astype("float32")
    E = np.concatenate([np.load(RAW / f"tc_pet_{y}.npy") for y in years]).astype("float32")
    T = P.shape[0]
    months = np.tile(np.arange(1, 13), len(years))
    yrs = np.repeat(years, 12)
    labels = [f"{y}-{m:02d}" for y, m in zip(yrs, months)]
    ref = (yrs >= REF[0]) & (yrs <= REF[1])
    qc = [f"Monthly P and PET {labels[0]} to {labels[-1]} ({T} months, {len(years)} complete years)"]
    assert np.nanmin(P) >= 0 and np.nanmin(E) >= 0
    qc.append(f"P within [0, {np.nanmax(P):.0f}] mm/month, PET within [0, {np.nanmax(E):.0f}] mm/month")
    same_mask = bool((np.isnan(P) == np.isnan(P[0])).all() and (np.isnan(E) == np.isnan(P[0])).all())
    qc.append("Same valid-cell mask for P and PET in every month" if same_mask else "WARNING: valid-cell mask varies")

    # ------------------------------------------------------------ units
    adm2 = gpd.read_file(BDIR / "dza_adm2_communes.geojson").sort_values("commune_code").reset_index(drop=True)
    adm1 = gpd.read_file(BDIR / "dza_adm1_wilayas.geojson").sort_values("wilaya_code").reset_index(drop=True)
    sp, tiny = sparse_coverage(list(adm2.geometry.values), grid, supersample=10)
    w2 = ZonalWeights(sp, grid)
    w1 = ZonalWeights.merge(w2, [list(adm2.index[adm2.wilaya_code == c]) for c in adm1.wilaya_code])
    w0 = ZonalWeights.merge(w2, [list(adm2.index)])
    qc.append(f"Weights: Algeria {w0.weights[0].sum():,.0f} km²; {len(tiny)} commune(s) below one sub-cell use a representative-point cell")
    inside = np.zeros(grid.nrow * grid.ncol, bool)
    inside[w0.cells[0]] = True
    inside = inside.reshape(grid.nrow, grid.ncol)
    levels = {
        "admin0": (w0, pd.DataFrame([{"code": "DZ", "name": "Algeria", "name_ar": "الجزائر", "parent": None}])),
        "admin1": (w1, pd.DataFrame({"code": adm1.wilaya_code, "name": adm1["name"], "name_ar": adm1.name_ar, "parent": "DZ"})),
        "admin2": (w2, pd.DataFrame({"code": adm2.commune_code, "name": adm2["name"], "name_ar": adm2.name_ar, "parent": adm2.wilaya_code})),
    }

    if OUT.exists():
        shutil.rmtree(OUT)
    for d in ("raster", "tables", "web/admin2", "map"):
        (OUT / d).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ unit SPEI
    summaries = {}
    for level, (w, units) in levels.items():
        Pu, _ = w.mean(P)
        Eu, _ = w.mean(E)
        Du = Pu - Eu
        S = {k: spei(Du.T, months, k, ref).T for k in SCALES}  # (units, T)
        annualP = Pu[:, ref].reshape(len(units), -1, 12).sum(2).mean(1)
        rows = {"level": level, "unit_code": np.repeat(units.code.values, T), "parent_code": np.repeat(units.parent.values, T),
                "year": np.tile(yrs, len(units)), "month": np.tile(months, len(units)),
                "p_mm": np.round(Pu.ravel(), 1), "pet_mm": np.round(Eu.ravel(), 1), "d_mm": np.round(Du.ravel(), 1)}
        for k in SCALES:
            rows[f"spei_{k}"] = np.round(S[k].ravel(), 3)
        tab = pd.DataFrame(rows)
        tab.to_parquet(OUT / "tables" / f"aeo_spei_monthly_{level}_v{VERSION}.parquet", index=False)
        if level != "admin2":
            tab.to_csv(OUT / "tables" / f"aeo_spei_monthly_{level}_v{VERSION}.csv", index=False)
        recent = yrs >= yrs[-1] - 9
        srows = []
        for i, u in units.iterrows():
            s12 = S[12][i]
            j = int(np.nanargmin(s12))
            srows.append({"level": level, "unit_code": u.code, "unit_name": u["name"], "unit_name_ar": u.name_ar, "parent_code": u.parent,
                          "normal_p_1991_2020_mm": round(float(annualP[i]), 1),
                          "hyper_arid": bool(annualP[i] < HYPERARID_UNIT_MM),
                          "latest_month": labels[-1], "latest_spei_3": r2(S[3][i][-1]), "latest_spei_12": r2(S[12][i][-1]),
                          f"pct_months_spei12_le_-1_{yrs[-1] - 9}_{yrs[-1]}": round(100 * float(np.nanmean(s12[recent] <= -1)), 1),
                          "min_spei_12": r2(s12[j]), "min_spei_12_month": labels[j],
                          "weighted_area_km2": round(float(w.weights[i].sum()), 3)})
        sm = pd.DataFrame(srows)
        sm.to_csv(OUT / "tables" / f"aeo_spei_summary_{level}_v{VERSION}.csv", index=False)
        summaries[level] = sm
        # web JSON
        start = 0 if level != "admin2" else labels.index(f"{WEB_ADMIN2_FROM}-01")
        scales = SCALES if level != "admin2" else (3, 12)
        payload = lambda idx: {  # noqa: E731
            "product": PRODUCT_ID, "version": VERSION, "level": level, "months": labels[start:], "reference": list(REF),
            "units": [{"code": units.code.iloc[i], "name": units["name"].iloc[i], "name_ar": units.name_ar.iloc[i],
                       "parent": units.parent.iloc[i], "hyper_arid": bool(annualP[i] < HYPERARID_UNIT_MM)} for i in idx],
            "spei": {str(k): [[r2(v) for v in S[k][i][start:]] for i in idx] for k in scales},
        }
        if level == "admin2":
            for wc in sorted(units.parent.unique()):
                idx = list(units.index[units.parent == wc])
                (OUT / "web" / "admin2" / f"{wc}.json").write_text(json.dumps(payload(idx), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        else:
            (OUT / "web" / f"{level}.json").write_text(json.dumps(payload(list(units.index)), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    qc.append(f"SPEI computed for {sum(len(u) for _, u in levels.values())} units at scales {SCALES}; reference {REF[0]}-{REF[1]}")
    qc.append(f"{int(summaries['admin1'].hyper_arid.sum())} wilayas and {int(summaries['admin2'].hyper_arid.sum())} communes flagged hyper-arid (normal P < {HYPERARID_UNIT_MM} mm/year)")

    # ------------------------------------------------------------ grid SPEI (chunked by rows)
    Pn = P[ref].reshape(-1, 12, grid.nrow, grid.ncol).sum(1).mean(0)
    arid_mask = Pn < HYPERARID_CELL_MM
    grids = {k: np.full((T, grid.nrow, grid.ncol), np.nan, np.float32) for k in (3, 12)}
    D = P - E
    for r0 in range(0, grid.nrow, 48):
        sl = slice(r0, min(r0 + 48, grid.nrow))
        for k in (3, 12):
            grids[k][:, sl] = spei(D[:, sl].astype("float64"), months, k, ref).astype("float32")
    for k in (3, 12):
        grids[k][:, ~inside] = np.nan
    qc.append(f"Grid SPEI-3/12 for {int(inside.sum())} cells; {int((arid_mask & inside).sum())} hyper-arid cells (normal P < {HYPERARID_CELL_MM} mm) masked on maps")

    def write_cog(path, data, desc, tags, scale=0.01):
        """int16 storage: value = stored x scale (declared in the file); -32768 = no data."""
        stored = np.where(np.isnan(data), -32768, np.round(data / scale)).astype("int16")
        prof = dict(driver="GTiff", dtype="int16", count=data.shape[0], height=data.shape[1], width=data.shape[2],
                    crs="EPSG:4326", transform=grid.transform, nodata=-32768)
        with MemoryFile() as mem:
            with mem.open(**prof) as ds:
                ds.write(stored)
                ds.scales = [scale] * data.shape[0]
                ds.offsets = [0.0] * data.shape[0]
                for i, dd in enumerate(desc, 1):
                    ds.set_band_description(i, dd)
                ds.update_tags(**tags)
            rasterio.shutil.copy(mem.name, path, driver="COG", compress="DEFLATE", predictor=2, level=9, blocksize=256, overview_resampling="nearest")

    tags = {"product": PRODUCT_ID, "version": VERSION, "source": "TerraClimate (doi:10.1038/sdata.2017.191), CC0", "units": "SPEI (standard normal)",
            "reference_period": f"{REF[0]}-{REF[1]}", "boundary_version": BOUNDARY_VERSION,
            "storage": "int16; value = stored value x scale_factor (0.01, or 1 for precipitation); -32768 = no data"}
    dec = months == 12
    files = {}
    p = OUT / "raster" / f"aeo_dza_spei12_december_{years[0]}_{years[-1]}_v{VERSION}.tif"
    write_cog(p, grids[12][dec], [f"spei12_{y}_12" for y in years], {**tags, "variable": "SPEI-12 at the end of December (calendar-year water balance)"})
    files["dec12"] = p
    last24 = slice(T - 12, T)
    for k in (3, 12):
        p = OUT / "raster" / f"aeo_dza_spei{k}_last12_{labels[T - 12]}_{labels[-1]}_v{VERSION}.tif"
        write_cog(p, grids[k][last24], [f"spei{k}_{m}" for m in labels[T - 12:]], {**tags, "variable": f"SPEI-{k}, last 12 months"})
        files[f"last{k}"] = p
    p = OUT / "raster" / f"aeo_dza_precip_normal_terraclimate_{REF[0]}_{REF[1]}_v{VERSION}.tif"
    write_cog(p, np.where(inside, Pn, np.nan)[None], ["p_normal_mm"], {**tags, "units": "mm/year", "variable": "TerraClimate mean annual precipitation 1991-2020 (hyper-arid mask basis)"}, scale=1.0)
    files["pnormal"] = p

    # ------------------------------------------------------------ map PNGs (Web Mercator)
    dst_t, dw, dh = calculate_default_transform("EPSG:4326", "EPSG:3857", grid.ncol, grid.nrow, *array_bounds(grid.nrow, grid.ncol, grid.transform), resolution=4500)
    lw, ls, le, ln = transform_bounds("EPSG:3857", "EPSG:4326", *array_bounds(dh, dw, dst_t))
    rgb = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in COLORS], np.uint8)
    arid_m = np.zeros((dh, dw), np.float32)
    reproject(np.where(inside, arid_mask.astype("float32"), np.nan), arid_m, src_transform=grid.transform, src_crs="EPSG:4326",
              src_nodata=np.nan, dst_transform=dst_t, dst_crs="EPSG:3857", dst_nodata=np.nan, resampling=Resampling.nearest)

    def png(a, path):
        m = np.full((dh, dw), np.nan, np.float32)
        reproject(a.astype("float32"), m, src_transform=grid.transform, src_crs="EPSG:4326", src_nodata=np.nan,
                  dst_transform=dst_t, dst_crs="EPSG:3857", dst_nodata=np.nan, resampling=Resampling.nearest)
        out = np.zeros((dh, dw, 4), np.uint8)
        ok = ~np.isnan(m)
        out[ok, :3] = rgb[np.digitize(m[ok], BREAKS)]
        out[ok, 3] = 235
        arid = (arid_m == 1)
        yy, xx = np.indices(arid.shape)
        out[arid] = (232, 220, 196, 235)  # light sand #e8dcc4 ...
        out[arid & (((xx + yy) % 7) < 2)] = (180, 157, 114, 235)  # ... with diagonal hatching #b49d72 (not colour alone)
        with rasterio.open(path, "w", driver="PNG", width=dw, height=dh, count=4, dtype="uint8") as ds:
            ds.write(np.moveaxis(out, 2, 0))
        aux = Path(str(path) + ".aux.xml")
        if aux.exists():
            aux.unlink()

    map_months = [l for l in labels if int(l[:4]) >= MAP_FROM]
    for l in map_months:
        t = labels.index(l)
        for k in (3, 12):
            png(grids[k][t], OUT / "map" / f"spei{k}_{l}.png")
    (OUT / "map" / "map.json").write_text(json.dumps({
        "coordinates": [[lw, ln], [le, ln], [le, ls], [lw, ls]], "months": map_months, "scales": [3, 12],
        "breaks": BREAKS, "colors": COLORS, "labels": CLASS_LABELS,
        "hyper_arid": {"color": "#b49d72", "pattern": "diagonal hatching #b49d72 on #e8dcc4", "label": f"hyper-arid (normal P < {HYPERARID_CELL_MM} mm/year): not shown"},
        "resampling": "nearest neighbour from the 1/30° grid to 4.5 km Web Mercator pixels (display only)"}, indent=1))

    # ------------------------------------------------------------ manifest
    def asset(path, role, fmt, level, title, extra=None):
        return {"href": f"{SITE}/{path.relative_to(OUT).as_posix()}", "role": role, "format": fmt, "level": level, "title": title,
                "bytes": path.stat().st_size, "sha256": sha256(path), **(extra or {})}

    assets = [asset(files["dec12"], "data", "COG", "admin0", f"SPEI-12 in December {years[0]}–{years[-1]}, Algeria (one band per year)"),
              asset(files["last3"], "data", "COG", "admin0", "SPEI-3, last 12 months, Algeria"),
              asset(files["last12"], "data", "COG", "admin0", "SPEI-12, last 12 months, Algeria"),
              asset(files["pnormal"], "data", "COG", "admin0", "TerraClimate normal annual precipitation 1991–2020 (hyper-arid mask)")]
    for p in sorted((OUT / "tables").iterdir()):
        lvl = next(x for x in ("admin0", "admin1", "admin2") if x in p.name)
        kind = "monthly" if "_monthly_" in p.name else "summary"
        assets.append(asset(p, "statistics", p.suffix[1:].upper(), lvl, f"{kind.capitalize()} SPEI statistics, {lvl}"))
    manifest = {
        "product_id": PRODUCT_ID, "title": "Algeria Drought Index SPEI (TerraClimate): SPEI-1, 3, 6, 12 for Algeria, wilayas and communes",
        "status": "available", "version": VERSION, "geographic_scope": "Algeria",
        "available_levels": ["admin0", "admin1", "admin2"], "spatial_products_levels": ["admin0"],
        "boundary_version": BOUNDARY_VERSION,
        "source_product": "TerraClimate monthly precipitation and reference evapotranspiration (University of Idaho / Climatology Lab)",
        "source_version": f"TerraClimate {years[0]}–{years[-1]} (retrieved {index['retrieved']})", "source_doi": "10.1038/sdata.2017.191",
        "source_license": "CC0 1.0", "license": "CC BY 4.0",
        "temporal_coverage": {"monthly": [labels[0], labels[-1]], "annual": [years[0], years[-1]]},
        "reference_period": list(REF), "scales": list(SCALES),
        "spatial_resolution": "1/30° (≈3.7 km); statistics are computed on area-weighted unit water balances",
        "crs": "EPSG:4326", "units": "SPEI (dimensionless, standard normal)", "formats": sorted({a["format"] for a in assets}),
        "processing_code": "scripts/pipelines/spei/", "methodology_url": "/docs/method-spei/", "created": date.today().isoformat(),
        "download_assets": assets,
        "web_assets": {"admin0": f"{SITE}/web/admin0.json", "admin1": f"{SITE}/web/admin1.json", "admin2": f"{SITE}/web/admin2/{{wilaya_code}}.json", "map": f"{SITE}/map/map.json"},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "PROVENANCE.json").write_text(json.dumps({
        "product_id": PRODUCT_ID, "version": VERSION, "created": date.today().isoformat(),
        "source": {"name": "TerraClimate", "base": index["base"], "retrieved": index["retrieved"], "files": len(index["files"]), "box": index["box"]},
        "boundaries": f"/data/aeo/boundaries/{BOUNDARY_VERSION}/", "qc": qc,
        "validation": "Python implementation (scripts/pipelines/aeo/spei.py) reproduces the R package SPEI 1.8.1 (log-Logistic, ub-pwm, ref.start/ref.end) to 1e-13 on synthetic series, except values beyond ±3.09 which AEO clips (tests/validation/spei_vs_r).",
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"months": [labels[0], labels[-1]], "assets": len(assets), "MB": round(sum(a["bytes"] for a in assets) / 1e6, 1),
                      "map_pngs": 2 * len(map_months), "qc": qc}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
