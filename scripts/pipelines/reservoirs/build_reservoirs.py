"""AEO reservoir monitor for Algeria: monthly water surface area of the main reservoirs (Landsat, 1984–present).

Inputs (all open, CC BY 4.0, no login):
  * Global Dam Watch (GDW) v1.0 — dams and reservoir polygons (Lehner et al. 2024; figshare
    doi:10.6084/m9.figshare.25988293). Downloaded to data-work/reservoirs/. The GDW authors ask that
    the database not be re-hosted in whole in its original format, so AEO publishes only dam points,
    names and capacities for Algeria together with derived series — never the GDW files.
  * Digital Earth Africa Waterbodies (continental service, Landsat 30 m, 1984–present, updated
    weekly): waterbody polygons (WFS layer DEAfrica_Waterbodies on geoserver.digitalearth.africa) and
    per-waterbody observations (wet / dry / invalid area per Landsat scene) from
    https://api.digitalearth.africa/waterbodies/waterbody/<uid>/observations/csv .

Method:
  1. Reservoirs: GDW records in Algeria with a reservoir polygon of at least 0.5 km².
  2. Matching: every DE Africa waterbody whose representative point lies inside the GDW reservoir
     polygon buffered by 500 m (DE Africa splits large reservoirs into several polygons).
  3. Per scene date: wet area and observed area summed over the matched polygons. A date is valid when
     at least 85 % of the reservoir's total polygon area was observed (DE Africa's own validity rule);
     invalid dates are dropped, never filled.
  4. Monthly value = median wet area of the valid dates of the month (number of dates kept), from the
     year after the dam's construction year (GDW YEAR_DAM) when it is known.
  5. Reference: the largest monthly wet area observed since 1984 (the "observed maximum");
     "% of observed maximum" = monthly wet area / observed maximum. This is a surface-area ratio, not a
     filling rate in volume and not an official ANBT figure.

Output: public/data/aeo/products/reservoirs/v1.0.0/
Usage:  python scripts/pipelines/reservoirs/build_reservoirs.py [--refresh]
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/pipelines"))
from aeo.product import BDIR, sha256, write_json, write_manifest, write_table  # noqa: E402

VERSION = "1.0.0"
WORK = ROOT / "data-work/reservoirs"
OUT = ROOT / f"public/data/aeo/products/reservoirs/v{VERSION}"
SITE = f"/data/aeo/products/reservoirs/v{VERSION}"
GDW_URL = "https://ndownloader.figshare.com/files/47913754"  # GDW_v1_0_shp.zip
WFS = "https://geoserver.digitalearth.africa/geoserver/wfs"
OBS = "https://api.digitalearth.africa/waterbodies/waterbody/{wb_id}/observations/csv?start_date=1984-01-01&end_date=2030-12-31"
UA = {"User-Agent": "aeo-pipeline"}
MIN_KM2 = 0.5
VALID_OBS = 0.85


def get(url: str, timeout: int = 300) -> bytes:
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception:  # noqa: BLE001
            if i == 4:
                raise
            time.sleep(5 * (i + 1))
    raise RuntimeError(url)


def gdw_algeria() -> gpd.GeoDataFrame:
    z = WORK / "GDW_v1_0_shp.zip"
    if not z.exists():
        z.write_bytes(get(GDW_URL, 900))
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
        res = [n for n in names if n.lower().endswith(".shp") and "res" in n.lower().split("/")[-1]]
        dams = [n for n in names if n.lower().endswith(".shp") and "barrier" in n.lower().split("/")[-1]]
        zf.extractall(WORK / "gdw")
    r = gpd.read_file(WORK / "gdw" / res[0])
    r = r[r["COUNTRY"].astype(str).str.contains("Algeria", case=False, na=False)].to_crs(4326)
    d = gpd.read_file(WORK / "gdw" / dams[0]) if dams else None
    if d is not None:
        d = d[d["COUNTRY"].astype(str).str.contains("Algeria", case=False, na=False)].to_crs(4326)
    return r, d


def wfs_polygons(bounds) -> gpd.GeoDataFrame:
    x0, y0, x1, y1 = bounds
    q = urllib.parse.urlencode({"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": "DEAfrica_Waterbodies",
                                "outputFormat": "application/json", "srsName": "EPSG:4326",
                                "bbox": f"{y0},{x0},{y1},{x1},urn:ogc:def:crs:EPSG::4326"})
    d = json.loads(get(f"{WFS}?{q}", 120))
    if not d["features"]:
        return gpd.GeoDataFrame(columns=["wb_id", "area_m2", "geometry"], geometry="geometry", crs=4326)
    g = gpd.GeoDataFrame([{**f["properties"], "geometry": shape(f["geometry"])} for f in d["features"]], crs=4326)
    return g


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download DE Africa observations")
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "obs").mkdir(exist_ok=True)
    res, dams = gdw_algeria()
    res = res[res["AREA_POLY"] >= MIN_KM2].copy()
    print("GDW Algerian reservoirs ≥", MIN_KM2, "km²:", len(res), flush=True)
    wil = gpd.read_file(BDIR / "dza_adm1_wilayas.geojson")[["wilaya_code", "name", "geometry"]].to_crs(4326)

    rows, series, matched = [], {}, {}
    for _, rr in res.sort_values("AREA_POLY", ascending=False).iterrows():
        gid = int(rr["GDW_ID"])
        poly = rr.geometry
        buf = gpd.GeoSeries([poly], crs=4326).to_crs(3857).buffer(500).to_crs(4326).iloc[0]
        cand = wfs_polygons(buf.bounds)
        if len(cand):
            pts = cand.geometry.representative_point()
            cand = cand[pts.within(buf)]
        uids = [str(int(u)) for u in cand["wb_id"]] if len(cand) else []
        matched[gid] = uids
        frames = []
        for uid in uids:
            f = WORK / "obs" / f"{uid}.csv"
            if a.refresh or not f.exists():
                f.write_bytes(get(OBS.format(wb_id=uid)))
            o = pd.read_csv(f, parse_dates=["date"])
            o["uid"] = uid
            frames.append(o)
        total_poly_m2 = float(cand["area_m2"].sum()) if len(cand) else 0.0
        if frames:
            o = pd.concat(frames)
            per = o.groupby("date").agg(wet=("area_wet_m2", "sum"), observed=("area_observed_m2", "sum"), n=("uid", "nunique")).reset_index()
            per = per[per.observed >= VALID_OBS * total_poly_m2]  # a polygon missing on a date counts as unobserved
            per["month"] = per.date.dt.strftime("%Y-%m")
            mon = per.groupby("month").agg(wet_km2=("wet", lambda x: float(np.median(x)) / 1e6), scenes=("wet", "size"), last=("date", "max")).reset_index()
        else:
            mon = pd.DataFrame(columns=["month", "wet_km2", "scenes", "last"])
        yr = int(rr["YEAR_DAM"]) if "YEAR_DAM" in rr and pd.notna(rr["YEAR_DAM"]) and rr["YEAR_DAM"] > 0 else None
        if yr and len(mon):
            mon = mon[mon.month >= f"{yr + 1}-01"].reset_index(drop=True)  # filling starts after construction
        mx = float(mon.wet_km2.max()) if len(mon) else np.nan
        mon["pct_of_max"] = 100 * mon.wet_km2 / mx if mx > 0 else np.nan
        series[gid] = mon
        c = poly.representative_point()
        w = wil[wil.contains(c)]
        name = next((str(rr[k]) for k in ("DAM_NAME", "RES_NAME", "ALT_NAME") if k in rr and isinstance(rr[k], str) and rr[k].strip()), f"Unnamed reservoir (GDW {gid})")
        cap = rr.get("CAP_REP") if "CAP_REP" in rr else None
        cap_mcm = rr.get("CAP_MCM") if "CAP_MCM" in rr else None
        last = mon.iloc[-1] if len(mon) else None
        rows.append({"gdw_id": gid, "name": name, "dam_name": str(rr.get("DAM_NAME") or ""), "river": str(rr.get("RIVER") or ""),
                     "year": int(rr["YEAR_DAM"]) if "YEAR_DAM" in rr and pd.notna(rr["YEAR_DAM"]) and rr["YEAR_DAM"] > 0 else None,
                     "wilaya_code": w.wilaya_code.iloc[0] if len(w) else None, "wilaya_name": w["name"].iloc[0] if len(w) else None,
                     "lon": round(c.x, 4), "lat": round(c.y, 4), "gdw_area_km2": round(float(rr["AREA_POLY"]), 2),
                     "capacity_mcm": None if cap_mcm is None or pd.isna(cap_mcm) or cap_mcm <= 0 else round(float(cap_mcm), 1),
                     "capacity_reported": bool(cap is not None and pd.notna(cap) and cap > 0),
                     "dea_polygons": len(uids), "dea_area_km2": round(total_poly_m2 / 1e6, 2),
                     "observed_max_km2": None if np.isnan(mx) else round(mx, 3),
                     "months_with_data": int(len(mon)),
                     "latest_month": None if last is None else last.month, "latest_area_km2": None if last is None else round(float(last.wet_km2), 3),
                     "latest_pct_of_max": None if last is None else round(float(last.pct_of_max), 1),
                     "latest_scene": None if last is None else str(last["last"].date())})
        print(gid, name[:28], len(uids), "polys", len(mon), "months", rows[-1]["latest_month"], rows[-1]["latest_pct_of_max"], flush=True)

    meta = pd.DataFrame(rows)
    long = []
    for gid, mon in series.items():
        for t in mon.itertuples():
            long.append({"gdw_id": gid, "month": t.month, "wet_area_km2": round(t.wet_km2, 4), "pct_of_observed_max": round(t.pct_of_max, 2), "valid_scenes": int(t.scenes)})
    longdf = pd.DataFrame(long)
    OUT.mkdir(parents=True, exist_ok=True)
    assets = write_table(meta, OUT, "aeo_reservoirs", "points", VERSION, "Algerian reservoirs: GDW attributes and latest Landsat water area")
    assets += write_table(longdf, OUT, "aeo_reservoir_area_monthly", "points", VERSION, "Monthly reservoir water area (DE Africa Waterbodies, Landsat)")

    # web: points GeoJSON + compact series
    feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [r_["lon"], r_["lat"]]}, "properties": {k: v for k, v in r_.items() if k not in ("lon", "lat")}} for r_ in rows]
    write_json(OUT / "web/reservoirs.geojson", {"type": "FeatureCollection", "features": feats})
    allm = sorted(longdf.month.unique()) if len(longdf) else []
    idx = {m: i for i, m in enumerate(allm)}
    ser = {}
    for gid, mon in series.items():
        arr = [None] * len(allm)
        for t in mon.itertuples():
            arr[idx[t.month]] = round(float(t.wet_km2), 3)
        ser[str(gid)] = arr
    write_json(OUT / "web/series.json", {"months": allm, "area_km2": ser})

    # national: total area of reservoirs with a valid value in both the month and the reference
    latest = meta.dropna(subset=["latest_pct_of_max"])
    qc = [f"{len(meta)} GDW reservoirs ≥ {MIN_KM2} km²; {int((meta.dea_polygons > 0).sum())} matched to DE Africa waterbodies",
          f"Latest months: {latest.latest_month.min()} to {latest.latest_month.max()}; median latest % of observed maximum {latest.latest_pct_of_max.median():.0f}"]
    write_manifest(OUT, {
        "product_id": "aeo-dza-reservoirs-deafrica", "title": "Algeria reservoir monitor: monthly water surface area of the main reservoirs (DE Africa Waterbodies, Landsat, 1984–present)",
        "status": "available", "version": VERSION, "geographic_scope": "Algeria (reservoirs ≥ 0.5 km² in Global Dam Watch)",
        "available_levels": ["admin0"], "spatial_products_levels": [],
        "source_product": "Digital Earth Africa Waterbodies (Landsat); Global Dam Watch v1.0", "source_version": "DE Africa Waterbodies (continental service); GDW v1.0",
        "source_doi": "10.6084/m9.figshare.25988293", "source_license": "CC BY 4.0 (both)", "license": "CC BY 4.0",
        "temporal_coverage": {"monthly": [min(allm) if allm else None, max(allm) if allm else None]},
        "spatial_resolution": "Reservoirs (Landsat 30 m water classification, DE Africa)", "units": "km² of water surface; % of the largest monthly area observed since 1984", "formats": ["CSV", "PARQUET", "GeoJSON"],
        "processing_code": "scripts/pipelines/reservoirs/build_reservoirs.py", "methodology_url": "/docs/method-reservoirs/",
        "download_assets": assets, "web_assets": {"points": f"{SITE}/web/reservoirs.geojson", "series": f"{SITE}/web/series.json"}, "qc": qc,
    }, {"product": "aeo-dza-reservoirs-deafrica", "version": VERSION,
        "gdw": {"url": GDW_URL, "sha256": sha256(WORK / "GDW_v1_0_shp.zip"), "note": "not redistributed (authors' request)"},
        "deafrica": {"wfs": WFS, "observations": OBS, "matched_uids": matched, "retrieved": pd.Timestamp.now().isoformat()[:19]},
        "method": __doc__, "qc": qc})
    print("\n".join(qc))


if __name__ == "__main__":
    main()
