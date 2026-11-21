"""AEO soil product: SoilGrids 2.0 properties summarised for Algeria, its wilayas and communes.

Source: ISRIC SoilGrids 2.0 (Poggio et al. 2021, doi:10.5194/soil-7-217-2021), CC BY 4.0.
  - mean predictions: 1 km aggregated maps, files.isric.org/soilgrids/latest/data_aggregated/1000m/
  - 5 % and 95 % prediction quantiles: 250 m maps (VRT), averaged in 4 x 4 blocks onto the 1 km grid

What the statistics are
  - SoilGrids values are MODEL PREDICTIONS (machine learning on soil profiles and covariates),
    not field measurements.
  - All computations are done in the native Interrupted Goode Homolosine projection, which is
    equal-area: every 1 km pixel has the same area, so the unweighted mean of the pixels whose
    centre falls in a unit is its area-weighted mean.
  - For each unit, property and depth: mean of the predicted means; mean of the pixel 5 % and
    95 % quantiles (an indication of the pixel-level prediction interval, NOT a confidence
    interval of the unit mean); number of 1 km pixels and share with a prediction.
  - Organic carbon stock (ocs, 0-30 cm) is ISRIC's own stock product (computed by ISRIC from
    SOC, bulk density and coarse fragments); AEO does not convert concentrations into stocks.
    The total stock of a unit is the sum over predicted pixels (t/ha x 100 ha per pixel).
  - Communes with no pixel centre inside are given the pixel at their centroid and flagged.

Outputs: public/data/aeo/products/soil/v1.0.0/ (tables/, web/, map/, manifest.json, PROVENANCE.json).
No SoilGrids raster is redistributed; the source files are linked instead.

Usage: python scripts/pipelines/soil/build_soil.py            (downloads are cached in data-work/soilgrids)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import time
from pathlib import Path

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.vrt")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "3")

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds
from rasterio.windows import from_bounds, bounds as window_bounds

ROOT = Path(__file__).resolve().parents[3]
VERSION = "1.0.0"
BOUNDARY_VERSION = "2026-11-20"
BDIR = ROOT / "public" / "data" / "aeo" / "boundaries" / BOUNDARY_VERSION
OUT = ROOT / "public" / "data" / "aeo" / "products" / "soil" / f"v{VERSION}"
SITE = f"/data/aeo/products/soil/v{VERSION}"
CACHE = ROOT / "data-work" / "soilgrids"
SRC = "https://files.isric.org/soilgrids/latest"
ALGERIA_BBOX = (-8.7, 18.9, 12.0, 37.2)

# name, label, mapped units, conversion factor (divide), conventional units  (ISRIC SoilGrids FAQ)
PROPS = {
    "soc": ("Soil organic carbon (concentration)", "dg/kg", 10, "g/kg"),
    "phh2o": ("Soil pH (in water)", "pH x 10", 10, "pH"),
    "clay": ("Clay fraction", "g/kg", 10, "%"),
    "sand": ("Sand fraction", "g/kg", 10, "%"),
    "silt": ("Silt fraction", "g/kg", 10, "%"),
    "bdod": ("Bulk density (fine earth)", "cg/cm3", 100, "kg/dm3"),
    "cec": ("Cation exchange capacity (pH 7)", "mmol(c)/kg", 10, "cmol(c)/kg"),
    "nitrogen": ("Total nitrogen", "cg/kg", 100, "g/kg"),
    "cfvo": ("Coarse fragments (volume)", "cm3/dm3", 10, "vol %"),
}
DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]
LAYERS = [(p, d) for p in PROPS for d in DEPTHS] + [("ocs", "0-30cm")]
OCS = ("Organic carbon stock", "t/ha", 1, "t/ha")


def meta(prop):
    return OCS if prop == "ocs" else PROPS[prop]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def read_layer(prop: str, depth: str, kind: str, grid: dict) -> np.ndarray:
    """Return the layer on the 1 km Algeria grid, in conventional units (NaN = no prediction)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"{prop}_{depth}_{kind}.npy"
    if cache.exists():
        return np.load(cache)
    fac = meta(prop)[2]
    t0 = time.time()
    if kind == "mean":
        url = f"/vsicurl/{SRC}/data_aggregated/1000m/{prop}/{prop}_{depth}_mean_1000.tif"
        with rasterio.open(url) as ds:
            w = from_bounds(*grid["bounds"], ds.transform).round_offsets().round_lengths()
            a = ds.read(1, window=w).astype(np.float32)
            nod = ds.nodata
        assert a.shape == grid["shape"], (a.shape, grid["shape"])
    else:  # Q0.05 / Q0.95 at 250 m, averaged in 4 x 4 blocks onto the 1 km grid
        url = f"/vsicurl/{SRC}/data/{prop}/{prop}_{depth}_{kind}.vrt"
        with rasterio.open(url) as ds:
            w = from_bounds(*grid["bounds"], ds.transform).round_offsets().round_lengths()
            a4 = ds.read(1, window=w).astype(np.float32)
            nod = ds.nodata
        h, wd = grid["shape"]
        a4 = a4[: h * 4, : wd * 4]
        assert a4.shape == (h * 4, wd * 4), (a4.shape, grid["shape"])
        a4[a4 == nod] = np.nan
        blocks = a4.reshape(h, 4, wd, 4)
        with np.errstate(invalid="ignore"):
            a = np.nanmean(blocks, axis=(1, 3))
        nod = None
    if nod is not None:
        a[a == nod] = np.nan
    a = a / fac
    np.save(cache, a)
    print(f"  {prop} {depth} {kind}: {time.time() - t0:.0f} s", flush=True)
    return a


