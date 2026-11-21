"""Regional partitions of published AEO tables and boundaries, for in-browser extraction.

Why: two published tables (commune-level monthly precipitation and SPEI) are single
Parquet files of 2.9 MB and 13.7 MB without a page index, so a browser would have to
download almost the whole file to extract one commune. The full-detail commune
boundaries are a 25.7 MB GeoJSON. This script splits those files by wilaya
without changing any value:

  - Parquet: rows of the published table whose parent_code is the wilaya, in the
    original order and schema (Snappy compression, as the source).
  - GeoJSON: the wilaya feature (from dza_adm1_wilayas.geojson) and the features of
    its communes (from dza_adm2_communes.geojson), copied unchanged.

Each partition set has an index.json that records the source file's SHA-256 and
size, and every partition's SHA-256, size and row/feature count. The website only
uses a partition set when the index's source SHA-256 equals the SHA-256 listed for
that file in the product manifest (or the boundary record); otherwise it falls back
to the full table. tests/python/test_partitions.py checks that the partitions
reproduce the source exactly.

Usage (from the repository root):
  python scripts/pipelines/partition_regional.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
PUB = ROOT / "public"
BOUNDARY_VERSION = "2026-11-20"

TABLES = [
    ("precipitation", "1.0.0", "aeo_precip_monthly_admin2_v1.0.0.parquet"),
    ("spei", "1.0.0", "aeo_spei_monthly_admin2_v1.0.0.parquet"),
    ("spi", "1.0.0", "aeo_spi_monthly_admin2_v1.0.0.parquet"),
]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def site(p: Path) -> str:
    return "/" + p.relative_to(PUB).as_posix()


def partition_table(product: str, version: str, name: str) -> None:
    src = PUB / "data" / "aeo" / "products" / product / f"v{version}" / "tables" / name
    out = src.parent / "by_wilaya" / src.stem
    out.mkdir(parents=True, exist_ok=True)
    t = pq.read_table(src)
    parts = []
    for code in sorted(set(t.column("parent_code").to_pylist())):
        sub = t.filter(pc.equal(t.column("parent_code"), code))
        dest = out / f"{code}.parquet"
        pq.write_table(sub, dest, compression="snappy")
        parts.append({
            "wilaya_code": code, "href": site(dest), "bytes": dest.stat().st_size, "sha256": sha256(dest),
            "rows": sub.num_rows, "unit_codes": sorted(set(sub.column("unit_code").to_pylist())),
        })
    index = {
        "kind": "regional-partitions",
        "description": "Rows of the source table split by wilaya (parent_code), unchanged and in the original order. For in-browser regional extraction; the source table remains the reference.",
        "partition_key": "parent_code",
        "source": {"href": site(src), "bytes": src.stat().st_size, "sha256": sha256(src), "rows": t.num_rows},
        "code": "scripts/pipelines/partition_regional.py",
        "partitions": parts,
    }
    (out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{name}: {len(parts)} partitions, {sum(p['bytes'] for p in parts) / 1e6:.1f} MB")


def partition_boundaries() -> None:
    bdir = PUB / "data" / "aeo" / "boundaries" / BOUNDARY_VERSION
    out = bdir / "by_wilaya"
    out.mkdir(parents=True, exist_ok=True)
    adm1_p, adm2_p = bdir / "dza_adm1_wilayas.geojson", bdir / "dza_adm2_communes.geojson"
    adm1 = json.loads(adm1_p.read_text(encoding="utf-8"))
    adm2 = json.loads(adm2_p.read_text(encoding="utf-8"))
    by_w: dict[str, list] = {}
    for f in adm2["features"]:
        by_w.setdefault(f["properties"]["wilaya_code"], []).append(f)
    parts = []
    for wf in sorted(adm1["features"], key=lambda f: f["properties"]["wilaya_code"]):
        code = wf["properties"]["wilaya_code"]
        communes = by_w.get(code, [])
        fc = {"type": "FeatureCollection", "name": f"dza_boundaries_wilaya_{code}", "features": [wf, *communes]}
        dest = out / f"{code}.geojson"
        dest.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        parts.append({
            "wilaya_code": code, "href": site(dest), "bytes": dest.stat().st_size, "sha256": sha256(dest),
            "features": 1 + len(communes), "commune_codes": sorted(f["properties"]["commune_code"] for f in communes),
        })
    index = {
        "kind": "regional-partitions",
        "description": "Per wilaya: the wilaya feature (first) followed by its communes, copied unchanged from the full-detail files. For in-browser regional extraction; the full files remain the reference.",
        "boundary_version": BOUNDARY_VERSION,
        "sources": {
            "admin1": {"href": site(adm1_p), "bytes": adm1_p.stat().st_size, "sha256": sha256(adm1_p)},
            "admin2": {"href": site(adm2_p), "bytes": adm2_p.stat().st_size, "sha256": sha256(adm2_p)},
        },
        "code": "scripts/pipelines/partition_regional.py",
        "partitions": parts,
    }
    (out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"boundaries: {len(parts)} partitions, {sum(p['bytes'] for p in parts) / 1e6:.1f} MB")


if __name__ == "__main__":
    for t in TABLES:
        partition_table(*t)
    partition_boundaries()
