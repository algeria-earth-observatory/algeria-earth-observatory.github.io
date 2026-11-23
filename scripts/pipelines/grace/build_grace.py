"""AEO terrestrial water storage product for Algeria from downscaled GRACE/GRACE-FO (Li & Kusche 2026).

Input:  data-work/grace_li_kusche/JPL_mascon_downscaled-v2.0.nc
        Li, F. (2025). Global high-resolution (0.25°) total water storage anomaly dataset derived by
        reproducing GRACE data, v2, Zenodo, doi:10.5281/zenodo.17265162 (CC BY 4.0); method in
        Li & Kusche (2026), GRL 53, e2025GL119881, doi:10.1029/2025GL119881. Downscaled from JPL
        RL06 mascons (~3°) with an LSTM model using ERA5 inputs; variables JPL_EWH_downscaled and
        downscaling_uncertainty (cm equivalent water height), monthly 2002-04 to 2025-03 with gaps.
        Checked against the Zenodo MD5 (7d51f349bf74543d3bcd73e504502073) on download.

Method:
  * Unit means are area-weighted over the 0.25° cells (commune coverage fractions merged into
    wilayas and Algeria). Uncertainty: the unit mean of the cell uncertainties, which assumes fully
    correlated errors (an upper bound for the unit mean's uncertainty).
  * Anomalies are re-referenced by AEO to each unit's 2004–2009 mean, a stated baseline.
  * Trend: Theil–Sen slope over all available months (cm per year) with a Mann–Kendall test on
    the deseasonalised series (monthly climatology removed).
  * Stable-cropland means weight each cell by its AEO stable-cropland area (GACED30).
  * Wilayas smaller than one 3° mascon (~96,000 km² at 30° N) are flagged: their value is mostly
    spatial detail added by the downscaling model, not resolved by GRACE.
  * Communes are not published: 0.25° cells are larger than most communes.

Output: public/data/aeo/products/water-storage/v1.0.0/
Usage:  python scripts/pipelines/grace/build_grace.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/pipelines"))
from aeo.product import MercatorPNG, Units, r, sha256, write_json, write_manifest, write_table  # noqa: E402
from aeo.stats import Grid, mann_kendall, theil_sen  # noqa: E402

VERSION = "1.0.0"
SRC = ROOT / "data-work/grace_li_kusche/JPL_mascon_downscaled-v2.0.nc"
CROP = ROOT / "data-work/cropland/stable_cropland_v1.npz"
if not CROP.exists():  # automated builds: the published AEO cropland mask holds the same grids
    CROP = ROOT / "public/data/aeo/products/stable-cropland/v1.0.0/mask/aeo_stable_cropland_grids_v1.0.0.npz"
OUT = ROOT / f"public/data/aeo/products/water-storage/v{VERSION}"
SITE = f"/data/aeo/products/water-storage/v{VERSION}"
GRID = Grid(west=-9.0, north=37.5, res=0.25, ncol=86, nrow=76)
BASE = (2004, 2009)
MASCON_KM2 = 96_000
# GDO / ColorBrewer RdBu-7 (red = storage loss, blue = gain), cm
BREAKS = [-10, -5, -2, 2, 5, 10]
COLORS = ["#b2182b", "#ef8a62", "#fddbc7", "#f7f7f7", "#d1e5f0", "#67a9cf", "#2166ac"]
TREND_BREAKS = [-0.6, -0.4, -0.2, 0.2, 0.4, 0.6]


def load() -> tuple[list[str], np.ndarray, np.ndarray]:
    ds = xr.open_dataset(SRC, decode_times=False)
    t = ds["time"].values.astype(float)
    months = []
    for x in t:
        y = int(np.floor(x + 1e-6))
        m = int(np.floor((x - y) * 12 + 1e-6)) + 1
        months.append(f"{y}-{m:02d}")
    assert len(set(months)) == len(months), "duplicate months after decoding"
    lon = ds["lon"].values
    lat = ds["lat"].values
    lon180 = np.where(lon > 180, lon - 360, lon)
    ci = [int(np.where(np.isclose(lon180, GRID.west + (k + 0.5) * GRID.res))[0][0]) for k in range(GRID.ncol)]
    ri = [int(np.where(np.isclose(lat, GRID.north - (k + 0.5) * GRID.res))[0][0]) for k in range(GRID.nrow)]
    ewh = ds["JPL_EWH_downscaled"].isel(lon=ci, lat=ri).transpose("time", "lat", "lon").values.astype("float64")
    unc = ds["downscaling_uncertainty"].isel(lon=ci, lat=ri).transpose("time", "lat", "lon").values.astype("float64")
    return months, ewh, unc


def main() -> None:
    months, ewh, unc = load()
    print("months", months[0], "→", months[-1], len(months), flush=True)
    units = Units(GRID, supersample=10)
    crop = np.load(CROP)
    assert np.allclose(crop["grid_grace025_def"], [GRID.west, GRID.north, GRID.res, GRID.ncol, GRID.nrow])
    cell_ha = np.broadcast_to(GRID.cell_area_km2() * 100, (GRID.nrow, GRID.ncol))
    share = np.clip(crop["grid_grace025_stable_ha"] / cell_ha, 0, 1)
    inside = crop["grid_grace025_valid_ha"] > 0
    yrs = np.array([int(m[:4]) for m in months])
    mon = np.array([int(m[5:]) for m in months])
    tdec = yrs + (mon - 0.5) / 12
    base = (yrs >= BASE[0]) & (yrs <= BASE[1])
    levels = ["admin0", "admin1"]
    assets, web_assets, qc, summ = [], {}, [], []
    for lv in levels:
        W = units.weights(lv)
        Wc = Units.reweight(W, share)
        tws, _ = W.mean(ewh)
        sig, _ = W.mean(unc)
        twc, _ = Wc.mean(ewh)
        crop_ha = np.array([w.sum() for w in Wc.weights]) * 100
        twc[crop_ha < 10_000] = np.nan
        tws = tws - np.nanmean(tws[:, base], 1, keepdims=True)
        twc = twc - np.nanmean(twc[:, base], 1, keepdims=True)
        meta = units.meta[lv]
        area = np.array([w.sum() for w in W.weights])
        rows, trends = [], []
        for i, u in enumerate(meta):
            y = tws[i]
            ok = ~np.isnan(y)
            clim = np.array([np.nanmean(y[mon == mm]) for mm in range(1, 13)])
            des = y - clim[mon - 1]
            ts = theil_sen(y[ok], tdec[ok])
            mk = mann_kendall(des[ok])
            trends.append({"slope_cm_per_year": ts.get("slope"), "mk_p": mk.get("p")})
            for j, m in enumerate(months):
                rows.append((u["code"], u["name"], u["parent"], int(m[:4]), int(m[5:]), tws[i, j], sig[i, j], twc[i, j]))
            summ.append((lv, u["code"], u["name"], round(float(area[i])), area[i] >= MASCON_KM2, ts.get("slope"), ts.get("lo"), ts.get("hi"), mk.get("p"), round(float(crop_ha[i]))))
        df = pd.DataFrame(rows, columns=["unit_code", "unit_name", "parent_code", "year", "month", "tws_anomaly_cm", "uncertainty_cm", "tws_anomaly_cropland_cm"])
        for c in df.columns[5:]:
            df[c] = df[c].round(2)
        assets += write_table(df, OUT, "aeo_tws_monthly", lv, VERSION, "Monthly terrestrial water storage anomaly (downscaled GRACE)")
        web_units = [{**u, "area_km2": round(float(area[i])), "resolved": bool(area[i] >= MASCON_KM2), "cropland_ha": round(float(crop_ha[i])),
                      "trend_cm_per_year": None if trends[i]["slope_cm_per_year"] is None else round(trends[i]["slope_cm_per_year"], 3),
                      "trend_mk_p": None if trends[i]["mk_p"] is None else round(trends[i]["mk_p"], 4)} for i, u in enumerate(meta)]
        write_json(OUT / "web" / f"{lv}.json", {"product": "aeo-dza-water-storage-grace", "version": VERSION, "level": lv, "months": months,
                                                "baseline": f"{BASE[0]}-{BASE[1]}", "units": web_units,
                                                "series": {"tws": r(tws, 2), "unc": r(sig, 2), "tws_crop": r(twc, 2)}})
        web_assets[lv] = f"{SITE}/web/{lv}.json"
    sm = pd.DataFrame(summ, columns=["level", "unit_code", "unit_name", "area_km2", "resolved_by_grace", "trend_cm_per_year", "trend_lo", "trend_hi", "mk_p", "stable_cropland_ha"])
    for c in ("trend_cm_per_year", "trend_lo", "trend_hi"):
        sm[c] = sm[c].astype(float).round(3)
    sm["mk_p"] = sm["mk_p"].astype(float).round(4)
    assets += write_table(sm, OUT, "aeo_tws_trends", "admin0-1", VERSION, "Water storage trend per unit (Theil–Sen)")

    # maps: monthly anomaly vs the 2004–2009 cell mean, and the trend per cell
    cell = ewh - np.nanmean(ewh[base], 0, keepdims=True)
    mp = MercatorPNG(GRID, 10_000, inside)
    for j, m in enumerate(months):
        mp.write(OUT / "map" / f"tws_{m}.png", cell[j], BREAKS, COLORS)
    slope = np.full((GRID.nrow, GRID.ncol), np.nan)
    for a in range(GRID.nrow):
        for b in range(GRID.ncol):
            if inside[a, b]:
                y = cell[:, a, b]
                ok = ~np.isnan(y)
                if ok.sum() > 100:
                    slope[a, b] = np.polyfit(tdec[ok], y[ok], 1)[0]
    mp.write(OUT / "map" / "trend.png", slope, TREND_BREAKS, COLORS)
    (OUT / "map" / "map.json").write_text(json.dumps({"coordinates": mp.coordinates, "months": months,
        "tws": {"breaks": BREAKS, "colors": COLORS, "units": "cm (vs 2004–2009 mean)", "palette": "ColorBrewer RdBu-7 (as the Copernicus Global Drought Observatory)"},
        "trend": {"breaks": TREND_BREAKS, "colors": COLORS, "units": "cm per year (least squares, display only)"},
        "resampling": "nearest neighbour from the 0.25° grid to 10 km Web Mercator pixels (display only)"}, indent=1), encoding="utf-8")
    web_assets["map"] = f"{SITE}/map/map.json"
    nat = sm[sm.level == "admin0"].iloc[0]
    qc.append(f"Algeria trend {nat.trend_cm_per_year:.3f} cm/yr (95 % {nat.trend_lo:.3f} to {nat.trend_hi:.3f}), Mann–Kendall p = {nat.mk_p:.4f}")
    qc.append(f"{int((sm[sm.level == 'admin1'].resolved_by_grace).sum())} of 69 wilayas are at least one mascon in area")
    write_manifest(OUT, {
        "product_id": "aeo-dza-water-storage-grace", "title": "Algeria terrestrial water storage anomaly (downscaled GRACE/GRACE-FO, Li & Kusche 2026): national and wilaya",
        "status": "available", "version": VERSION, "geographic_scope": "Algeria", "available_levels": levels, "spatial_products_levels": [],
        "source_product": "Global 0.25° total water storage anomaly reproducing GRACE (Li 2025, Zenodo v2), from JPL RL06 mascons",
        "source_version": "v2.0", "source_doi": "10.5281/zenodo.17265162", "source_license": "CC BY 4.0", "license": "CC BY 4.0",
        "temporal_coverage": {"monthly": [months[0], months[-1]]}, "reference_period": list(BASE),
        "spatial_resolution": "Administrative units (0.25° grid; GRACE native resolution ~3°)", "crs": "not applicable (tables by administrative unit)",
        "units": "cm equivalent water height", "formats": ["CSV", "PARQUET"], "processing_code": "scripts/pipelines/grace/build_grace.py",
        "methodology_url": "/docs/method-water-storage/", "download_assets": assets, "web_assets": web_assets, "qc": qc,
    }, {"product": "aeo-dza-water-storage-grace", "version": VERSION,
        "input": {"file": SRC.name, "doi": "10.5281/zenodo.17265162", "md5": "7d51f349bf74543d3bcd73e504502073", "bytes": SRC.stat().st_size},
        "cropland_mask": {"file": CROP.name, "sha256": sha256(CROP)}, "method": __doc__, "qc": qc})
    print("\n".join(qc))


if __name__ == "__main__":
    main()
