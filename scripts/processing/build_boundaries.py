"""Build the AEO Algeria boundary layers from an OpenStreetMap snapshot.

Output (AEO-derived dataset `aeo-dza-admin-boundaries`):
  public/data/aeo/boundaries/<version>/dza_adm0.geojson        national boundary (land)
  public/data/aeo/boundaries/<version>/dza_adm1_wilayas.geojson wilayas, full detail (land-clipped)
  public/data/aeo/boundaries/<version>/dza_adm1_wilayas_display.geojson  simplified for web maps
  public/data/aeo/boundaries/<version>/PROVENANCE.json

Method
  1. Overpass API: the Algeria country relation (admin_level=2, ISO3166-1=DZ) and
     every admin_level=4 boundary relation inside it, with member way geometries.
  2. Rings are assembled per relation with shapely.polygonize (outer minus inner).
  3. Wilaya polygons are clipped to the land part of the national boundary using
     the OSM-derived geoBoundaries DZA ADM0 polygon only as a coastline mask
     (OSM admin_level=2 includes territorial sea).
  4. Display layer: topology-aware simplification with mapshaper (npx).

Run (conda env with geopandas/shapely):
  python scripts/processing/build_boundaries.py --version 2026-11-19
Licence of outputs: ODbL 1.0 (derived from OpenStreetMap © OpenStreetMap contributors).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import polygonize, unary_union

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data-work" / "boundaries"
OVERPASS = "https://overpass-api.de/api/interpreter"
GB_ADM0 = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/"
    "DZA/ADM0/geoBoundaries-DZA-ADM0.geojson"
)
QUERY = """[out:json][timeout:600];
area["ISO3166-1"="DZ"][admin_level=2]->.a;
(rel["ISO3166-1"="DZ"][admin_level=2][boundary=administrative];
 rel(area.a)[boundary=administrative][admin_level=4];);
