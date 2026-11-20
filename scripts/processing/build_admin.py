"""Build the AEO nested administrative boundaries of Algeria (admin 0 / 1 / 2).

Legal basis (see research/wilaya_geography.md): Loi n° 26-06 du 4 avril 2026 (JO n° 25)
— 69 wilayas and 1,541 communes. The 2019 and 2026 reforms regrouped existing
communes; no commune boundary was created by them.

Method
  1. Communes: every OpenStreetMap boundary relation with admin_level=8 inside Algeria,
     plus three commune relations that OSM tags inconsistently (listed in EXTRA_RELATIONS),
     with member-way geometries (Overpass API). Rings are assembled with
     shapely.polygonize and clipped to land with the coastline mask used by
     build_boundaries.py (geoBoundaries DZA ADM0, OSM-derived).
  2. Commune code = ONS code tagged in OSM (ref:ONS, 4 digits; first two digits = the
     wilaya of the 1984 48-wilaya scheme). One relation without ref:ONS is coded from
     MISSING_ONS after checking its Wikidata item.
  3. Each commune is assigned to the 2026 wilaya (01-69) whose AEO polygon (OSM
     snapshot BASE_WILAYAS) covers most of its area.
  4. Checks (the build stops if any fails): 1,541 communes; unique codes; the commune
     count of each of the 11 wilayas created by law 26-06 equals the law; every commune
     of a new wilaya carries the 1984 prefix of the wilaya it was taken from; each
     1984 prefix group lies within the expected 2026 wilayas.
  5. Wilayas (admin 1) are the union of their communes and Algeria (admin 0) the union
     of all communes, so the three levels nest exactly.
  6. Display versions are simplified with mapshaper (shared borders kept topologically).

Run: python scripts/processing/build_admin.py --version 2026-11-20
Licence of outputs: ODbL 1.0 (© OpenStreetMap contributors).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import polygonize, unary_union

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data-work" / "boundaries"
OVERPASS = "https://overpass-api.de/api/interpreter"
BASE_WILAYAS = ROOT / "public" / "data" / "aeo" / "boundaries" / "2026-11-19" / "dza_adm1_wilayas.geojson"
LAND_MASK = WORK / "geoBoundaries-DZA-ADM0.geojson"
EQUAL_AREA = "+proj=laea +lat_0=28 +lon_0=3 +datum=WGS84 +units=m"

# Commune relations missing from the admin_level=8 query (checked 2026-11-20):
EXTRA_RELATIONS = {
    540555: "Birtouta (ONS 1634): no boundary/admin_level tags in OSM",
    4069543: "Souk Oufella (ONS 0630): admin_level=8 but no boundary=administrative",
    6823963: "Dayet Ben Dahoua (ONS 4703): tagged admin_level=6 'Daïra Dayet Ben Dahoua', but its "
             "wikidata item Q3025708 is the commune ('commune of Algeria', located in the daïra Q3019691)",
}
EXCLUDE_RELATIONS = {
    2965467: "Greek municipality (Agioi Anargyroi-Kamatero, Q1349648) that carries ref=4703; "
             "fetched by an earlier query, not Algerian",
}
MISSING_ONS = {21037899: "4401"}  # Aïn Defla commune relation has no ref:ONS (Wikidata checked)
NAME_FIX = {6823963: ("Dayet Ben Dahoua", "ضاية بن ضحوة")}  # labels of Wikidata Q3025708

# Law 26-06 (2026): new wilaya code -> (name, number of communes, 1984 prefix of the mother wilaya)
NEW_WILAYAS_2026 = {
    "59": ("Aflou", 12, "03"), "60": ("Barika", 8, "05"), "61": ("El Kantara", 5, "07"),
    "62": ("Bir El Ater", 4, "12"), "63": ("El Aricha", 4, "13"), "64": ("Ksar Chellala", 6, "14"),
    "65": ("Aïn Ouessara", 10, "17"), "66": ("Messaad", 8, "17"), "67": ("Ksar El Boukhari", 21, "26"),
    "68": ("Bou Saâda", 23, "28"), "69": ("El Abiodh Sidi Cheikh", 7, "32"),
}
# 2019 reform (law 19-12; names by decree 21-117): wilaya 49-58 -> 1984 prefix of the mother wilaya
NEW_WILAYAS_2019 = {"49": "01", "50": "01", "51": "07", "52": "08", "53": "11", "54": "11",
                    "55": "30", "56": "33", "57": "39", "58": "47"}
LEGAL_COMMUNES = 1541

QUERY = """[out:json][timeout:900];
area["ISO3166-1"="DZ"][admin_level=2]->.a;
(rel(area.a)[boundary=administrative][admin_level=8];);
out geom;"""
QUERY_EXTRA = """[out:json][timeout:300];rel(id:{extra});out geom;"""


def fetch(dest: Path, query: str) -> Path:
    if dest.exists():
        return dest
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(OVERPASS, data=data, headers={"User-Agent": "AEO-boundary-build/0.2"})
    with urllib.request.urlopen(req, timeout=1200) as r:
        dest.write_bytes(r.read())
    return dest


def relation_polygon(rel: dict):
    outer, inner = [], []
    for m in rel.get("members", []):
        if m.get("type") != "way" or "geometry" not in m:
            continue
        line = LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
        (inner if m.get("role") == "inner" else outer).append(line)
    polys = list(polygonize(unary_union(outer)))
    if not polys:
        return None
    geom = unary_union(polys)
    if inner:
        holes = list(polygonize(unary_union(inner)))
        if holes:
            geom = geom.difference(unary_union(holes))
    return geom


def as_multi(g):
    g = g.buffer(0)
    if isinstance(g, Polygon):
        return MultiPolygon([g])
    if isinstance(g, MultiPolygon):
        return g
    return MultiPolygon([p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    args = ap.parse_args()
    out = ROOT / "public" / "data" / "aeo" / "boundaries" / args.version
    out.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    query = QUERY
    query_extra = QUERY_EXTRA.format(extra=",".join(str(i) for i in EXTRA_RELATIONS))
    osm = json.loads(fetch(WORK / f"overpass_communes_{args.version}.json", query).read_text(encoding="utf-8"))
    extra = json.loads(fetch(WORK / f"overpass_communes_extra_{args.version}.json", query_extra).read_text(encoding="utf-8"))
    osm["elements"] = osm["elements"] + extra["elements"]
    land = unary_union(gpd.read_file(LAND_MASK).to_crs(4326).geometry.values)

    rows, failed, seen = [], [], set()
    for el in osm["elements"]:
        if el["type"] != "relation" or el["id"] in seen or el["id"] in EXCLUDE_RELATIONS:
            continue
        seen.add(el["id"])
        t = el.get("tags", {})
        code = t.get("ref:ONS") or MISSING_ONS.get(el["id"])
        geom = relation_polygon(el)
        if geom is None:
            failed.append({"osm_relation": el["id"], "name": t.get("name:fr") or t.get("name")})
            continue
        name = (t.get("name:fr") or t.get("name") or "").removeprefix("Commune ").strip()
        name_ar = t.get("name:ar")
        if el["id"] in NAME_FIX:
            name, name_ar = NAME_FIX[el["id"]]
        rows.append({
            "commune_code": code, "name": name, "name_ar": name_ar,
            "name_en": t.get("name:en"), "osm_relation": el["id"], "wikidata": t.get("wikidata"),
            "geometry": as_multi(geom.intersection(land)),
        })
    if failed:
        raise SystemExit(f"relations without polygon: {failed}")
    com = gpd.GeoDataFrame(rows, crs=4326)
    empty = com[com.geometry.is_empty]
    if len(empty):
        raise SystemExit(f"communes with empty geometry after land clip: {empty[['commune_code', 'name', 'osm_relation']].to_dict('records')}")

    # ---- checks on codes
    assert com.commune_code.notna().all(), com[com.commune_code.isna()][["osm_relation", "name"]]
    dup = [c for c, n in Counter(com.commune_code).items() if n > 1]
    assert not dup, f"duplicate commune codes {dup}"
    assert len(com) == LEGAL_COMMUNES, f"{len(com)} communes, law says {LEGAL_COMMUNES}"

    # ---- overlaps between communes (OSM editing slivers): later code loses the overlap
    com = com.sort_values("commune_code").reset_index(drop=True)
    ea = com.to_crs(EQUAL_AREA)
    sidx = ea.sindex
    overlaps = []
    for i, g in enumerate(ea.geometry):
        for j in sidx.query(g, predicate="intersects"):
            if j <= i:
                continue
            a = g.intersection(ea.geometry.iloc[j]).area / 1e6
            if a > 0.01:
                overlaps.append((com.commune_code.iloc[i], com.commune_code.iloc[j], round(a, 3)))
                com.loc[j, "geometry"] = as_multi(com.geometry.iloc[j].difference(com.geometry.iloc[i]))
    big = [o for o in overlaps if o[2] > 5]
    assert not big, f"large commune overlaps (km2): {big}"

    # ---- assign 2026 wilaya by largest overlap with the AEO wilaya layer
    wil = gpd.read_file(BASE_WILAYAS).to_crs(EQUAL_AREA)
    ea = com.to_crs(EQUAL_AREA)
    inter = gpd.overlay(ea[["commune_code", "geometry"]], wil[["wilaya_code", "geometry"]], how="intersection", keep_geom_type=True)
    inter["a"] = inter.area
    best = inter.sort_values("a").groupby("commune_code").tail(1).set_index("commune_code")
    share = (best["a"] / ea.set_index("commune_code").area.reindex(best.index)).round(4)
    com["wilaya_code"] = com.commune_code.map(best["wilaya_code"])
    com["wilaya_assignment_share"] = com.commune_code.map(share)
    assert com.wilaya_code.notna().all(), com[com.wilaya_code.isna()].commune_code.tolist()
    com["wilaya_code_1984"] = com.commune_code.str[:2]

    # ---- legal checks (law 26-06 and law 19-12)
    problems = []
    counts = Counter(com.wilaya_code)
    for code, (name, n, prefix) in NEW_WILAYAS_2026.items():
        if counts.get(code) != n:
            problems.append(f"wilaya {code} {name}: {counts.get(code)} communes, law 26-06 lists {n}")
        bad = com[(com.wilaya_code == code) & (com.wilaya_code_1984 != prefix)]
        if len(bad):
            problems.append(f"wilaya {code}: communes from other 1984 wilayas {bad.commune_code.tolist()}")
    for code, prefix in NEW_WILAYAS_2019.items():
        bad = com[(com.wilaya_code == code) & (com.wilaya_code_1984 != prefix)]
        if len(bad):
            problems.append(f"wilaya {code}: communes from other 1984 wilayas {bad.commune_code.tolist()}")
    # a 1984 wilaya may only split into itself and its documented children
    children: dict[str, set[str]] = {}
    for code, (_, _, p) in NEW_WILAYAS_2026.items():
        children.setdefault(p, set()).add(code)
    for code, p in NEW_WILAYAS_2019.items():
        children.setdefault(p, set()).add(code)
    for p, grp in com.groupby("wilaya_code_1984"):
        allowed = {p} | children.get(p, set())
        extra = set(grp.wilaya_code) - allowed
        if extra:
            problems.append(f"1984 wilaya {p}: communes assigned to {sorted(extra)} "
                            f"({grp[grp.wilaya_code.isin(extra)].commune_code.tolist()})")
    low = com[com.wilaya_assignment_share < 0.9]
    if problems:
        raise SystemExit("legal consistency checks failed:\n  " + "\n  ".join(problems))
    assert len(set(com.wilaya_code)) == 69, sorted(set(com.wilaya_code))

    # ---- attributes and nesting
    wattr = gpd.read_file(BASE_WILAYAS).drop(columns="geometry").set_index("wilaya_code")
    com["wilaya_name"] = com.wilaya_code.map(wattr["name"])
    com["wilaya_name_ar"] = com.wilaya_code.map(wattr["name_ar"])
    com["area_km2"] = (com.to_crs(EQUAL_AREA).area / 1e6).round(2)
    com["source"] = "OpenStreetMap"
    com["snapshot"] = args.version
    com = com[["commune_code", "name", "name_ar", "name_en", "wilaya_code", "wilaya_name", "wilaya_name_ar",
               "wilaya_code_1984", "area_km2", "osm_relation", "wikidata", "wilaya_assignment_share",
               "source", "snapshot", "geometry"]].sort_values("commune_code").reset_index(drop=True)

    adm1 = com.dissolve(by="wilaya_code", as_index=False)[["wilaya_code", "geometry"]]
    adm1["geometry"] = adm1.geometry.apply(as_multi)
    for col in ["name", "name_ar", "name_en", "iso_3166_2", "osm_relation", "wikidata"]:
        adm1[col] = adm1.wilaya_code.map(wattr[col])
    adm1["n_communes"] = adm1.wilaya_code.map(counts)
    adm1["area_km2"] = (adm1.to_crs(EQUAL_AREA).area / 1e6).round(1)
    adm1["source"] = "Union of AEO communes (OpenStreetMap)"
    adm1["snapshot"] = args.version
    adm1 = adm1[["wilaya_code", "name", "name_ar", "name_en", "iso_3166_2", "n_communes", "area_km2",
                 "osm_relation", "wikidata", "source", "snapshot", "geometry"]].sort_values("wilaya_code")

    adm0 = gpd.GeoDataFrame([{"iso_3166_1": "DZ", "name": "Algeria", "name_ar": "الجزائر",
                              "n_wilayas": 69, "n_communes": len(com), "source": "Union of AEO communes (OpenStreetMap)",
                              "snapshot": args.version, "geometry": as_multi(unary_union(com.geometry.values))}], crs=4326)
    adm0["area_km2"] = (adm0.to_crs(EQUAL_AREA).area / 1e6).round(0)

    # compare with the 2026-11-19 wilaya polygons
    old = gpd.read_file(BASE_WILAYAS).to_crs(EQUAL_AREA).set_index("wilaya_code")
    new = adm1.to_crs(EQUAL_AREA).set_index("wilaya_code")
    diff_km2 = {c: round(old.geometry[c].symmetric_difference(new.geometry[c]).area / 1e6, 1) for c in new.index}

    files = {"adm0": out / "dza_adm0.geojson", "adm1": out / "dza_adm1_wilayas.geojson",
             "adm2": out / "dza_adm2_communes.geojson"}
    adm0.to_file(files["adm0"], driver="GeoJSON", COORDINATE_PRECISION=6)
    adm1.to_file(files["adm1"], driver="GeoJSON", COORDINATE_PRECISION=6)
    com.to_file(files["adm2"], driver="GeoJSON", COORDINATE_PRECISION=6)
    com.drop(columns="geometry").to_csv(out / "dza_admin_units.csv", index=False, encoding="utf-8")

    # display versions: simplify communes once, then dissolve (shared borders stay identical)
    mapshaper = "npx --yes mapshaper@0.6.102"
    d2 = out / "dza_adm2_communes_display.geojson"
    subprocess.run(f'{mapshaper} "{files["adm2"]}" -simplify 6% keep-shapes -filter-fields '
                   f'commune_code,name,name_ar,wilaya_code,wilaya_name,area_km2 -o "{d2}" format=geojson precision=0.0001',
                   shell=True, check=True, cwd=ROOT)
    subprocess.run(f'{mapshaper} "{d2}" -dissolve wilaya_code copy-fields=wilaya_name -rename-fields name=wilaya_name '
                   f'-o "{out / "dza_adm1_wilayas_display.geojson"}" format=geojson precision=0.0001',
                   shell=True, check=True, cwd=ROOT)
    subprocess.run(f'{mapshaper} "{d2}" -dissolve -each "name=\'Algeria\'" -o "{out / "dza_adm0_display.geojson"}" '
                   f'format=geojson precision=0.0001', shell=True, check=True, cwd=ROOT)
    # restore wilaya attributes on the dissolved display layer (map popups)
    d1 = out / "dza_adm1_wilayas_display.geojson"
    gj = json.loads(d1.read_text(encoding="utf-8"))
    attrs = adm1.drop(columns="geometry").set_index("wilaya_code")
    for f in gj["features"]:
        code = f["properties"]["wilaya_code"]
        row = attrs.loc[code]
        f["properties"] = {"wilaya_code": code, "name": row["name"], "name_ar": row["name_ar"],
                           "iso_3166_2": row["iso_3166_2"], "n_communes": int(row["n_communes"]),
                           "area_km2": float(row["area_km2"]), "osm_relation": int(row["osm_relation"]),
                           "snapshot": args.version}
    d1.write_text(json.dumps(gj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    prov = {
        "dataset": "aeo-dza-admin-boundaries", "version": args.version,
        "legal_basis": "Loi n° 26-06 du 4 avril 2026 (JO n° 25 du 5 avril 2026): 69 wilayas, 1,541 communes; names of wilayas 59-69: Décret présidentiel n° 26-206 (JO n° 40 du 3 juin 2026).",
        "inputs": {"openstreetmap": {"api": OVERPASS, "query": query, "retrieved": args.version,
                                      "relations": len(seen)},
                   "query_extra": query_extra,
                   "extra_relations": {str(k): v for k, v in EXTRA_RELATIONS.items()},
                   "excluded_relations": {str(k): v for k, v in EXCLUDE_RELATIONS.items()},
                   "codes_added": {str(k): v for k, v in MISSING_ONS.items()},
                   "wilaya_assignment": str(BASE_WILAYAS.relative_to(ROOT)).replace("\\", "/"),
                   "land_mask": "geoBoundaries DZA ADM0 (gbOpen, OSM-derived, ODbL)"},
        "counts": {"communes": len(com), "wilayas": int(adm1.shape[0])},
        "checks_passed": [
            "1,541 communes with unique 4-digit ONS codes (Loi 26-06 Art. 3)",
            "Commune counts of wilayas 59-69 equal the lists in law 26-06 (Aflou 12, Barika 8, El Kantara 5, Bir El Ater 4, El Aricha 4, Ksar Chellala 6, Aïn Ouessara 10, Messaad 8, Ksar El Boukhari 21, Bou Saâda 23, El Abiodh Sidi Cheikh 7)",
            "Every commune of wilayas 49-69 carries the 1984 ONS prefix of its mother wilaya",
            "Every 1984 wilaya splits only into itself and its documented new wilayas",
        ],
        "commune_overlaps_removed_km2": overlaps,
        "communes_with_assignment_share_below_0.9": low[["commune_code", "name", "wilaya_code", "wilaya_assignment_share"]].to_dict("records"),
        "wilaya_difference_vs_2026-11-19_km2": diff_km2,
        "notes": [
            "commune_code is the ONS code (4 digits) as tagged in OpenStreetMap; its first two digits are the wilaya of the 1984 scheme (wilaya_code_1984), not the 2026 wilaya.",
            "wilaya_code is the 2026 code (01-69). Wilaya polygons are the union of their communes.",
            "area_km2: planimetric area in a Lambert azimuthal equal-area projection; not an official statistic.",
            "Community-mapped boundaries; not a legal or cadastral delineation.",
        ],
        "crs": "EPSG:4326", "license": "ODbL-1.0",
        "attribution": "© OpenStreetMap contributors; processing: Algeria Earth Observatory",
        "code": "scripts/processing/build_admin.py",
    }
    (out / "PROVENANCE.json").write_text(json.dumps(prov, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"communes": len(com), "wilayas": int(adm1.shape[0]), "overlaps": len(overlaps),
                      "low_share": len(low), "max_wilaya_diff_km2": max(diff_km2.values())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
