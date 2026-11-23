"""AEO seasonal precipitation outlook over stable cropland — an experimental, verified test.

Question: can the NMME multi-model seasonal forecast say whether the next 3-month rainfall over
each wilaya's stable cropland will be below, near or above normal — better than climatology?

Inputs:
  * NMME ensemble-mean 3-month precipitation, 1° grid, hindcasts 1991–2021 and the latest forecasts
    (NOAA CPC, CPT format; fetch_nmme.py).
  * Observed precipitation: CHIRPS v3.0 monthly, 0.05° (raw files in D:/CHIRPS/chirps_monthly or
    $AEO_CHIRPS_MONTHLY; read only).
  * AEO stable cropland v1 (GACED30, cropland in ≥ 20 of 25 years), as area weights on both grids.

Method, for each wilaya with at least 10,000 ha of stable cropland (and for all stable cropland in
Algeria), each start month (12) and lead (6 target seasons):
  1. x = forecast seasonal mean precipitation over the wilaya's stable cropland (1° cells weighted by
     their stable-cropland area); y = observed CHIRPS seasonal total over the same cropland.
  2. Leave-one-year-out cross-validation: for each year, fit y = a + b·x on the other years
     (b < 0 is not credible and gives the climatological forecast), predict ŷ with the residual
     standard deviation s, and derive tercile probabilities P(below) = Φ((q₁ − ŷ)/s),
     P(above) = 1 − Φ((q₂ − ŷ)/s), where q₁, q₂ are the other years' observed terciles.
  3. Scores: ranked probability skill score against equal chances (RPSS), ROC area for
     below-normal, Pearson r of x and y with a one-sided p-value.
  4. A combination is locally skilful when RPSS > 0, ROC area > 0.5 and p < 0.05. Because about 5 %
     of the thousands of combinations pass by chance, a start month × lead is usable only if at least
     20 % of the wilayas pass (field significance, 4× the chance rate) and the lead is ≤ 3 months;
     an outlook is published only for locally skilful wilayas of a usable start month × lead.
  5. Current outlook: the regression fitted on all hindcast years, applied to the latest forecast.
     Where the combination is not skilful, the published outlook is "equal chances" (33/33/33)
     with the reason; the raw model signal is still given for transparency.

Output: public/data/aeo/products/seasonal-outlook/v0.1.0/  (status: experimental)
Usage:  python scripts/pipelines/outlook/build_outlook.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, pearsonr

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/pipelines"))
from aeo.product import Units, r, sha256, write_json, write_manifest, write_table  # noqa: E402
from aeo.stats import Grid  # noqa: E402

VERSION = "0.1.0"
NMME = ROOT / "data-work/nmme"
CHIRPS = Path(os.environ.get("AEO_CHIRPS_MONTHLY", "D:/CHIRPS/chirps_monthly"))
CROP = ROOT / "data-work/cropland/stable_cropland_v1.npz"
if not CROP.exists():  # automated builds: the published AEO cropland mask holds the same grids
    CROP = ROOT / "public/data/aeo/products/stable-cropland/v1.0.0/mask/aeo_stable_cropland_grids_v1.0.0.npz"
OUT = ROOT / f"public/data/aeo/products/seasonal-outlook/v{VERSION}"
SITE = f"/data/aeo/products/seasonal-outlook/v{VERSION}"
G1 = Grid(west=-9.5, north=37.5, res=1.0, ncol=22, nrow=19)
G005 = Grid(west=-9.0, north=37.5, res=0.05, ncol=430, nrow=380)
MIN_CROP_HA = 10_000
FIELD_MIN = 0.20
MAX_LEAD = 3
MON = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
DAYS = np.array([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])


# ----------------------------------------------------------------------------- CPT reader
def norm_T(T: str) -> str:
    """CPT target periods come as 'YYYY-MM/YYYY-MM' or, within one year, 'YYYY-MM/MM'."""
    a, b = T.split("/")
    if "-" not in b:
        y = int(a[:4]) + (1 if int(b) < int(a[5:7]) else 0)
        b = f"{y}-{int(b):02d}"
    return f"{a[:7]}/{b[:7]}"


def read_cpt(path: Path) -> list[dict]:
    """Fields of a CPT file: [{'T': 'YYYY-MM/YYYY-MM', 'S': 'YYYY-MM-DD', 'data': (19, 22) on G1}]."""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("cpt:field="):
            T = norm_T(re.search(r"cpt:T=([^,]+)", ln).group(1).strip())
            S = re.search(r"cpt:S=([^,]+)", ln).group(1).strip()
            nrow = int(re.search(r"cpt:nrow=(\d+)", ln).group(1))
            miss = float(re.search(r"cpt:missing=([-\d.Ee+]+)", ln).group(1))
            lons = np.array(lines[i + 1].split(), float)
            rows = [np.array(l.split(), float) for l in lines[i + 2:i + 2 + nrow]]
            lat = np.array([x[0] for x in rows])
            vals = np.array([x[1:] for x in rows])
            vals[vals == miss] = np.nan
            lon180 = np.where(lons > 180, lons - 360, lons)
            ci = [int(np.where(np.isclose(lon180, -9.0 + k))[0][0]) for k in range(G1.ncol)]
            ri = [int(np.where(np.isclose(lat, 37.0 - k))[0][0]) for k in range(G1.nrow)]
            out.append({"T": T, "S": S, "data": vals[np.ix_(ri, ci)]})
            i += 2 + nrow
        else:
            i += 1
    return out


# ----------------------------------------------------------------------------- observations
class Agg:
    """A set of weighting units (wilayas' stable cropland + all Algerian stable cropland)."""

    def __init__(self, grid: Grid, stable_ha: np.ndarray):
        u = Units(grid, supersample=10 if grid.res >= 1 else 4)
        cell_ha = np.broadcast_to(grid.cell_area_km2() * 100, (grid.nrow, grid.ncol))
        share = np.clip(stable_ha / cell_ha, 0, 1)
        self.w1 = Units.reweight(u.w1, share)
        self.w0 = Units.reweight(u.w0, share)
        self.meta = u.meta["admin1"]
        self.crop_ha = np.array([w.sum() for w in self.w1.weights]) * 100

    def mean(self, field: np.ndarray) -> np.ndarray:
        """(n_wilayas + 1, ...) cropland-weighted means; last row = Algeria."""
        a, _ = self.w1.mean(field)
        b, _ = self.w0.mean(field)
        return np.concatenate([a, b], 0)


# ----------------------------------------------------------------------------- verification
def terciles(y):
    return np.quantile(y, [1 / 3, 2 / 3])


def probs(yhat, s, q):
    pb = norm.cdf((q[0] - yhat) / s)
    pa = 1 - norm.cdf((q[1] - yhat) / s)
    return np.array([pb, 1 - pb - pa, pa])


def rps(p, obs_cat):
    o = np.zeros(3)
    o[obs_cat] = 1
    return float(np.sum((np.cumsum(p) - np.cumsum(o)) ** 2))


def roc_area(score, event):
    pos, neg = score[event], score[~event]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    gt = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(gt / (len(pos) * len(neg)))


def verify(x: np.ndarray, y: np.ndarray) -> dict:
    n = len(y)
    pf, pc, cats, pbelow = [], [], [], []
    for t in range(n):
        m = np.arange(n) != t
        q = terciles(y[m])
        cat = int(np.digitize(y[t], q))
        b, a = np.polyfit(x[m], y[m], 1)
        if b <= 0:
            p = np.array([1 / 3, 1 / 3, 1 / 3])
        else:
            res = y[m] - (a + b * x[m])
            s = np.std(res, ddof=2) * np.sqrt(1 + 1 / (n - 1))
            p = probs(a + b * x[t], s, q)
        pf.append(rps(p, cat))
        pc.append(rps(np.array([1 / 3, 1 / 3, 1 / 3]), cat))
        cats.append(cat)
        pbelow.append(p[0])
    rr, pv = pearsonr(x, y)
    p_one = pv / 2 if rr > 0 else 1 - pv / 2
    rpss = 1 - np.mean(pf) / np.mean(pc)
    roc = roc_area(np.array(pbelow), np.array(cats) == 0)
    skilful = bool(rpss > 0 and (roc if not np.isnan(roc) else 0) > 0.5 and p_one < 0.05)
    return {"n": n, "r": float(rr), "p": float(p_one), "rpss": float(rpss), "roc_below": roc, "skilful": skilful}


def main() -> None:
    crop = np.load(CROP)
    A1 = Agg(G1, crop["grid_nmme1_stable_ha"])
    A5 = Agg(G005, crop["grid_chirps005_stable_ha"])
    names = [u["name"] for u in A1.meta] + ["Algeria (all stable cropland)"]
    codes = [u["code"] for u in A1.meta] + ["DZ"]
    crop_ha = np.concatenate([A5.crop_ha, [A5.crop_ha.sum()]])
    keep = crop_ha >= MIN_CROP_HA
    print("units with enough stable cropland:", int(keep.sum()), "of", len(codes), flush=True)

    # observed monthly cropland-mean precipitation (mm): from the CHIRPS files when available,
    # otherwise (automated builds) from the series saved by the previous build of this product
    obs_table = OUT / "tables" / f"aeo_outlook_observed_cropland_precip_admin1_v{VERSION}.csv"
    if CHIRPS.exists() and any(CHIRPS.glob("chirps-v3.0.*.monthly.nc")):
        import xarray as xr
        months, obs = [], []
        for f in sorted(CHIRPS.glob("chirps-v3.0.*.monthly.nc")):
            ds = xr.open_dataset(f)
            lat, lon = ds["latitude"].values, ds["longitude"].values
            li = np.where((lat < G005.north) & (lat > G005.north - G005.nrow * G005.res))[0]
            lo = np.where((lon > G005.west) & (lon < G005.west + G005.ncol * G005.res))[0]
            p = ds["precip"].isel(latitude=li, longitude=lo).values.astype("float32")
            if lat[li[0]] < lat[li[-1]]:
                p = p[:, ::-1, :]
            assert p.shape[1:] == (G005.nrow, G005.ncol), p.shape
            p[p < -1] = np.nan
            obs.append(A5.mean(p))
            months += [str(t)[:7] for t in ds["time"].values]
            ds.close()
        obs = np.round(np.concatenate(obs, 1), 4)  # the precision saved for automated rebuilds
        obs_source = "CHIRPS v3.0 monthly files"
    else:
        t = pd.read_csv(obs_table, dtype={"unit_code": str})
        months = list(t.columns[2:])
        t = t.set_index("unit_code").loc[codes]
        obs = t[months].to_numpy(float)
        obs_source = f"saved series {obs_table.name}"
    print("observations:", obs_source, flush=True)
    midx = {m: i for i, m in enumerate(months)}
    print("CHIRPS months", months[0], "→", months[-1], flush=True)

    def season_obs(T: str) -> np.ndarray | None:
        a, b = T.split("/")
        ms = pd.period_range(a, b, freq="M").strftime("%Y-%m")
        if any(m not in midx for m in ms):
            return None
        return obs[:, [midx[m] for m in ms]].sum(1)

    ver_rows, series = [], {}
    hfiles = sorted((NMME / "hcst").glob("nmme_precip_hcst_*.txt"))
    for f in hfiles:
        mm = re.match(r"nmme_precip_hcst_([A-Za-z]{3})ic_(\d+)-(\d+)_", f.name)
        init, m1, m3 = MON[mm.group(1)], int(mm.group(2)), int(mm.group(3))
        lead = (m1 - init) % 12
        fields = read_cpt(f)
        xs, ys, yrs = [], [], []
        for fl in fields:
            yo = season_obs(fl["T"])
            if yo is None:
                continue
            xs.append(A1.mean(fl["data"]))
            ys.append(yo)
            yrs.append(fl["T"])
        X, Y = np.array(xs).T, np.array(ys).T  # (units, years)
        season = f"{m1:02d}-{m3:02d}"
        for k in np.flatnonzero(keep):
            v = verify(X[k], Y[k])
            ver_rows.append({"unit_code": codes[k], "unit_name": names[k], "init_month": init, "lead_months": lead,
                             "target_months": season, **v})
            series[(codes[k], init, lead)] = {"x": X[k], "y": Y[k], "T": yrs}
    ver = pd.DataFrame(ver_rows)
    # Field significance: with thousands of tests, about 5 % pass by chance. A start month × lead is
    # usable only if at least FIELD_MIN of the wilayas pass (4× the chance rate) and lead ≤ MAX_LEAD;
    # a unit's outlook is then published only if the unit itself passes.
    ver = ver.rename(columns={"skilful": "skilful_local"})
    share = ver[ver.unit_code != "DZ"].groupby(["init_month", "lead_months"]).skilful_local.mean().rename("field_share").reset_index()
    ver = ver.merge(share, on=["init_month", "lead_months"], how="left")
    ver["field_ok"] = (ver.field_share >= FIELD_MIN) & (ver.lead_months <= MAX_LEAD)
    ver["skilful"] = ver.skilful_local & ver.field_ok
    print("verification rows", len(ver), "locally skilful", int(ver.skilful_local.sum()), "published-skilful", int(ver.skilful.sum()), flush=True)

    # latest forecast issue
    fc = []
    for f in sorted((NMME / "fcst").glob("nmme_precip_fcst_*.txt")):
        for fl in read_cpt(f):
            fc.append((fl["S"], f.name, fl))
    latest_s = max(s for s, _, _ in fc)
    issue = [(n, fl) for s, n, fl in fc if s == latest_s]
    print("latest issue", latest_s, [n for n, _ in issue], flush=True)
    out_rows = []
    for name, fl in issue:
        mm = re.match(r"nmme_precip_fcst_([A-Za-z]{3})ic_(\d+)-(\d+)_", name)
        init, m1, m3 = MON[mm.group(1)], int(mm.group(2)), int(mm.group(3))
        lead = (m1 - init) % 12
        x_now = A1.mean(fl["data"])
        for k in np.flatnonzero(keep):
            s_ = series.get((codes[k], init, lead))
            if s_ is None:
                continue
            x, y = s_["x"], s_["y"]
            b, a = np.polyfit(x, y, 1)
            q = terciles(y)
            res = y - (a + b * x)
            s = np.std(res, ddof=2) * np.sqrt(1 + 1 / len(y))
            raw = probs(a + b * x_now[k], s, q) if b > 0 else np.array([1 / 3, 1 / 3, 1 / 3])
            v = ver[(ver.unit_code == codes[k]) & (ver.init_month == init) & (ver.lead_months == lead)].iloc[0]
            pub = raw if v.skilful else np.array([1 / 3, 1 / 3, 1 / 3])
            clim_mean = float(np.mean(y))
            out_rows.append({"unit_code": codes[k], "unit_name": names[k], "issued": latest_s, "target": fl["T"],
                             "lead_months": lead, "skilful": bool(v.skilful), "rpss": round(float(v.rpss), 3),
                             "roc_below": round(float(v.roc_below), 3), "r": round(float(v.r), 3),
                             "locally_skilful": bool(v.skilful_local), "field_share": round(float(v.field_share), 3),
                             "p_below": round(float(pub[0]), 3), "p_normal": round(float(pub[1]), 3), "p_above": round(float(pub[2]), 3),
                             "model_p_below": round(float(raw[0]), 3), "model_p_above": round(float(raw[2]), 3),
                             "calibrated_mm": round(float(a + b * x_now[k]), 1), "hindcast_mean_obs_mm": round(clim_mean, 1),
                             "stable_cropland_ha": round(float(crop_ha[k]))})
    outlook = pd.DataFrame(out_rows)

    OUT.mkdir(parents=True, exist_ok=True)
    assets = []
    vv = ver.copy()
    for c in ("r", "p", "rpss", "roc_below", "field_share"):
        vv[c] = vv[c].round(3)
    assets += write_table(vv, OUT, "aeo_outlook_verification", "admin1", VERSION, "Hindcast verification 1991–2021 by wilaya, start month and lead")
    assets += write_table(outlook, OUT, "aeo_outlook_latest", "admin1", VERSION, f"Seasonal outlook issued {latest_s}")
    od = pd.DataFrame(np.round(obs, 4), columns=months)
    od.insert(0, "unit_name", names)
    od.insert(0, "unit_code", codes)
    assets += write_table(od, OUT, "aeo_outlook_observed_cropland_precip", "admin1", VERSION, "Observed monthly precipitation over stable cropland (CHIRPS v3.0, mm)", csv=True)
    # web JSON: per unit, verification matrix (12 x 6) and the latest outlook; hindcast series for charts
    web_units = []
    for k in np.flatnonzero(keep):
        sub = ver[ver.unit_code == codes[k]]
        mat = {f"{int(t.init_month)}-{int(t.lead_months)}": [round(t.rpss, 3), round(t.roc_below, 3) if not np.isnan(t.roc_below) else None, round(t.r, 3), bool(t.skilful), bool(t.skilful_local)] for t in sub.itertuples()}
        web_units.append({"code": codes[k], "name": names[k], "cropland_ha": round(float(crop_ha[k])), "verification": mat})
    hc = {}
    for (c, init, lead), s_ in series.items():
        if init == int(latest_s[5:7]):
            hc[f"{c}|{lead}"] = {"T": s_["T"], "forecast_mm_day": r(s_["x"], 3), "observed_mm": r(s_["y"], 1)}
    write_json(OUT / "web/outlook.json", {"product": "aeo-dza-seasonal-outlook-nmme", "version": VERSION, "status": "experimental",
                                          "issued": latest_s, "units": web_units,
                                          "outlook": outlook.to_dict(orient="records"), "hindcasts": hc,
                                          "skill_rule": "locally: RPSS > 0, ROC area (below normal) > 0.5 and one-sided p(r) < 0.05, leave-one-year-out 1991–2021; published only if, for that start month and lead (≤ 3 months), at least 20 % of wilayas pass",
                                          "field_share": {f"{int(t.init_month)}-{int(t.lead_months)}": round(float(t.field_share), 3) for t in share.itertuples()},
                                          "min_cropland_ha": MIN_CROP_HA, "excluded": [{"code": codes[k], "name": names[k], "cropland_ha": round(float(crop_ha[k]))} for k in np.flatnonzero(~keep)]})
    # choropleth for the Explore map: v = P(above) − P(below) of the published (gated) outlook;
    # flag = not skilful, or too little stable cropland (shown grey)
    targets = sorted(outlook.target.unique(), key=lambda t: int(outlook[outlook.target == t].lead_months.iloc[0]))
    month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def lab(t: str) -> str:
        a, b = t.split("/")
        return f"{month_abbr[int(a[5:7]) - 1]} {a[:4]} – {month_abbr[int(b[5:7]) - 1]} {b[:4]}"

    vals, flags = {}, {}
    for t in targets:
        sub = outlook[outlook.target == t].set_index("unit_code")
        vals[t] = [[None if (u["code"] not in sub.index or not sub.loc[u["code"], "skilful"]) else round(float(sub.loc[u["code"], "p_above"] - sub.loc[u["code"], "p_below"]), 3)] for u in A1.meta]
        flags[t] = [u["code"] not in sub.index or not bool(sub.loc[u["code"], "skilful"]) for u in A1.meta]
    write_json(OUT / "web/choropleth.json", {
        "issued": latest_s, "targets": targets, "labels": {t: lab(t) for t in targets}, "months": ["static"],
        "units": [{"code": u["code"], "name": u["name"]} for u in A1.meta], "v": vals, "flags": flags,
        "breaks": [-0.25, -0.1, 0.1, 0.25], "colors": ["#a6611a", "#dfc27d", "#f5f5f5", "#80cdc1", "#018571"],
        "class_labels": ["Below normal much more likely (≥ 25 points)", "Below normal more likely (10–25 points)", "No clear tilt (within 10 points)",
                         "Above normal more likely (10–25 points)", "Above normal much more likely (≥ 25 points)"],
        "palette": "ColorBrewer BrBG-5"})
    summary = ver.groupby("lead_months").agg(skilful_share=("skilful_local", "mean"), median_rpss=("rpss", "median")).reset_index()
    qc = [f"{len(ver)} unit × start × lead combinations verified; {int(ver.skilful_local.sum())} locally skilful ({100 * ver.skilful_local.mean():.1f} %; about 5 % expected by chance); {int(ver.skilful.sum())} pass the field-significance rule",
          f"Latest issue {latest_s}: {int(outlook.skilful.sum())} of {len(outlook)} unit × target outlooks are skilful"]
    qc += [f"lead {int(t.lead_months)}: {100 * t.skilful_share:.0f} % locally skilful, median RPSS {t.median_rpss:.3f}" for t in summary.itertuples()]
    inputs = json.loads((NMME / "files.json").read_text(encoding="utf-8"))
    write_manifest(OUT, {
        "product_id": "aeo-dza-seasonal-outlook-nmme", "title": "Algeria seasonal precipitation outlook over stable cropland (NMME, verified test)",
        "status": "experimental", "version": VERSION, "geographic_scope": "Algeria (stable cropland of wilayas with ≥ 10,000 ha)",
        "available_levels": ["admin1"], "spatial_products_levels": [],
        "source_product": "NMME multi-model ensemble mean, seasonal precipitation (NOAA CPC); CHIRPS v3.0 observations",
        "source_version": "NMME (CPC CPT files)", "source_doi": None, "source_license": "NOAA data: public domain (U.S. Government work); CHIRPS CC BY 4.0",
        "license": "CC BY 4.0", "temporal_coverage": {"hindcast": ["1991", "2021"], "issued": latest_s},
        "spatial_resolution": "Wilayas (stable cropland; NMME 1° cells weighted by stable-cropland area, CHIRPS 0.05°)", "units": "tercile probabilities; mm per season", "formats": ["CSV", "PARQUET"],
        "processing_code": "scripts/pipelines/outlook/build_outlook.py", "methodology_url": "/docs/method-seasonal-outlook/",
        "cropland_mask": "AEO stable cropland v1 (GACED30, cropland in ≥ 20 of 25 years 2000–2024)",
        "download_assets": assets, "web_assets": {"admin1": f"{SITE}/web/outlook.json"}, "qc": qc,
    }, {"product": "aeo-dza-seasonal-outlook-nmme", "version": VERSION, "nmme_files": inputs,
        "chirps": {"files": sorted(p.name for p in CHIRPS.glob("chirps-v3.0.*.monthly.nc")), "months": [months[0], months[-1]]},
        "cropland_mask": {"file": CROP.name, "sha256": sha256(CROP)}, "method": __doc__, "qc": qc})
    print("\n".join(qc))


if __name__ == "__main__":
    main()
