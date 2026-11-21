"""Regional partitions (scripts/pipelines/partition_regional.py) must reproduce their sources exactly."""
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[2]
PUB = ROOT / "public"
PRODUCTS = PUB / "data" / "aeo" / "products"
BDIR = PUB / "data" / "aeo" / "boundaries" / "2026-11-20"
TABLES = [
    ("precipitation", "aeo_precip_monthly_admin2_v1.0.0"),
    ("spei", "aeo_spei_monthly_admin2_v1.0.0"),
    ("spi", "aeo_spi_monthly_admin2_v1.0.0"),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def local(href: str) -> Path:
    return PUB / href.lstrip("/")


@pytest.mark.parametrize("product,stem", TABLES)
def test_table_partitions_reproduce_source(product, stem):
    idx_p = PRODUCTS / product / "v1.0.0" / "tables" / "by_wilaya" / stem / "index.json"
    if not idx_p.exists():
        pytest.skip("partitions not built")
    idx = json.loads(idx_p.read_text(encoding="utf-8"))
    manifest = json.loads((PRODUCTS / product / "v1.0.0" / "manifest.json").read_text(encoding="utf-8"))
    src_asset = next(a for a in manifest["download_assets"] if a["href"] == idx["source"]["href"])
    # the index points at the exact published file
    assert idx["source"]["sha256"] == src_asset["sha256"] == sha(local(idx["source"]["href"]))
    src = pq.read_table(local(idx["source"]["href"]))
    parts = []
    for p in idx["partitions"]:
        f = local(p["href"])
        assert f.stat().st_size == p["bytes"] and sha(f) == p["sha256"], p["href"]
        t = pq.read_table(f)
        assert t.num_rows == p["rows"]
        assert set(t.column("parent_code").to_pylist()) == {p["wilaya_code"]}
        assert sorted(set(t.column("unit_code").to_pylist())) == p["unit_codes"]
        parts.append(t)
    joined = pa.concat_tables(parts)
    assert joined.schema.equals(src.schema)
    # identical rows: sort both by unit_code, year, month and compare every column
    keys = [("unit_code", "ascending"), ("year", "ascending"), ("month", "ascending")]
    a, b = joined.sort_by(keys), src.sort_by(keys)
    assert a.num_rows == b.num_rows == idx["source"]["rows"]
    for name in src.column_names:
        assert a.column(name).equals(b.column(name)), name


def test_boundary_partitions_reproduce_source():
    idx_p = BDIR / "by_wilaya" / "index.json"
    if not idx_p.exists():
        pytest.skip("partitions not built")
    idx = json.loads(idx_p.read_text(encoding="utf-8"))
    rec = json.loads((ROOT / "src" / "content" / "datasets" / "aeo-dza-admin-boundaries.json").read_text(encoding="utf-8"))
    rec_sha = {a["url"]: a.get("sha256") for a in rec["access"] if a.get("kind") == "download"}
    for lvl in ("admin1", "admin2"):
        s = idx["sources"][lvl]
        assert sha(local(s["href"])) == s["sha256"]
        if s["href"] in rec_sha:
            assert rec_sha[s["href"]] == s["sha256"], s["href"]
    adm1 = {f["properties"]["wilaya_code"]: f for f in json.loads(local(idx["sources"]["admin1"]["href"]).read_text(encoding="utf-8"))["features"]}
    adm2 = {f["properties"]["commune_code"]: f for f in json.loads(local(idx["sources"]["admin2"]["href"]).read_text(encoding="utf-8"))["features"]}
    seen = set()
    for p in idx["partitions"]:
        f = local(p["href"])
        assert sha(f) == p["sha256"] and f.stat().st_size == p["bytes"]
        fc = json.loads(f.read_text(encoding="utf-8"))
        assert fc["features"][0] == adm1[p["wilaya_code"]]
        communes = fc["features"][1:]
        assert sorted(c["properties"]["commune_code"] for c in communes) == p["commune_codes"]
        for c in communes:
            assert c == adm2[c["properties"]["commune_code"]]
            assert c["properties"]["wilaya_code"] == p["wilaya_code"]
            seen.add(c["properties"]["commune_code"])
    assert len(idx["partitions"]) == len(adm1) == 69
    assert seen == set(adm2)  # every commune appears exactly once overall
