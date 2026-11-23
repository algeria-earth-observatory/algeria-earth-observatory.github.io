"""Publish the AEO stable-cropland product from data-work/cropland/stable_cropland_v1.npz.

Tables (ha, true pixel areas): per commune, wilaya and Algeria — land area mapped by GACED30,
cropland in any year, in at least 13 years (majority), in at least 20 years (stable, the AEO mask),
in all 25 years, and the share of the unit that is stable cropland; plus the full distribution of
the number of cropland years (0–25) per commune.
Map: share of each ~1.2 km cell that is stable cropland (display PNG, Web Mercator).
Mask: the stable-cropland area per cell on the grids used by other AEO products, as a compressed
NPZ download, so the cropland statistics of every product can be reproduced.

Usage: python scripts/pipelines/cropland/publish_stable_cropland.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/pipelines"))
from aeo.product import BDIR, MercatorPNG, sha256, write_json, write_manifest, write_table  # noqa: E402
from aeo.stats import Grid  # noqa: E402

VERSION = "1.0.0"
NPZ = ROOT / "data-work/cropland/stable_cropland_v1.npz"
OUT = ROOT / f"public/data/aeo/products/stable-cropland/v{VERSION}"
SITE = f"/data/aeo/products/stable-cropland/v{VERSION}"
BREAKS = [1, 5, 10, 20, 35, 50]  # % of the cell
COLORS = ["#ffffff00", "#fff7bc", "#fee391", "#fec44f", "#fe9929", "#d95f0e", "#993404"]


def main() -> None:
    z = np.load(NPZ)
    hist = z["years_hist_ha"]
    codes = [str(c) for c in z["commune_codes"]]
    s_min, maj = int(z["stable_min"]), int(z["majority_min"])
    import geopandas as gpd
    c = gpd.read_file(BDIR / "dza_adm2_communes.geojson")
    c["commune_code"] = c["commune_code"].astype(str)
    c["wilaya_code"] = c["wilaya_code"].astype(str).str.zfill(2)
    w = gpd.read_file(BDIR / "dza_adm1_wilayas.geojson")
    w["wilaya_code"] = w["wilaya_code"].astype(str).str.zfill(2)
    info = c.set_index("commune_code")[["name", "wilaya_code"]]
    assert codes[:-1] == list(c.commune_code), "commune order differs from the build"

    def summarise(h):
        return {"land_ha": h.sum(), "cropland_any_year_ha": h[1:].sum(), "cropland_majority_ha": h[maj:].sum(),
                "stable_cropland_ha": h[s_min:].sum(), "cropland_all_years_ha": h[25]}

    rows2 = []
    for i, code in enumerate(codes[:-1]):
        rows2.append({"unit_code": code, "unit_name": info.loc[code, "name"], "parent_code": info.loc[code, "wilaya_code"], **summarise(hist[i])})
    d2 = pd.DataFrame(rows2)
    d1 = d2.groupby("parent_code")[[k for k in d2.columns if k.endswith("_ha")]].sum().reset_index().rename(columns={"parent_code": "unit_code"})
    d1 = d1.merge(w[["wilaya_code", "name"]].rename(columns={"wilaya_code": "unit_code", "name": "unit_name"}), on="unit_code")
    d1["parent_code"] = "DZ"
    tot = hist.sum(0)
    d0 = pd.DataFrame([{"unit_code": "DZ", "unit_name": "Algeria", "parent_code": None, **summarise(tot)}])
    qc = [f"Pixels in Algeria outside any commune polygon: {hist[-1].sum():,.0f} ha ({100 * hist[-1].sum() / tot.sum():.3f} %)"]
    assets = []
    for lv, d in (("admin0", d0), ("admin1", d1), ("admin2", d2)):
        d = d[["unit_code", "unit_name", "parent_code"] + [k for k in d.columns if k.endswith("_ha")]].copy()
        d["stable_share_pct"] = 100 * d.stable_cropland_ha / d.land_ha
        for k in d.columns:
            if k.endswith("_ha"):
                d[k] = d[k].round(0)
        d["stable_share_pct"] = d["stable_share_pct"].round(2)
        assets += write_table(d, OUT, "aeo_stable_cropland", lv, VERSION, "Stable cropland area (GACED30, ≥ 20 of 25 years)")
        web_units = [{"code": t.unit_code, "name": t.unit_name, "parent": t.parent_code, "land_ha": t.land_ha, "any_ha": t.cropland_any_year_ha,
                      "majority_ha": t.cropland_majority_ha, "stable_ha": t.stable_cropland_ha, "all_ha": t.cropland_all_years_ha,
                      "stable_share_pct": t.stable_share_pct} for t in d.itertuples()]
        payload = {"product": "aeo-dza-stable-cropland-gaced30", "version": VERSION, "level": lv, "definition": f"cropland in at least {s_min} of 25 years"}
        if lv == "admin2":
            for wc in sorted({u["parent"] for u in web_units}):
                write_json(OUT / "web/admin2" / f"{wc}.json", {**payload, "units": [u for u in web_units if u["parent"] == wc]})
        else:
            write_json(OUT / "web" / f"{lv}.json", {**payload, "units": web_units})
    hy = pd.DataFrame(hist[:-1], columns=[f"years_{k}_ha" for k in range(26)]).round(0)
    hy.insert(0, "unit_code", codes[:-1])
    assets += write_table(hy, OUT, "aeo_cropland_years_histogram", "admin2", VERSION, "Area by number of cropland years 2000–2024")
    qc.append(f"Algeria: cropland in any year {d0.cropland_any_year_ha[0] / 1e6:.2f} Mha, majority {d0.cropland_majority_ha[0] / 1e6:.2f} Mha, stable {d0.stable_cropland_ha[0] / 1e6:.2f} Mha, all 25 years {d0.cropland_all_years_ha[0] / 1e6:.2f} Mha")
    assert abs(d1.stable_cropland_ha.sum() - (tot[s_min:].sum() - hist[-1][s_min:].sum())) < 5

    # mask download: per-cell stable area on every product grid
    (OUT / "mask").mkdir(parents=True, exist_ok=True)
    mask = OUT / "mask" / f"aeo_stable_cropland_grids_v{VERSION}.npz"
    keep = {k: z[k] for k in z.files if k.startswith("grid_")}
    np.savez_compressed(mask, **keep)
    assets.append({"href": f"{SITE}/mask/{mask.name}", "format": "NPZ", "level": "admin0", "role": "data",
                   "title": "Stable-cropland area per cell (ha) on the CHIRPS 0.05°, WaPOR 1.2 km, CMIP6 and GRACE 0.25° and NMME 1° grids",
                   "bytes": mask.stat().st_size, "sha256": sha256(mask)})

    # map: stable share of each WaPOR-grid cell
    gdef = z["grid_wapor1km_def"]
    g = Grid(west=float(gdef[0]), north=float(gdef[1]), res=float(gdef[2]), ncol=int(gdef[3]), nrow=int(gdef[4]))
    valid = z["grid_wapor1km_valid_ha"]
    share = np.where(valid > 0, 100 * z["grid_wapor1km_stable_ha"] / np.maximum(valid, 1e-9), np.nan)
    share = np.where(share < BREAKS[0], np.nan, share)
    mp = MercatorPNG(g, 1200, valid > 0)
    mp.write(OUT / "map" / "stable_share.png", share, BREAKS, [c[:7] for c in COLORS])
    (OUT / "map" / "map.json").write_text(json.dumps({"coordinates": mp.coordinates, "breaks": BREAKS[1:], "colors": [c for c in COLORS[1:]],
                                                      "units": "% of the cell that is stable cropland",
                                                      "resampling": "nearest neighbour from the 1.17 km grid to 1.2 km Web Mercator pixels (display only); cells under 1 % not shown"}, indent=1), encoding="utf-8")
    write_manifest(OUT, {
        "product_id": "aeo-dza-stable-cropland-gaced30", "title": "Algeria stable cropland 2000–2024 (from GACED30): area by commune, wilaya and Algeria, and the AEO cropland mask",
        "status": "available", "version": VERSION, "geographic_scope": "Algeria", "available_levels": ["admin0", "admin1", "admin2"], "spatial_products_levels": [],
        "source_product": "GACED30 v1, AEO Algeria clip (30 m, annual 2000–2024)", "source_version": "GACED30 v1", "source_doi": "10.5281/zenodo.18199675",
        "source_license": "CC BY 4.0", "license": "CC BY 4.0", "temporal_coverage": {"annual": ["2000", "2024"]},
        "spatial_resolution": "30 m pixels summarised by administrative unit (true pixel areas)", "crs": "EPSG:4326 (areas on the authalic sphere)",
        "units": "hectares; % of unit land area", "formats": ["CSV", "PARQUET", "NPZ"],
        "processing_code": "scripts/pipelines/cropland/build_stable_cropland.py, publish_stable_cropland.py",
        "methodology_url": "/docs/method-stable-cropland/", "definition": f"cropland in at least {s_min} of the 25 years 2000–2024 (GACED30)",
        "download_assets": assets, "web_assets": {"map": f"{SITE}/map/map.json"}, "qc": qc,
    }, {"product": "aeo-dza-stable-cropland-gaced30", "version": VERSION,
        "inputs": {"gaced30_aeo_clip": "data-work/gaced30/out/gaced30_dza_<year>_v1.tif (see the GACED30 Algeria clip PROVENANCE)",
                   "boundaries": str(BDIR.relative_to(ROOT))}, "build_npz_sha256": sha256(NPZ), "method": __doc__, "qc": qc})
    print("\n".join(qc))


if __name__ == "__main__":
    main()
