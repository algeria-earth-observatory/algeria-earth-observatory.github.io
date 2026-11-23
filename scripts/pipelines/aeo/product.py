"""Shared helpers for AEO product builds: unit weights, tables, web JSON, map PNGs, manifests.

Every product follows the same layout (as precipitation, SPEI and SPI):
  public/data/aeo/products/<name>/v<version>/
    tables/   CSV + Parquet per level (download assets, with SHA-256 in the manifest)
    web/      compact JSON for the browser (admin0.json, admin1.json, admin2/<wilaya>.json)
    map/      display PNGs in Web Mercator + map.json (colours are classes, not data)
    manifest.json, PROVENANCE.json
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds

from .stats import Grid, ZonalWeights, sparse_coverage

ROOT = Path(__file__).resolve().parents[3]
BOUNDARY_VERSION = "2026-11-20"
BDIR = ROOT / "public/data/aeo/boundaries" / BOUNDARY_VERSION


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def today() -> str:
    return dt.date.today().isoformat()


# ----------------------------------------------------------------------------- units
class Units:
    """AEO units (admin0, admin1, admin2) with zonal weights on one grid.

    Weights come from commune coverage fractions; wilayas and the country are exact merges of
    their communes, so national = area-weighted mean of wilayas = of communes.
    """

    def __init__(self, grid: Grid, supersample: int = 4):
        self.grid = grid
        c = gpd.read_file(BDIR / "dza_adm2_communes.geojson").to_crs(4326)
        c["commune_code"] = c["commune_code"].astype(str)
        c["wilaya_code"] = c["wilaya_code"].astype(str).str.zfill(2)
        self.communes = c.reset_index(drop=True)
        w = gpd.read_file(BDIR / "dza_adm1_wilayas.geojson")
        code_col = next(k for k in ("wilaya_code", "code") if k in w.columns)
        w[code_col] = w[code_col].astype(str).str.zfill(2)
        self.wilayas = w.rename(columns={code_col: "code"}).sort_values("code").reset_index(drop=True)
        cov, self.tiny = sparse_coverage(list(self.communes.geometry), grid, supersample)
        self.w2 = ZonalWeights(cov, grid)
        groups = [list(np.flatnonzero(self.communes.wilaya_code.values == k)) for k in self.wilayas.code]
        self.w1 = ZonalWeights.merge(self.w2, groups)
        self.w0 = ZonalWeights.merge(self.w2, [list(range(len(self.communes)))])
        self.meta = {
            "admin0": [{"code": "DZ", "name": "Algeria", "parent": None}],
            "admin1": [{"code": r.code, "name": r["name"], "parent": "DZ"} for _, r in self.wilayas.iterrows()],
            "admin2": [{"code": r.commune_code, "name": r["name"], "parent": r.wilaya_code} for _, r in self.communes.iterrows()],
        }

    def weights(self, level: str) -> ZonalWeights:
        return {"admin0": self.w0, "admin1": self.w1, "admin2": self.w2}[level]

    @staticmethod
    def reweight(zw: ZonalWeights, cell_factor: np.ndarray) -> ZonalWeights:
        """Weights multiplied by a per-cell factor (e.g. stable-cropland share of the cell)."""
        f = cell_factor.ravel()
        new = ZonalWeights.__new__(ZonalWeights)
        new.cells = zw.cells
        new.fractions = zw.fractions
        new.weights = [w * f[idx] for idx, w in zip(zw.cells, zw.weights)]
        return new


# ----------------------------------------------------------------------------- outputs
def write_table(df: pd.DataFrame, out: Path, stem: str, level: str, version: str, title: str, csv: bool = True) -> list[dict]:
    """Write <stem>_<level>_v<version>.{csv,parquet}; return manifest download_assets entries."""
    (out / "tables").mkdir(parents=True, exist_ok=True)
    site = "/" + out.relative_to(ROOT / "public").as_posix()
    assets = []
    fmts = (["csv"] if csv else []) + ["parquet"]
    for ext in fmts:
        p = out / "tables" / f"{stem}_{level}_v{version}.{ext}"
        if ext == "csv":
            df.to_csv(p, index=False, lineterminator="\n")
        else:
            df.to_parquet(p, index=False)
        assets.append({"href": f"{site}/tables/{p.name}", "format": ext.upper(), "level": level, "role": "statistics",
                       "title": f"{title}, {level}", "bytes": p.stat().st_size, "sha256": sha256(p)})
    return assets


def r(x, d: int = 2):
    """Round an array to a JSON-friendly nested list with None for NaN."""
    a = np.asarray(x, float)
    out = np.round(a, d).astype(object)
    out[np.isnan(a)] = None
    return out.tolist()


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


class MercatorPNG:
    """Display PNGs in Web Mercator from a regular lon/lat grid (nearest neighbour, classes)."""

    def __init__(self, grid: Grid, resolution_m: float, inside: np.ndarray | None = None):
        self.grid = grid
        self.inside = inside
        b = array_bounds(grid.nrow, grid.ncol, grid.transform)
        self.t, self.w, self.h = calculate_default_transform("EPSG:4326", "EPSG:3857", grid.ncol, grid.nrow, *b, resolution=resolution_m)
        lw, ls, le, ln = transform_bounds("EPSG:3857", "EPSG:4326", *array_bounds(self.h, self.w, self.t))
        self.coordinates = [[lw, ln], [le, ln], [le, ls], [lw, ls]]

    def warp(self, a: np.ndarray) -> np.ndarray:
        src = a.astype("float32")
        if self.inside is not None:
            src = np.where(self.inside, src, np.nan)
        out = np.full((self.h, self.w), np.nan, np.float32)
        reproject(src, out, src_transform=self.grid.transform, src_crs="EPSG:4326", src_nodata=np.nan,
                  dst_transform=self.t, dst_crs="EPSG:3857", dst_nodata=np.nan, resampling=Resampling.nearest)
        return out

    @staticmethod
    def colorize(a: np.ndarray, breaks: list[float], colors: list[str]) -> np.ndarray:
        rgb = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in colors], np.uint8)
        idx = np.digitize(a, breaks)
        out = np.zeros((*a.shape, 4), np.uint8)
        ok = ~np.isnan(a)
        out[ok, :3] = rgb[idx[ok]]
        out[ok, 3] = 255
        return out

    def write(self, path: Path, a: np.ndarray, breaks: list[float], colors: list[str]) -> None:
        rgba = self.colorize(self.warp(a), breaks, colors)
        path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(path, "w", driver="PNG", width=rgba.shape[1], height=rgba.shape[0], count=4, dtype="uint8") as ds:
            ds.write(np.moveaxis(rgba, 2, 0))
        aux = Path(str(path) + ".aux.xml")
        if aux.exists():
            aux.unlink()


def write_manifest(out: Path, manifest: dict, provenance: dict) -> None:
    manifest = {"boundary_version": BOUNDARY_VERSION, "created": today(), **manifest}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "PROVENANCE.json").write_text(json.dumps({"created": today(), **provenance}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
