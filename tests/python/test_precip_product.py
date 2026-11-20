"""Quality-assurance tests on the PUBLISHED precipitation product files.

Run after scripts/pipelines/precip/build_precip.py (and in CI on the committed files):
    python -m pytest tests/python -q
"""
import hashlib
import os
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio

ROOT = Path(__file__).resolve().parents[2]
PROD = Path(os.environ["AEO_PRECIP_OUT"]) if os.environ.get("AEO_PRECIP_OUT") else ROOT / "public" / "data" / "aeo" / "products" / "precipitation" / "v1.0.0"
BDIR = ROOT / "public" / "data" / "aeo" / "boundaries" / "2026-11-20"
pytestmark = pytest.mark.skipif(not (PROD / "manifest.json").exists(), reason="product not built")


@pytest.fixture(scope="module")
def manifest():
    return json.loads((PROD / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def years(manifest):
    a, b = manifest["temporal_coverage"]["annual"]
    return list(range(a, b + 1))


def table(level, kind, ext="parquet"):
    p = PROD / "tables" / f"aeo_precip_{kind}_{level}_v1.0.0.{ext}"
    return pd.read_parquet(p) if ext == "parquet" else pd.read_csv(p, dtype={"unit_code": str, "parent_code": str})


# ------------------------------------------------------------------ download integrity
def test_manifest_has_no_placeholders(manifest):
    assert "VERIFY" not in json.dumps(manifest)
    for k in ("source_doi", "license", "boundary_version", "temporal_coverage", "available_levels"):
        assert manifest[k]


def test_every_asset_matches_size_and_checksum(manifest):
    for a in manifest["download_assets"]:
        p = PROD / a["href"].split("/v1.0.0/", 1)[1]
        assert p.exists(), a["href"]
        assert p.stat().st_size == a["bytes"], a["href"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == a["sha256"], a["href"]


def test_one_wilaya_raster_per_wilaya(manifest):
    codes = sorted(a["unit_code"] for a in manifest["download_assets"] if a["level"] == "admin1" and a["format"] == "COG")
    assert codes == [f"{i:02d}" for i in range(1, 70)]


# ------------------------------------------------------------------ rasters
def test_national_raster_properties(manifest, years):
    a = next(x for x in manifest["download_assets"] if x["level"] == "admin0" and "_annual_" in x["href"])
    with rasterio.open(PROD / a["href"].split("/v1.0.0/", 1)[1]) as ds:
        assert ds.crs.to_epsg() == 4326
        assert ds.res == pytest.approx((0.05, 0.05))
        assert ds.nodata == -9999
        assert ds.count == len(years)
        assert ds.descriptions[0] == f"precip_{years[0]}_mm" and ds.descriptions[-1] == f"precip_{years[-1]}_mm"
        assert ds.bounds.left == pytest.approx(-9.0) and ds.bounds.top == pytest.approx(37.5)
        arr = ds.read(1, masked=True)
        assert arr.count() > 0
        assert float(arr.min()) >= 0
        assert float(arr.max()) < 3000  # mm/year; Algeria's wettest areas receive < 2000 mm
        assert ds.tags()["units"] == "mm"


def test_national_raster_covers_algeria(manifest):
    """Every 0.05° cell whose centre is inside Algeria must hold a value (CHIRPS covers all land)."""
    import geopandas as gpd
    from rasterio.features import geometry_mask
    adm0 = gpd.read_file(BDIR / "dza_adm0.geojson").geometry.iloc[0]
    a = next(x for x in manifest["download_assets"] if x["level"] == "admin0" and "_normal_" in x["href"])
    with rasterio.open(PROD / a["href"].split("/v1.0.0/", 1)[1]) as ds:
        arr = ds.read(1)
        inside = geometry_mask([adm0], out_shape=arr.shape, transform=ds.transform, invert=True)
        missing = inside & (arr == ds.nodata)
        assert inside.sum() > 75000  # ≈ 2.3 million km² / ≈ 27 km² per 0.05° cell at 28°N
        assert missing.sum() / inside.sum() < 0.002, f"{missing.sum()} cells inside Algeria without data"


# ------------------------------------------------------------------ tables
@pytest.mark.parametrize("level,n_units", [("admin0", 1), ("admin1", 69), ("admin2", 1541)])
def test_annual_tables_complete(level, n_units, years):
    t = table(level, "annual")
    assert t.unit_code.nunique() == n_units
    assert len(t) == n_units * len(years)
    assert sorted(t.year.unique()) == years
    assert t.precip_mm.notna().all()
    assert (t.precip_mm >= 0).all() and (t.precip_mm < 3000).all()
    assert (t.valid_area_pct > 50).all()


def test_admin2_codes_match_boundaries():
    t = table("admin2", "annual")
    units = pd.read_csv(BDIR / "dza_admin_units.csv", dtype=str)
    assert set(t.unit_code) == set(units.commune_code)
    assert (t.drop_duplicates("unit_code").set_index("unit_code").parent_code.sort_index()
            == units.set_index("commune_code").wilaya_code.sort_index()).all()


def test_monthly_series_continuous(manifest):
    t = table("admin0", "monthly")
    months = pd.PeriodIndex(pd.to_datetime(dict(year=t.year, month=t.month, day=1)), freq="M")
    expected = pd.period_range(manifest["temporal_coverage"]["monthly"][0], manifest["temporal_coverage"]["monthly"][1], freq="M")
    assert len(months) == len(expected) and (months.sort_values() == expected).all()


def test_anomalies_consistent(manifest):
    b0, b1 = manifest["reference_period"]
    t = table("admin1", "annual")
    assert np.allclose(t.anomaly_mm, t.precip_mm - t.normal_1991_2020_mm, atol=0.11)
    base = t[(t.year >= b0) & (t.year <= b1)].groupby("unit_code").precip_mm.mean()
    norm = t.groupby("unit_code").normal_1991_2020_mm.first()
    assert np.allclose(base.sort_index(), norm.sort_index(), atol=0.06)


def test_annual_equals_sum_of_months():
    a = table("admin1", "annual").set_index(["unit_code", "year"]).precip_mm
    m = table("admin1", "monthly")
    m = m[m.year <= a.index.get_level_values("year").max()].groupby(["unit_code", "year"]).precip_mm.sum()
    diff = (a - m.reindex(a.index)).abs()
    assert diff.max() < 0.7, diff.idxmax()  # 12 monthly values rounded to 0.1 mm


def test_national_equals_weighted_wilaya_mean():
    s1 = pd.read_csv(PROD / "tables" / "aeo_precip_summary_admin1_v1.0.0.csv", dtype={"unit_code": str})
    s2 = pd.read_csv(PROD / "tables" / "aeo_precip_summary_admin2_v1.0.0.csv", dtype={"unit_code": str, "parent_code": str})
    s0 = pd.read_csv(PROD / "tables" / "aeo_precip_summary_admin0_v1.0.0.csv")
    # nesting of weights: communes -> wilaya -> nation
    assert s2.groupby("parent_code").weighted_area_km2.sum().round(1).sort_index().tolist() == pytest.approx(
        s1.set_index("unit_code").weighted_area_km2.sort_index().round(1).tolist(), abs=0.2)
    assert s1.weighted_area_km2.sum() == pytest.approx(s0.weighted_area_km2.iloc[0], rel=1e-6)
    a1 = table("admin1", "annual").merge(s1[["unit_code", "weighted_area_km2"]], on="unit_code")
    rec = a1.groupby("year").apply(lambda g: np.average(g.precip_mm, weights=g.weighted_area_km2), include_groups=False)
    nat = table("admin0", "annual").set_index("year").precip_mm
    assert (rec - nat).abs().max() < 0.1


def test_weights_cover_algeria_area():
    s0 = pd.read_csv(PROD / "tables" / "aeo_precip_summary_admin0_v1.0.0.csv")
    # geodesic area of the boundary polygon: 2,309,832 km² (boundary PROVENANCE / docs)
    assert s0.weighted_area_km2.iloc[0] == pytest.approx(2_309_832, rel=0.005)


def test_trend_fields_present():
    s1 = pd.read_csv(PROD / "tables" / "aeo_precip_summary_admin1_v1.0.0.csv", dtype={"unit_code": str})
    assert s1.trend_n.min() >= 40
    assert s1.trend_mk_p.between(0, 1).all()
    assert (s1.trend_ci95_low <= s1.trend_slope_mm_per_decade).all() and (s1.trend_slope_mm_per_decade <= s1.trend_ci95_high).all()


def test_support_classes():
    s2 = pd.read_csv(PROD / "tables" / "aeo_precip_summary_admin2_v1.0.0.csv", dtype={"unit_code": str})
    assert set(s2.statistical_support) <= {"adequate", "limited", "very limited"}
    eff = s2.effective_cells  # rounded to 0.01 in the table; the class uses the unrounded value
    clear = (eff - 4).abs() > 0.01
    assert ((eff >= 4) == (s2.statistical_support == "adequate"))[clear].all()
