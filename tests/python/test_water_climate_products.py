"""QA of the water, cropland and climate products: internal consistency, physical ranges and the
publication rules (no outlook without verified skill, no reservoir value presented as volume)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "public/data/aeo/products"


def need(path: Path):
    if not path.exists():
        pytest.skip(f"{path.relative_to(ROOT)} not built")
    return path


def manifest_ok(d: Path):
    import hashlib
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    for a in m["download_assets"]:
        f = ROOT / "public" / a["href"].lstrip("/")
        assert f.exists(), a["href"]
        assert f.stat().st_size == a["bytes"]
        assert hashlib.sha256(f.read_bytes()).hexdigest() == a["sha256"]
    return m


# ----------------------------------------------------------------------------- stable cropland
def test_stable_cropland_consistent():
    d = need(P / "stable-cropland/v1.0.0")
    manifest_ok(d)
    t0 = pd.read_csv(d / "tables/aeo_stable_cropland_admin0_v1.0.0.csv")
    t1 = pd.read_csv(d / "tables/aeo_stable_cropland_admin1_v1.0.0.csv", dtype={"unit_code": str})
    t2 = pd.read_csv(d / "tables/aeo_stable_cropland_admin2_v1.0.0.csv", dtype={"unit_code": str, "parent_code": str})
    assert len(t1) == 69 and len(t2) == 1541
    for t in (t0, t1, t2):
        assert (t.cropland_all_years_ha <= t.stable_cropland_ha + 1).all()
        assert (t.stable_cropland_ha <= t.cropland_majority_ha + 1).all()
        assert (t.cropland_majority_ha <= t.cropland_any_year_ha + 1).all()
        assert (t.cropland_any_year_ha <= t.land_ha + 1).all()
        assert t.stable_share_pct.between(0, 100).all()
    # wilayas are sums of communes; Algeria = wilayas (+ the reported slivers outside any commune)
    s2 = t2.groupby("parent_code").stable_cropland_ha.sum()
    assert np.allclose(t1.set_index("unit_code").stable_cropland_ha.loc[s2.index], s2, atol=50)  # communes rounded to 1 ha
    assert abs(t0.stable_cropland_ha[0] - t1.stable_cropland_ha.sum()) < 0.001 * t0.stable_cropland_ha[0]
    # the published mask grids carry the same national total
    z = np.load(d / "mask/aeo_stable_cropland_grids_v1.0.0.npz")
    for g in ("chirps005", "wapor1km", "cmip025", "grace025", "nmme1"):
        assert abs(z[f"grid_{g}_stable_ha"].sum() - t0.stable_cropland_ha[0]) < 0.005 * t0.stable_cropland_ha[0], g


# ----------------------------------------------------------------------------- ET and soil moisture
def test_et_soil_moisture_ranges_and_mask():
    d = need(P / "et-soil-moisture/v1.0.0")
    m = manifest_ok(d)
    t = pd.read_csv(d / "tables/aeo_et_sm_monthly_admin1_v1.0.0.csv", dtype={"unit_code": str})
    assert t.unit_code.nunique() == 69
    assert (t.aeti_mm.dropna() >= 0).all() and (t.ret_mm.dropna() > 0).all()
    assert t.rsm_pct.dropna().between(0, 100).all() and t.rsm_cropland_pct.dropna().between(0, 100).all()
    assert t.rsm_pct.dropna().median() > 5, "soil moisture looks like a fraction, not a percentage"
    # cropland statistics only where there is enough stable cropland
    small = t[t.stable_cropland_ha < 1000]
    assert small.aeti_cropland_mm.isna().all() and small.rsm_cropland_pct.isna().all()
    months = sorted({f"{y}-{mo:02d}" for y, mo in zip(t.year, t.month)})
    assert months[0] == m["temporal_coverage"]["monthly"][0] and months[-1] == m["temporal_coverage"]["monthly"][1]
    assert len(months) == len(pd.period_range(months[0], months[-1], freq="M"))


# ----------------------------------------------------------------------------- water storage
def test_water_storage_tables():
    d = need(P / "water-storage/v1.0.0")
    manifest_ok(d)
    w = json.loads((d / "web/admin1.json").read_text(encoding="utf-8"))
    assert len(w["units"]) == 69 and len(w["months"]) == len(set(w["months"]))
    assert w["months"] == sorted(w["months"])
    tr = pd.read_csv(d / "tables/aeo_tws_trends_admin0-1_v1.0.0.csv", dtype={"unit_code": str})
    ok = tr.dropna(subset=["trend_cm_per_year"])
    assert (ok.trend_lo <= ok.trend_cm_per_year + 1e-9).all() and (ok.trend_cm_per_year <= ok.trend_hi + 1e-9).all()
    # flagged resolution: only units of at least one mascon are "resolved"
    assert (tr[tr.resolved_by_grace].area_km2 >= 96_000).all()


# ----------------------------------------------------------------------------- seasonal outlook
def test_outlook_only_where_verified():
    d = need(P / "seasonal-outlook/v0.1.0")
    m = manifest_ok(d)
    assert m["status"] == "experimental"
    ver = pd.read_csv(d / "tables/aeo_outlook_verification_admin1_v0.1.0.csv", dtype={"unit_code": str})
    out = pd.read_csv(d / "tables/aeo_outlook_latest_admin1_v0.1.0.csv", dtype={"unit_code": str})
    # publication rule
    assert (ver.skilful <= ver.skilful_local).all()
    assert ver[ver.skilful].lead_months.max() <= 3
    assert (ver[ver.skilful].field_share >= 0.2).all()
    loc = ver[ver.skilful_local]
    # tables are rounded to 3 decimals
    assert ((loc.rpss >= 0) & (loc.roc_below >= 0.5) & (loc.p <= 0.0505)).all()
    # probabilities: sum to one; equal chances where not skilful
    s = out.p_below + out.p_normal + out.p_above
    assert np.allclose(s, 1, atol=0.002)
    ns = out[~out.skilful]
    assert np.allclose(ns[["p_below", "p_normal", "p_above"]].to_numpy(), 1 / 3, atol=0.001)
    # each published outlook matches a skilful verification row
    for o in out[out.skilful].itertuples():
        v = ver[(ver.unit_code == o.unit_code) & (ver.lead_months == o.lead_months) & (ver.init_month == int(o.issued[5:7]))]
        assert len(v) == 1 and bool(v.skilful.iloc[0])


# ----------------------------------------------------------------------------- reservoirs
def test_reservoirs_are_areas_not_volumes():
    d = need(P / "reservoirs/v1.0.0")
    manifest_ok(d)
    r = pd.read_csv(d / "tables/aeo_reservoirs_points_v1.0.0.csv")
    s = pd.read_csv(d / "tables/aeo_reservoir_area_monthly_points_v1.0.0.csv")
    assert r.gdw_id.is_unique
    assert s.pct_of_observed_max.between(0, 100.0001).all()
    assert (s.groupby("gdw_id").pct_of_observed_max.max().round(3) == 100).all()
    assert (s.valid_scenes >= 1).all()
    # no series month before the dam existed
    yr = r.set_index("gdw_id").year.dropna()
    first = s.groupby("gdw_id").month.min()
    for gid, y in yr.items():
        if gid in first.index:
            assert first[gid] >= f"{int(y) + 1}-01", gid
    # only points are published (the GDW polygons are not redistributed)
    g = json.loads((d / "web/reservoirs.geojson").read_text(encoding="utf-8"))
    assert {f["geometry"]["type"] for f in g["features"]} == {"Point"}


# ----------------------------------------------------------------------------- climate projections
def test_projections_ensemble_statistics():
    d = need(P / "climate-projections/v1.0.0")
    manifest_ok(d)
    t = pd.read_csv(d / "tables/aeo_cmip6_change_admin0-1_v1.0.0.csv", dtype={"unit_code": str})
    assert (t.change_min <= t.change_median + 1e-9).all() and (t.change_median <= t.change_max + 1e-9).all()
    assert t.models_agree_on_sign.between(0, 8).all()
    nat = t[(t.domain == "all") & (t.level == "admin0") & (t.indicator == "tx_mean")]
    assert (nat.change_min > 0).all(), "every model warms Algeria"
    # higher emissions, more warming (median), late century
    late = nat[nat.period == "2071-2100"].set_index("scenario").change_median
    assert late["ssp585"] > late["ssp245"]