def main() -> None:
    # ------------------------------------------------------------ grid (1 km Homolosine window over Algeria)
    with rasterio.open(f"/vsicurl/{SRC}/data_aggregated/1000m/soc/soc_0-5cm_mean_1000.tif") as ds:
        crs = ds.crs
        b = transform_bounds("EPSG:4326", crs, *ALGERIA_BBOX, densify_pts=100)
        w = from_bounds(*b, ds.transform).round_offsets().round_lengths()
        transform = ds.window_transform(w)
        grid = {"bounds": window_bounds(w, ds.transform), "shape": (int(w.height), int(w.width)), "transform": transform, "crs": crs}
    with rasterio.open(f"/vsicurl/{SRC}/data/soc/soc_0-5cm_Q0.05.vrt") as q:
        # the 250 m grid must nest exactly in the 1 km grid
        ox = (grid["bounds"][0] - q.transform.c) / q.transform.a
        oy = (q.transform.f - grid["bounds"][3]) / -q.transform.e
        assert abs(ox - round(ox)) < 1e-6 and abs(oy - round(oy)) < 1e-6, (ox, oy)
    print("grid", grid["shape"], crs.to_proj4())

    # ------------------------------------------------------------ zones
    adm0 = gpd.read_file(BDIR / "dza_adm0.geojson").to_crs(crs)
    adm1 = gpd.read_file(BDIR / "dza_adm1_wilayas.geojson").to_crs(crs).sort_values("wilaya_code").reset_index(drop=True)
    adm2 = gpd.read_file(BDIR / "dza_adm2_communes.geojson").to_crs(crs).sort_values("commune_code").reset_index(drop=True)
    shape, tr = grid["shape"], grid["transform"]

    def zones(gdf):
        lab = rasterize(((g, i + 1) for i, g in enumerate(gdf.geometry)), out_shape=shape, transform=tr, fill=0, dtype="int32")
        idx = [np.flatnonzero(lab.ravel() == i + 1) for i in range(len(gdf))]
        fallback = []
        for i, ix in enumerate(idx):
            if ix.size == 0:  # no pixel centre inside: use the pixel at the centroid
                c = gdf.geometry.iloc[i].representative_point()
                r, col = rasterio.transform.rowcol(tr, c.x, c.y)
                idx[i] = np.array([r * shape[1] + col])
                fallback.append(i)
        return idx, set(fallback)

    units = []
    for level, gdf, code_col, name_col, parent in [
        ("admin0", adm0, None, None, None), ("admin1", adm1, "wilaya_code", "name", "DZ"), ("admin2", adm2, "commune_code", "name", None),
    ]:
        idx, fb = zones(gdf)
        for i in range(len(gdf)):
            r = gdf.iloc[i]
            units.append({
                "level": level,
                "unit_code": "DZ" if level == "admin0" else str(r[code_col]),
                "unit_name": "Algeria" if level == "admin0" else str(r[name_col]),
                "unit_name_ar": "الجزائر" if level == "admin0" else (r.get("name_ar") or ""),
                "parent_code": None if level == "admin0" else ("DZ" if level == "admin1" else str(r["wilaya_code"])),
                "idx": idx[i], "centroid_pixel": i in fb,
            })
    print("zones", sum(u["level"] == "admin2" for u in units), "communes;", sum(u["centroid_pixel"] for u in units), "centroid-pixel fallbacks")

    # ------------------------------------------------------------ statistics
    rows = []
    rasters = {}
    for prop, depth in LAYERS:
        mean = read_layer(prop, depth, "mean", grid).ravel()
        q05 = read_layer(prop, depth, "Q0.05", grid).ravel()
        q95 = read_layer(prop, depth, "Q0.95", grid).ravel()
        rasters[(prop, depth)] = mean.reshape(shape)
        label, _, _, cu = meta(prop)
        for u in units:
            v = mean[u["idx"]]
            ok = ~np.isnan(v)
            n, nv = int(v.size), int(ok.sum())
            row = {
                "level": u["level"], "unit_code": u["unit_code"], "unit_name": u["unit_name"], "parent_code": u["parent_code"],
                "property": prop, "property_label": label, "depth": depth, "units": cu,
                "mean": round(float(v[ok].mean()), 3) if nv else None,
                "q05_mean": round(float(np.nanmean(q05[u["idx"]])), 3) if nv and np.isfinite(q05[u["idx"]]).any() else None,
                "q95_mean": round(float(np.nanmean(q95[u["idx"]])), 3) if nv and np.isfinite(q95[u["idx"]]).any() else None,
                "pixels_1km": n, "valid_pct": round(100 * nv / n, 1),
                "total_stock_Mt": round(float(np.nansum(v) * 100 / 1e6), 4) if prop == "ocs" and nv else None,
                "support": "centroid pixel only" if u["centroid_pixel"] else ("limited (< 10 km² predicted)" if nv < 10 else "adequate"),
            }
            rows.append(row)
    df = pd.DataFrame(rows)

    # ------------------------------------------------------------ QC
    qc = []
    for prop, depth in LAYERS:
        d = df[(df.property == prop) & (df.depth == depth)]
        nat = d[d.level == "admin0"].iloc[0]
        w1 = d[d.level == "admin1"]
        recon = (w1["mean"] * w1["pixels_1km"] * w1["valid_pct"]).sum() / (w1["pixels_1km"] * w1["valid_pct"]).sum()
        diff = abs(recon - nat["mean"])
        assert diff < 0.02 * max(1.0, abs(nat["mean"])), (prop, depth, recon, nat["mean"])
        assert (d["q05_mean"].dropna() <= d["q95_mean"].dropna() + 1e-6).all(), (prop, depth)
    qc.append("National mean equals the pixel-weighted mean of the 69 wilaya means for every layer (within 2 %, boundary-pixel effects)")
    tex = df[df.property.isin(["clay", "sand", "silt"]) & (df.level == "admin1")].pivot_table(index=["unit_code", "depth"], columns="property", values="mean")
    s = tex.sum(axis=1)
    qc.append(f"Clay + sand + silt per wilaya and depth: {s.min():.1f}–{s.max():.1f} %")
    ph = df[(df.property == "phh2o")]["mean"].dropna()
    assert ph.between(3, 11).all()
    qc.append(f"pH range of unit means: {ph.min():.2f}–{ph.max():.2f}")
    print("\n".join(qc))

    # ------------------------------------------------------------ outputs
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "web").mkdir(parents=True, exist_ok=True)
    (OUT / "map").mkdir(parents=True, exist_ok=True)
    assets = []
    for level in ["admin0", "admin1", "admin2"]:
        d = df[df.level == level].reset_index(drop=True)
        for fmt in ["csv", "parquet"]:
            p = OUT / "tables" / f"aeo_soil_stats_{level}_v{VERSION}.{fmt}"
            (d.to_csv(p, index=False, lineterminator="\n") if fmt == "csv" else d.to_parquet(p, index=False, compression="snappy"))
            assets.append({"href": f"{SITE}/tables/{p.name}", "format": fmt.upper(), "level": level, "role": "statistics",
                           "title": f"Soil statistics (SoilGrids 2.0, 0–30 cm), {level}", "bytes": p.stat().st_size, "sha256": sha256(p)})
        layer_ids = [f"{p}_{dp}" for p, dp in LAYERS]
        us = d.drop_duplicates("unit_code")[["unit_code", "unit_name", "parent_code"]]
        web = {
            "product": "aeo-dza-soil-soilgrids", "version": VERSION, "level": level, "boundary_version": BOUNDARY_VERSION,
            "layers": [{"id": f"{p}_{dp}", "property": p, "depth": dp, "label": meta(p)[0], "units": meta(p)[3]} for p, dp in LAYERS],
            "units": [{"code": r.unit_code, "name": r.unit_name, "parent": r.parent_code,
                       "support": d[(d.unit_code == r.unit_code)].iloc[0]["support"]} for r in us.itertuples()],
            "mean": {}, "q05": {}, "q95": {}, "valid_pct": {}, "total_stock_Mt": None,
        }
        for lid, (p, dp) in zip(layer_ids, LAYERS):
            dd = d[(d.property == p) & (d.depth == dp)].set_index("unit_code").loc[us.unit_code]
            for k, col in [("mean", "mean"), ("q05", "q05_mean"), ("q95", "q95_mean"), ("valid_pct", "valid_pct")]:
                web[k][lid] = [None if pd.isna(x) else float(x) for x in dd[col]]
            if p == "ocs":
                web["total_stock_Mt"] = [None if pd.isna(x) else float(x) for x in dd["total_stock_Mt"]]
        if level == "admin2":
            for wcode, grp in us.groupby("parent_code"):
                sel = [i for i, c in enumerate(us.unit_code) if us.iloc[i].parent_code == wcode]
                sub = {**web, "units": [web["units"][i] for i in sel]}
                for k in ["mean", "q05", "q95", "valid_pct"]:
                    sub[k] = {lid: [web[k][lid][i] for i in sel] for lid in layer_ids}
                sub["total_stock_Mt"] = [web["total_stock_Mt"][i] for i in sel]
                (OUT / "web" / "admin2").mkdir(exist_ok=True)
                (OUT / "web" / "admin2" / f"{wcode}.json").write_text(json.dumps(sub, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        else:
            (OUT / "web" / f"{level}.json").write_text(json.dumps(web, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ------------------------------------------------------------ display maps (Web Mercator PNG, classified)
    inside = rasterize(((g, 1) for g in adm0.geometry), out_shape=shape, transform=tr, fill=0, dtype="uint8") == 1
    dst_t, dw, dh = calculate_default_transform(crs, "EPSG:3857", shape[1], shape[0], *array_bounds(shape[0], shape[1], tr), resolution=2000)
    lon_w, lat_s, lon_e, lat_n = transform_bounds("EPSG:3857", "EPSG:4326", *array_bounds(dh, dw, dst_t))
    seq = ["#f3ead8", "#e3cfa6", "#cfb07a", "#b78e55", "#8f6a3b", "#634727", "#3b2a17"]  # light -> dark soil browns
    maps = {}
    for (p, dp), a in rasters.items():
        v = np.where(inside, a, np.nan)
        # more classes in the upper tail: the Sahara holds most pixels with low values
        qs = np.nanquantile(v, [0.15, 0.35, 0.55, 0.75, 0.90, 0.97])
        def nice(x):  # two significant figures
            return float(f"{x:.2g}") if x else 0.0
        br = sorted(set(nice(x) for x in qs))
        m3857 = np.full((dh, dw), np.nan, np.float32)
        reproject(v.astype("float32"), m3857, src_transform=tr, src_crs=crs, src_nodata=np.nan, dst_transform=dst_t, dst_crs="EPSG:3857",
                  dst_nodata=np.nan, resampling=Resampling.nearest)
        cols = seq if len(br) == 6 else seq[: len(br) + 1]
        rgb = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in cols], np.uint8)
        out = np.zeros((dh, dw, 4), np.uint8)
        ok = ~np.isnan(m3857)
        out[ok, :3] = rgb[np.digitize(m3857[ok], br)]
        out[ok, 3] = 235
        path = OUT / "map" / f"{p}_{dp}.png"
        with rasterio.open(path, "w", driver="PNG", width=dw, height=dh, count=4, dtype="uint8") as ds:
            ds.write(np.moveaxis(out, 2, 0))
        aux = Path(str(path) + ".aux.xml")
        if aux.exists():
            aux.unlink()
        maps[f"{p}_{dp}"] = {"breaks": br, "colors": cols, "units": meta(p)[3], "label": meta(p)[0], "depth": dp}
    (OUT / "map" / "map.json").write_text(json.dumps({
        "coordinates": [[lon_w, lat_n], [lon_e, lat_n], [lon_e, lat_s], [lon_w, lat_s]],
        "layers": maps, "resampling": "nearest neighbour from the 1 km Homolosine grid to 2 km Web Mercator pixels (display only); class breaks at the 15/35/55/75/90/97 % quantiles of Algerian pixels, two significant figures",
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # ------------------------------------------------------------ manifest + provenance
    now = dt.date.today().isoformat()
    manifest = {
        "product_id": "aeo-dza-soil-soilgrids", "title": "Algeria soil properties (SoilGrids 2.0), 0–30 cm: national, wilaya and commune statistics",
        "status": "available", "version": VERSION, "geographic_scope": "Algeria",
        "available_levels": ["admin0", "admin1", "admin2"], "spatial_products_levels": [],
        "boundary_version": BOUNDARY_VERSION,
        "source_product": "SoilGrids 2.0 (ISRIC — World Soil Information)", "source_version": "SoilGrids 2.0 (files.isric.org/soilgrids/latest, retrieved " + now + ")",
        "source_doi": "10.5194/soil-7-217-2021", "source_license": "CC BY 4.0", "license": "CC BY 4.0",
        "temporal_coverage": {"snapshot": "SoilGrids 2.0 predictions (static; soil profiles collected over several decades)"},
        "reference_period": None, "spatial_resolution": "1 km (SoilGrids 1 km aggregated means; 5 %/95 % quantiles averaged from 250 m); statistics over administrative units",
        "crs": "Statistics computed in Interrupted Goode Homolosine (equal-area); boundaries in EPSG:4326",
        "units": "per property (see tables: units column)", "formats": ["CSV", "PARQUET"],
        "processing_code": "scripts/pipelines/soil/build_soil.py", "methodology_url": "/docs/method-soil/", "created": now,
        "layers": [{"id": f"{p}_{dp}", "property": p, "depth": dp, "label": meta(p)[0], "mapped_units": meta(p)[1], "conversion_factor": meta(p)[2], "units": meta(p)[3]} for p, dp in LAYERS],
        "download_assets": assets,
        "external_rasters": {"note": "SoilGrids rasters are not redistributed by AEO; use the ISRIC files.", "url": "https://files.isric.org/soilgrids/latest/", "documentation": "https://docs.isric.org/globaldata/soilgrids/"},
        "web_assets": {"admin0": f"{SITE}/web/admin0.json", "admin1": f"{SITE}/web/admin1.json", "admin2": f"{SITE}/web/admin2/{{wilaya_code}}.json", "map": f"{SITE}/map/map.json"},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (OUT / "PROVENANCE.json").write_text(json.dumps({
        "product": "aeo-dza-soil-soilgrids", "version": VERSION, "created": now,
        "inputs": {"mean": f"{SRC}/data_aggregated/1000m/<property>/<property>_<depth>_mean_1000.tif",
                   "quantiles": f"{SRC}/data/<property>/<property>_<depth>_Q0.05.vrt and _Q0.95.vrt (250 m)",
                   "boundaries": f"AEO boundaries {BOUNDARY_VERSION} (full detail)"},
        "grid": {"crs": crs.to_proj4(), "shape": list(shape), "transform": list(tr)[:6]},
        "conversion": "values divided by the ISRIC conversion factor (docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html)",
        "zonal_method": "pixels whose centre falls in the unit (equal-area projection, so the unweighted mean is area-weighted); centroid pixel for units without any pixel centre",
        "qc": qc,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("done", len(df), "rows")


if __name__ == "__main__":
    main()
