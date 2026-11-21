"""QA tests on the PUBLISHED soil product (scripts/pipelines/soil/build_soil.py)."""
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "public" / "data" / "aeo" / "products" / "soil" / "v1.0.0"
pytestmark = pytest.mark.skipif(not (PROD / "manifest.json").exists(), reason="soil product not built")

RANGES = {"soc": (0, 600), "phh2o": (3, 11), "clay": (0, 100), "sand": (0, 100), "silt": (0, 100), "bdod": (0.2, 2.2),
          "cec": (0, 200), "nitrogen": (0, 50), "cfvo": (0, 100), "ocs": (0, 400)}


@pytest.fixture(scope="module")
def manifest():
    return json.loads((PROD / "manifest.json").read_text(encoding="utf-8"))


def table(level):
    return pd.read_parquet(PROD / "tables" / f"aeo_soil_stats_{level}_v1.0.0.parquet")


def test_assets_checksums(manifest):
    for a in manifest["download_assets"]:
        p = PROD / a["href"].split("/v1.0.0/", 1)[1]
        assert p.stat().st_size == a["bytes"], a["href"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == a["sha256"], a["href"]


@pytest.mark.parametrize("level,n", [("admin0", 1), ("admin1", 69), ("admin2", 1541)])
def test_complete(manifest, level, n):
    t = table(level)
    layers = {(l["property"], l["depth"]) for l in manifest["layers"]}
    assert len(layers) == 28
    assert t.unit_code.nunique() == n
    assert len(t) == n * len(layers)
    assert set(zip(t.property, t.depth)) == layers


@pytest.mark.parametrize("level", ["admin0", "admin1", "admin2"])
def test_physical_ranges_and_quantiles(level):
    t = table(level).dropna(subset=["mean"])
    for prop, (lo, hi) in RANGES.items():
        v = t[t.property == prop]["mean"]
        assert v.between(lo, hi).all(), (prop, v.min(), v.max())
    q = t.dropna(subset=["q05_mean", "q95_mean"])
    assert (q.q05_mean <= q.q95_mean + 1e-9).all()
    # the mean prediction lies inside the average prediction interval for (almost) every unit
    inside = ((q["mean"] >= q.q05_mean - 1e-6) & (q["mean"] <= q.q95_mean + 1e-6)).mean()
    assert inside > 0.98, inside


def test_national_consistent_with_wilayas():
    n, w = table("admin0"), table("admin1")
    for (prop, depth), g in w.groupby(["property", "depth"]):
        wt = g.pixels_1km * g.valid_pct
        recon = (g["mean"] * wt).sum() / wt.sum()
        nat = n[(n.property == prop) & (n.depth == depth)]["mean"].iloc[0]
        assert abs(recon - nat) <= 0.02 * max(1.0, abs(nat)), (prop, depth, recon, nat)


def test_stock_totals_add_up():
    n, w = table("admin0"), table("admin1")
    nat = n[n.property == "ocs"]["total_stock_Mt"].iloc[0]
    tot = w[w.property == "ocs"]["total_stock_Mt"].sum()
    assert abs(tot - nat) / nat < 0.02, (tot, nat)


def test_web_json_matches_tables():
    t = table("admin1")
    web = json.loads((PROD / "web" / "admin1.json").read_text(encoding="utf-8"))
    for i, u in enumerate(web["units"]):
        row = t[(t.unit_code == u["code"]) & (t.property == "soc") & (t.depth == "0-5cm")].iloc[0]
        assert web["mean"]["soc_0-5cm"][i] == pytest.approx(row["mean"])
