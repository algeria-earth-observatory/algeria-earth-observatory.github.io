"""AEO climate hazard projections for Algeria from NASA NEX-GDDP-CMIP6 (8 models, SSP2-4.5 and SSP5-8.5).

Input:  data-work/cmip6/<model>/<scenario>/{tasmax,pr}_<year>.nc (fetch_nex_gddp.py; daily, 0.25°,
        bias-corrected and statistically downscaled CMIP6; Thrasher et al. 2022, doi:10.1038/s41597-022-01393-4)
        data-work/cropland/stable_cropland_v1.npz (AEO stable cropland, GACED30)

Indicators, per model, year and 0.25° cell (calendar year unless stated):
  tx_mean   mean daily maximum temperature (°C)
  hd35      days with Tmax > 35 °C
  hd40      days with Tmax > 40 °C
  spring32  days with Tmax > 32 °C in March–May (the grain-filling months of rain-fed cereals)
  prcptot   annual precipitation (mm)
  pr_ndjfma precipitation November–April (mm, season of the year in which it ends; the cereal season)
  cdd       longest run of days with precipitation < 1 mm (days)
Period means: 1985–2014 (historical), 2041–2070 and 2071–2100 (SSP2-4.5, SSP5-8.5).
Unit values: area-weighted means of the cell indicators over the wilaya or Algeria, and over their
stable cropland (cells weighted by stable-cropland area). Change = future − historical of the same
model (temperatures and days) or % change (precipitation). Ensemble statistics across the 8 models:
median, minimum and maximum, and the number of models agreeing on the sign of the change.

Output: public/data/aeo/products/climate-projections/v1.0.0/
Usage:  python scripts/pipelines/cmip6/build_cmip6.py
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
from aeo.product import MercatorPNG, Units, sha256, write_json, write_manifest, write_table  # noqa: E402
from aeo.stats import Grid  # noqa: E402

VERSION = "1.0.0"
SRC = ROOT / "data-work/cmip6"
CROP = ROOT / "data-work/cropland/stable_cropland_v1.npz"
if not CROP.exists():  # automated builds: the published AEO cropland mask holds the same grids
    CROP = ROOT / "public/data/aeo/products/stable-cropland/v1.0.0/mask/aeo_stable_cropland_grids_v1.0.0.npz"
OUT = ROOT / f"public/data/aeo/products/climate-projections/v{VERSION}"
SITE = f"/data/aeo/products/climate-projections/v{VERSION}"
GRID = Grid(west=-8.875, north=37.5, res=0.25, ncol=84, nrow=75)
MODELS = ["ACCESS-CM2", "EC-Earth3", "GFDL-ESM4", "IPSL-CM6A-LR", "MIROC6", "MPI-ESM1-2-HR", "MRI-ESM2-0", "NorESM2-LM"]
PERIODS = {("historical", "1985-2014"): range(1985, 2015),
           ("ssp245", "2041-2070"): range(2041, 2071), ("ssp245", "2071-2100"): range(2071, 2101),
           ("ssp585", "2041-2070"): range(2041, 2071), ("ssp585", "2071-2100"): range(2071, 2101)}
IND = {
    "tx_mean": ("Mean daily maximum temperature", "°C", "abs"),
    "hd35": ("Days above 35 °C", "days/year", "abs"),
    "hd40": ("Days above 40 °C", "days/year", "abs"),
    "spring32": ("Days above 32 °C in March–May", "days/year", "abs"),
    "prcptot": ("Annual precipitation", "mm/year", "pct"),
    "pr_ndjfma": ("November–April precipitation", "mm/season", "pct"),
    "cdd": ("Longest dry spell (< 1 mm/day)", "days", "abs"),
}
# display palettes (ColorBrewer): warming OrRd-7, precipitation change BrBG-7
WARM_COLORS = ["#fef0d9", "#fdd49e", "#fdbb84", "#fc8d59", "#ef6548", "#d7301f", "#990000"]
PCT_COLORS = ["#8c510a", "#d8b365", "#f6e8c3", "#f5f5f5", "#c7eae5", "#5ab4ac", "#01665e"]


def longest_run(dry: np.ndarray) -> np.ndarray:
    """Longest run of True along axis 0 (time) for each cell."""
    best = np.zeros(dry.shape[1:], np.int32)
    cur = np.zeros(dry.shape[1:], np.int32)
    for t in range(dry.shape[0]):
        cur = np.where(dry[t], cur + 1, 0)
        best = np.maximum(best, cur)
    return best


def load(model: str, scen: str, var: str, year: int) -> tuple[np.ndarray, np.ndarray]:
    ds = xr.open_dataset(SRC / model / scen / f"{var}_{year}.nc")
    a = ds[var].values.astype("float32")
    lat = ds["lat"].values
    lon = ds["lon"].values
    t = pd.DatetimeIndex(ds["time"].values) if np.issubdtype(ds["time"].dtype, np.datetime64) else pd.DatetimeIndex([pd.Timestamp(str(x)[:10]) for x in ds["time"].values])
    ds.close()
    assert a.shape[1:] == (GRID.nrow, GRID.ncol), a.shape
    assert np.isclose(lon[0] - 360, GRID.west + GRID.res / 2) and np.isclose(lat[-1], GRID.north - GRID.res / 2), (lon[0], lat[-1])
    if lat[0] < lat[-1]:
        a = a[:, ::-1, :]
    return a, t.month.values


def year_indicators(model: str, scen: str, year: int, prev_pr: tuple | None) -> tuple[dict, tuple]:
    tx, mon = load(model, scen, "tasmax", year)
    pr, monp = load(model, scen, "pr", year)
    tx = tx - 273.15
    pr = pr * 86400.0
    spring = (mon >= 3) & (mon <= 5)
    out = {
        "tx_mean": tx.mean(0),
        "hd35": (tx > 35).sum(0).astype("float32"),
        "hd40": (tx > 40).sum(0).astype("float32"),
        "spring32": (tx[spring] > 32).sum(0).astype("float32"),
        "prcptot": pr.sum(0),
        "cdd": longest_run(pr < 1.0).astype("float32"),
    }
    jfma = pr[(monp >= 1) & (monp <= 4)].sum(0)
    nd = pr[monp >= 11].sum(0)
    out["pr_ndjfma"] = (prev_pr + jfma) if prev_pr is not None else np.full_like(jfma, np.nan)
    return out, nd


def main() -> None:
    crop = np.load(CROP)
    assert np.allclose(crop["grid_cmip025_def"], [GRID.west, GRID.north, GRID.res, GRID.ncol, GRID.nrow])
    cell_ha = np.broadcast_to(GRID.cell_area_km2() * 100, (GRID.nrow, GRID.ncol))
    share = np.clip(crop["grid_cmip025_stable_ha"] / cell_ha, 0, 1)
    inside = crop["grid_cmip025_valid_ha"] > 0
    units = Units(GRID, supersample=10)
    W = {"all": {lv: units.weights(lv) for lv in ("admin0", "admin1")}}
    W["cropland"] = {lv: Units.reweight(W["all"][lv], share) for lv in ("admin0", "admin1")}
    crop_ha = {lv: np.array([w.sum() for w in W["cropland"][lv].weights]) * 100 for lv in ("admin0", "admin1")}

    # period means per model and cell: clim[model][(scen, period)][ind] -> (nrow, ncol)
    clim: dict = {}
    for m in MODELS:
        clim[m] = {}
        for (scen, per), years in PERIODS.items():
            acc = {k: [] for k in IND}
            prev = None
            # November–December of the year before the first year, for the first season
            try:
                y0 = years[0] - 1
                _, prev = year_indicators(m, scen, y0, None) if (SRC / m / scen / f"pr_{y0}.nc").exists() else (None, None)
            except Exception:  # noqa: BLE001
                prev = None
            for y in years:
                ind, prev = year_indicators(m, scen, y, prev)
                for k in IND:
                    acc[k].append(ind[k])
            clim[m][(scen, per)] = {k: np.nanmean(np.stack(v), 0) for k, v in acc.items()}
        print(m, "done", flush=True)

    fut = [k for k in PERIODS if k[0] != "historical"]
    rows, models_rows, web = [], [], {}
    for dom in ("all", "cropland"):
        for lv in ("admin0", "admin1"):
            meta = units.meta[lv]
            for ind, (label, unit, kind) in IND.items():
                hist = np.stack([W[dom][lv].mean(clim[m][("historical", "1985-2014")][ind])[0] for m in MODELS])  # (models, units)
                for scen, per in fut:
                    f = np.stack([W[dom][lv].mean(clim[m][(scen, per)][ind])[0] for m in MODELS])
                    with np.errstate(all="ignore"):
                        ch = np.where(hist > 0, 100 * (f - hist) / hist, np.nan) if kind == "pct" else f - hist
                    for i, u in enumerate(meta):
                        if dom == "cropland" and crop_ha[lv][i] < 10_000:
                            continue
                        c = ch[:, i]
                        if np.all(np.isnan(c)):
                            continue
                        med = float(np.nanmedian(c))
                        agree = int(np.sum(np.sign(c) == np.sign(med))) if med != 0 else 0
                        rows.append({"domain": dom, "level": lv, "unit_code": u["code"], "unit_name": u["name"], "indicator": ind,
                                     "indicator_label": label, "units": unit, "change_type": "percent" if kind == "pct" else "absolute",
                                     "scenario": scen, "period": per,
                                     "baseline_median": round(float(np.nanmedian(hist[:, i])), 2),
                                     "future_median": round(float(np.nanmedian(f[:, i])), 2),
                                     "change_median": round(med, 2), "change_min": round(float(np.nanmin(c)), 2), "change_max": round(float(np.nanmax(c)), 2),
                                     "models_agree_on_sign": agree, "models": len(MODELS),
                                     "stable_cropland_ha": round(float(crop_ha[lv][i]))})
                        for mi, m in enumerate(MODELS):
                            models_rows.append({"domain": dom, "level": lv, "unit_code": u["code"], "indicator": ind, "scenario": scen, "period": per,
                                                "model": m, "baseline": round(float(hist[mi, i]), 3), "future": round(float(f[mi, i]), 3), "change": round(float(c[mi]), 3)})
    df = pd.DataFrame(rows)
    dm = pd.DataFrame(models_rows)
    assets = write_table(df, OUT, "aeo_cmip6_change", "admin0-1", VERSION, "Projected change by wilaya, 8-model median and range")
    assets += write_table(dm, OUT, "aeo_cmip6_change_by_model", "admin0-1", VERSION, "Projected change by wilaya and model", csv=True)

    # web JSON: {domain: {indicator: {scen|period: {code: [median, min, max, agree, baseline]}}}}
    for dom in ("all", "cropland"):
        web[dom] = {}
        for ind in IND:
            web[dom][ind] = {}
            sub = df[(df.domain == dom) & (df.indicator == ind)]
            for (scen, per), g in sub.groupby(["scenario", "period"]):
                web[dom][ind][f"{scen}|{per}"] = {t.unit_code: [t.change_median, t.change_min, t.change_max, t.models_agree_on_sign, t.baseline_median] for t in g.itertuples()}
    write_json(OUT / "web/projections.json", {"product": "aeo-dza-climate-projections-nexgddp", "version": VERSION, "models": MODELS,
                                              "baseline": "1985-2014", "indicators": {k: {"label": v[0], "units": v[1], "change": "percent" if v[2] == "pct" else "absolute"} for k, v in IND.items()},
                                              "scenarios": {"ssp245": "SSP2-4.5 (intermediate emissions)", "ssp585": "SSP5-8.5 (very high emissions)"},
                                              "periods": ["2041-2070", "2071-2100"], "units": units.meta["admin1"], "values": web,
                                              "cropland_ha": {u["code"]: round(float(crop_ha["admin1"][i])) for i, u in enumerate(units.meta["admin1"])}})

    # maps: ensemble-median change per cell for the main indicators
    mp = MercatorPNG(GRID, 10_000, inside)
    maps = {}
    spec = {"tx_mean": ([1, 1.5, 2, 2.5, 3, 4], WARM_COLORS), "hd40": ([5, 10, 20, 30, 45, 60], WARM_COLORS),
            "spring32": ([2, 5, 10, 15, 20, 30], WARM_COLORS), "prcptot": ([-30, -20, -10, 10, 20, 30], PCT_COLORS),
            "pr_ndjfma": ([-30, -20, -10, 10, 20, 30], PCT_COLORS)}
    for ind, (br, col) in spec.items():
        kind = IND[ind][2]
        for scen, per in fut:
            chs = []
            for m in MODELS:
                h = clim[m][("historical", "1985-2014")][ind]
                f = clim[m][(scen, per)][ind]
                with np.errstate(all="ignore"):
                    chs.append(np.where(h > 1, 100 * (f - h) / h, np.nan) if kind == "pct" else f - h)
            med = np.nanmedian(np.stack(chs), 0)
            name = f"{ind}_{scen}_{per}.png"
            mp.write(OUT / "map" / name, med, br, col)
        maps[ind] = {"breaks": br, "colors": col, "units": ("% change" if kind == "pct" else IND[ind][1]), "label": IND[ind][0]}
    (OUT / "map" / "map.json").write_text(json.dumps({"coordinates": mp.coordinates, "layers": maps, "scenarios": ["ssp245", "ssp585"], "periods": ["2041-2070", "2071-2100"],
                                                      "resampling": "nearest neighbour from the 0.25° grid to 10 km Web Mercator pixels (display only)"}, indent=1), encoding="utf-8")
    nat = df[(df.domain == "all") & (df.level == "admin0")]
    qc = [f"{t.indicator} {t.scenario} {t.period}: median {t.change_median:+.2f} ({t.change_min:+.2f} to {t.change_max:+.2f}) {t.units if t.change_type == 'absolute' else '%'}, {t.models_agree_on_sign}/8 agree"
          for t in nat.itertuples()]
    files = json.loads((SRC / "files.json").read_text(encoding="utf-8")) if (SRC / "files.json").exists() else {}
    write_manifest(OUT, {
        "product_id": "aeo-dza-climate-projections-nexgddp", "title": "Algeria climate hazard projections (NASA NEX-GDDP-CMIP6, 8 models): national and wilaya, all land and stable cropland",
        "status": "available", "version": VERSION, "geographic_scope": "Algeria", "available_levels": ["admin0", "admin1"], "spatial_products_levels": [],
        "source_product": "NASA NEX-GDDP-CMIP6 (daily tasmax and pr, 0.25°)", "source_version": "NEX-GDDP-CMIP6 (newest file version per year)",
        "source_doi": "10.1038/s41597-022-01393-4", "source_license": "CC BY 4.0 for most models; see the NEX-GDDP-CMIP6 model licence table", "license": "CC BY 4.0",
        "temporal_coverage": {"periods": ["1985-2014", "2041-2070", "2071-2100"]}, "reference_period": [1985, 2014],
        "spatial_resolution": "Administrative units (0.25° grid cells)", "crs": "not applicable (tables by administrative unit)",
        "units": "see indicators", "formats": ["CSV", "PARQUET"], "processing_code": "scripts/pipelines/cmip6/build_cmip6.py",
        "methodology_url": "/docs/method-climate-projections/", "models": MODELS,
        "download_assets": assets, "web_assets": {"admin1": f"{SITE}/web/projections.json", "map": f"{SITE}/map/map.json"}, "qc": qc,
    }, {"product": "aeo-dza-climate-projections-nexgddp", "version": VERSION, "files": files,
        "cropland_mask": {"file": CROP.name, "sha256": sha256(CROP)}, "method": __doc__, "qc": qc})
    print("\n".join(qc[:20]))


if __name__ == "__main__":
    main()