out geom;"""


def fetch(url: str, dest: Path, data: bytes | None = None) -> Path:
    if dest.exists():
        return dest
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "AEO-boundary-build/0.1"})
    with urllib.request.urlopen(req, timeout=900) as r:
        dest.write_bytes(r.read())
    return dest


def relation_polygon(rel: dict):
    outer, inner = [], []
    for m in rel.get("members", []):
        if m.get("type") != "way" or "geometry" not in m:
            continue
        line = LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
        (inner if m.get("role") == "inner" else outer).append(line)
    outer_polys = list(polygonize(unary_union(outer)))
    inner_polys = list(polygonize(unary_union(inner))) if inner else []
    if not outer_polys:
        raise ValueError(f"relation {rel['id']} produced no polygon")
    geom = unary_union(outer_polys)
    if inner_polys:
        geom = geom.difference(unary_union(inner_polys))
    if isinstance(geom, Polygon):
        geom = MultiPolygon([geom])
    return geom


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=date.today().isoformat())
    args = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    out_dir = ROOT / "public" / "data" / "aeo" / "boundaries" / args.version
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = fetch(
        OVERPASS,
        WORK / f"overpass_{args.version}.json",
        data=urllib.parse.urlencode({"data": QUERY}).encode(),
    )
    osm = json.loads(raw.read_text(encoding="utf-8"))
    gb0 = gpd.read_file(fetch(GB_ADM0, WORK / "geoBoundaries-DZA-ADM0.geojson")).to_crs(4326)
    land = unary_union(gb0.geometry.values)

    country, wilayas = None, []
    for el in osm["elements"]:
        if el["type"] != "relation":
            continue
        t = el.get("tags", {})
        geom = relation_polygon(el)
        if t.get("admin_level") == "2":
            country = (el, geom)
            continue
        code = t.get("ref")
        wilayas.append(
            {
                "wilaya_code": code.zfill(2) if code else None,
                "iso_3166_2": t.get("ISO3166-2"),
                "name": re.sub(r"^Wilaya (de |d'|du )", "", t.get("name:fr") or t.get("name") or ""),
                "name_ar": t.get("name:ar"),
                "name_en": t.get("name:en"),
                "osm_relation": el["id"],
                "wikidata": t.get("wikidata"),
                "geometry": geom.intersection(land),
            }
        )
    if country is None:
        raise SystemExit("country relation missing from Overpass response")

    gdf = gpd.GeoDataFrame(wilayas, crs=4326).sort_values("wilaya_code").reset_index(drop=True)
    gdf["geometry"] = gdf.geometry.buffer(0)

    # Resolve overlaps left by incomplete OSM edits after the 2026 reform (Loi n° 26-06): where a
    # newly created wilaya (higher code) overlaps an older one, the newer polygon
    # takes precedence and is removed from the older (parent) polygon.
    fixes = []
    proj = "+proj=laea +lat_0=28 +lon_0=3"
    for i in range(len(gdf)):
        for j in range(i + 1, len(gdf)):
            a, b = gdf.geometry.iloc[i], gdf.geometry.iloc[j]
            if not a.intersects(b):
                continue
            inter = a.intersection(b)
            km2 = gpd.GeoSeries([inter], crs=4326).to_crs(proj).area.iloc[0] / 1e6
            if km2 > 1:
                gdf.loc[gdf.index[i], "geometry"] = a.difference(b).buffer(0)
                fixes.append({"parent": gdf.name.iloc[i], "parent_code": gdf.wilaya_code.iloc[i],
                              "removed_overlap_with": gdf.name.iloc[j],
                              "code": gdf.wilaya_code.iloc[j], "overlap_km2": round(km2, 1)})
    print("overlap fixes:", fixes)
    gdf["area_km2"] = (gdf.to_crs("+proj=laea +lat_0=28 +lon_0=3").area / 1e6).round(1)
    gdf["source"] = "OpenStreetMap"
    gdf["snapshot"] = args.version

    adm0 = gpd.GeoDataFrame(
        [{"name": "Algeria", "name_ar": country[0]["tags"].get("name:ar"), "iso_3166_1": "DZ",
          "osm_relation": country[0]["id"], "source": "OpenStreetMap (land mask: geoBoundaries DZA ADM0)",
          "snapshot": args.version,
          "geometry": unary_union(gdf.geometry.values).buffer(0)}],
        crs=4326,
    )
    full = out_dir / "dza_adm1_wilayas.geojson"
    gdf.to_file(full, driver="GeoJSON", COORDINATE_PRECISION=6)
    adm0.to_file(out_dir / "dza_adm0.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)

    display = out_dir / "dza_adm1_wilayas_display.geojson"
    subprocess.run(
        f'npx --yes mapshaper@0.6.102 "{full}" -simplify 4% keep-shapes '
        f'-o "{display}" format=geojson precision=0.0001',
        shell=True, check=True, cwd=ROOT,
    )
    display0 = out_dir / "dza_adm0_display.geojson"
    subprocess.run(
        f'npx --yes mapshaper@0.6.102 "{full}" -dissolve -each "name=\'Algeria\'" '
        f'-simplify 4% keep-shapes -o "{display0}" format=geojson precision=0.0001',
        shell=True, check=True, cwd=ROOT,
    )

    prov = {
        "dataset": "aeo-dza-admin-boundaries",
        "version": args.version,
        "inputs": {
            "openstreetmap": {"api": OVERPASS, "query": QUERY, "retrieved": args.version,
                               "elements": len(osm["elements"])},
            "land_mask": {"url": GB_ADM0, "boundaryID": "DZA-ADM0-9297773",
                          "license": "ODbL 1.0"},
        },
        "wilaya_count": int(len(gdf)),
        "iso_3166_2_note": "iso_3166_2 values are copied from OSM tags (ISO3166-2) and are null where OSM has no tag.",
        "missing_iso_3166_2": gdf.loc[gdf.iso_3166_2.isna(), "name"].tolist(),
        "overlap_fixes": fixes,
        "notes": [
            "area_km2 is the planimetric area of the polygon in a Lambert azimuthal equal-area projection; it is not an official statistic.",
            "Boundaries are community-mapped (OpenStreetMap) and are not a legal or cadastral delineation.",
        ],
        "crs": "EPSG:4326",
        "license": "ODbL-1.0",
        "attribution": "© OpenStreetMap contributors; processing: Algeria Earth Observatory",
        "code": "scripts/processing/build_boundaries.py",
    }
    (out_dir / "PROVENANCE.json").write_text(json.dumps(prov, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: prov[k] for k in ("wilaya_count", "missing_iso_3166_2")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
