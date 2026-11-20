"""QA tests on the PUBLISHED SPEI product (scripts/pipelines/spei/build_spei.py)."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio

ROOT = Path(__file__).resolve().parents[2]
PROD = Path(os.environ.get("AEO_SPEI_OUT", ROOT / "public" / "data" / "aeo" / "products" / "spei" / "v1.0.0"))
pytestmark = pytest.mark.skipif(not (PROD / "manifest.json").exists(), reason="SPEI product not built")


@pytest.fixture(scope="module")
def manifest():
    return json.loads((PROD / "manifest.json").read_text(encoding="utf-8"))


def monthly(level):
    return pd.read_parquet(PROD / "tables" / f"aeo_spei_monthly_{level}_v1.0.0.parquet")


def test_assets_checksums(manifest):
    assert "VERIFY" not in json.dumps(manifest)
    for a in manifest["download_assets"]:
        p = PROD / a["href"].split("/v1.0.0/", 1)[1]
        assert p.stat().st_size == a["bytes"], a["href"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == a["sha256"], a["href"]


@pytest.mark.parametrize("level,n", [("admin0", 1), ("admin1", 69), ("admin2", 1541)])
def test_tables_complete(manifest, level, n):
    t = monthly(level)
    m0, m1 = manifest["temporal_coverage"]["monthly"]
    months = (int(m1[:4]) - int(m0[:4])) * 12 + int(m1[5:]) - int(m0[5:]) + 1
    assert t.unit_code.nunique() == n
    assert len(t) == n * months
    assert (t.p_mm >= 0).all() and (t.pet_mm >= 0).all()
    assert np.allclose(t.d_mm, t.p_mm - t.pet_mm, atol=0.11)


@pytest.mark.parametrize("k", [1, 3, 6, 12])
def test_spei_standardised_over_reference(k):
    t = monthly("admin1")
    ref = t[(t.year >= 1991) & (t.year <= 2020)]
    g = ref.groupby("unit_code")[f"spei_{k}"].agg(["mean", "std"])
    assert g["mean"].abs().max() < 0.1
    assert g["std"].between(0.85, 1.1).all()
    assert t[f"spei_{k}"].abs().max() <= 3.09 + 1e-9
    # the first k-1 months have no value
    first = t[(t.year == t.year.min()) & (t.month < k)]
    assert first[f"spei_{k}"].isna().all()


def test_hyper_arid_flag_consistent():
    s = pd.read_csv(PROD / "tables" / "aeo_spei_summary_admin2_v1.0.0.csv", dtype={"unit_code": str})
    assert ((s.normal_p_1991_2020_mm < 100) == s.hyper_arid).all()


def test_rasters_scaled_int16(manifest):
    a = next(x for x in manifest["download_assets"] if "spei12_december" in x["href"])
    with rasterio.open(PROD / a["href"].split("/v1.0.0/", 1)[1]) as ds:
        assert ds.dtypes[0] == "int16" and ds.nodata == -32768
        assert ds.scales[0] == pytest.approx(0.01)
        assert ds.crs.to_epsg() == 4326 and ds.res[0] == pytest.approx(1 / 30)
        v = ds.read(1, masked=True) * ds.scales[0]
        assert v.count() > 0 and float(abs(v).max()) <= 3.09 + 1e-6
        assert ds.count == manifest["temporal_coverage"]["annual"][1] - manifest["temporal_coverage"]["annual"][0] + 1


def test_map_images_cover_months(manifest):
    meta = json.loads((PROD / "map" / "map.json").read_text())
    for m in (meta["months"][0], meta["months"][-1]):
        for k in meta["scales"]:
            assert (PROD / "map" / f"spei{k}_{m}.png").exists()
