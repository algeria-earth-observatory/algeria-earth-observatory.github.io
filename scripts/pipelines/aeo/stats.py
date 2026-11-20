"""Shared statistics for AEO products: zonal weights, zonal means, trends.

The same trend methods are implemented in TypeScript for the browser
(src/lib/trend.ts); tests/python/test_stats.py and tests/js/trend.test.mjs check that
both give identical results on the same series.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from rasterio.features import rasterize
from rasterio.transform import Affine
from scipy.stats import norm

R_AUTHALIC_KM = 6371.0072  # WGS84 authalic sphere radius


# --------------------------------------------------------------------------- grids
@dataclass(frozen=True)
class Grid:
    west: float
    north: float
    res: float
    ncol: int
    nrow: int

    @property
    def transform(self) -> Affine:
        return Affine(self.res, 0, self.west, 0, -self.res, self.north)

    def cell_area_km2(self) -> np.ndarray:
        """Geodesic (authalic-sphere) area of each cell row, km², shape (nrow, 1)."""
        lat_top = self.north - np.arange(self.nrow) * self.res
        lat_bot = lat_top - self.res
        dlon = math.radians(self.res)
        a = R_AUTHALIC_KM ** 2 * dlon * (np.sin(np.radians(lat_top)) - np.sin(np.radians(lat_bot)))
        return a[:, None]


def coverage_fractions(geoms, grid: Grid, supersample: int = 10) -> np.ndarray:
    """Fraction of each grid cell covered by each geometry.

    Returns float32 array (n_geoms, nrow, ncol). Geometries must not overlap. Method:
    rasterize unit ids on a grid `supersample` times finer (pixel-centre rule) and count
    sub-cells per coarse cell; the error per cell is at most about 1/supersample of the
    boundary length within the cell.
    """
    s = supersample
    fine = Affine(grid.res / s, 0, grid.west, 0, -grid.res / s, grid.north)
    ids = rasterize(((g, i + 1) for i, g in enumerate(geoms)), out_shape=(grid.nrow * s, grid.ncol * s),
                    transform=fine, fill=0, dtype="int32")
    n = len(geoms)
    out = np.zeros((n, grid.nrow, grid.ncol), np.float32)
    # count sub-cells of each id in each coarse cell
    coarse_r = np.repeat(np.arange(grid.nrow), s)[:, None]
    coarse_c = np.repeat(np.arange(grid.ncol), s)[None, :]
    flat = (coarse_r * grid.ncol + coarse_c)
    mask = ids > 0
    key = (ids[mask].astype(np.int64) - 1) * (grid.nrow * grid.ncol) + np.broadcast_to(flat, ids.shape)[mask]
    counts = np.bincount(key, minlength=n * grid.nrow * grid.ncol)
    out[:] = (counts.reshape(n, grid.nrow, grid.ncol) / (s * s)).astype(np.float32)
    return out


def sparse_coverage(geoms, grid: Grid, supersample: int = 10):
    """Sparse version of coverage_fractions for many units.

    Returns a list (one per geometry) of (cell_index, fraction) arrays. A unit too small
    to contain any sub-cell centre (area below about (res/supersample)²) gets the cell
    containing a representative point, with fraction = unit area / cell area; such units
    are listed in the second return value.
    """
    s = supersample
    fine = Affine(grid.res / s, 0, grid.west, 0, -grid.res / s, grid.north)
    ids = rasterize(((g, i + 1) for i, g in enumerate(geoms)), out_shape=(grid.nrow * s, grid.ncol * s),
                    transform=fine, fill=0, dtype="int32")
    rr, cc = np.nonzero(ids)
    unit = ids[rr, cc].astype(np.int64) - 1
    cell = (rr // s) * grid.ncol + (cc // s)
    key = unit * (grid.nrow * grid.ncol) + cell
    uniq, counts = np.unique(key, return_counts=True)
    u_of = uniq // (grid.nrow * grid.ncol)
    c_of = uniq % (grid.nrow * grid.ncol)
    frac = counts / (s * s)
    out = [(np.empty(0, np.int64), np.empty(0)) for _ in geoms]
    bounds = np.searchsorted(u_of, np.arange(len(geoms) + 1))
    for k in range(len(geoms)):
        a, b = bounds[k], bounds[k + 1]
        out[k] = (c_of[a:b], frac[a:b])
    tiny = []
    area = grid.cell_area_km2()
    for k, g in enumerate(geoms):
        if out[k][0].size == 0 and not g.is_empty:
            p = g.representative_point()
            r = int((grid.north - p.y) / grid.res)
            c = int((p.x - grid.west) / grid.res)
            # planar area in degrees² -> fraction of the cell (both in degrees²)
            out[k] = (np.array([r * grid.ncol + c]), np.array([min(g.area / grid.res ** 2, 1.0)]))
            tiny.append(k)
    return out, tiny


class ZonalWeights:
    """Sparse per-unit weights = coverage fraction x cell area (km²)."""

    def __init__(self, fractions, grid: Grid):
        """`fractions`: dense array (n, nrow, ncol) or the list returned by sparse_coverage."""
        area = np.broadcast_to(grid.cell_area_km2(), (grid.nrow, grid.ncol)).ravel()
        self.cells: list[np.ndarray] = []
        self.fractions: list[np.ndarray] = []
        self.weights: list[np.ndarray] = []
        for f in fractions:
            if isinstance(f, tuple):
                idx, fr = f
            else:
                idx = np.flatnonzero(f > 0)
                fr = f.ravel()[idx]
            self.cells.append(np.asarray(idx))
            self.fractions.append(np.asarray(fr, float))
            self.weights.append((np.asarray(fr, float) * area[idx]).astype(np.float64))

    @classmethod
    def merge(cls, base: "ZonalWeights", groups: list[list[int]]) -> "ZonalWeights":
        """Weights of parent units made of non-overlapping child units (exact nesting)."""
        new = cls.__new__(cls)
        new.cells, new.fractions, new.weights = [], [], []
        for members in groups:
            idx = np.concatenate([base.cells[m] for m in members])
            fr = np.concatenate([base.fractions[m] for m in members])
            w = np.concatenate([base.weights[m] for m in members])
            u, inv = np.unique(idx, return_inverse=True)
            new.cells.append(u)
            new.fractions.append(np.bincount(inv, fr))
            new.weights.append(np.bincount(inv, w))
        return new

    def support(self) -> tuple[np.ndarray, np.ndarray]:
        """(cells touched, effective number of cells = sum of coverage fractions) per unit."""
        return (np.array([len(c) for c in self.cells]),
                np.array([float(f.sum()) for f in self.fractions]))

    def mean(self, field: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Area-weighted mean of `field` (..., nrow, ncol) per unit, ignoring NaN cells.

        Returns (means, valid_fraction) with shapes (n_units, ...). valid_fraction is the
        share of the unit's weighted area with data.
        """
        lead = field.shape[:-2]
        flat = field.reshape(*lead, -1)
        means = np.full((len(self.cells), *lead), np.nan)
        valid = np.zeros((len(self.cells), *lead))
        for k, (idx, w) in enumerate(zip(self.cells, self.weights)):
            if idx.size == 0:
                continue
            v = flat[..., idx]
            ok = ~np.isnan(v)
            wsum = (ok * w).sum(-1)
            means[k] = np.where(wsum > 0, np.nansum(v * w, -1) / np.where(wsum > 0, wsum, 1), np.nan)
            valid[k] = wsum / w.sum()
        return means, valid


# --------------------------------------------------------------------------- trends
def mann_kendall(y: np.ndarray) -> dict:
    """Two-sided Mann–Kendall test with tie correction.

    If the lag-1 autocorrelation of the Sen-detrended series is significant at 5 %
    (|r1| > 1.96/sqrt(n)), the variance of S is inflated following Yue & Wang (2004)
    for an AR(1) process: n/n* = 1 + 2 * sum_{k=1}^{n-1} (1 - k/n) r1^k.
    Missing values (NaN) are removed first; at least 8 values are required.
    """
    y = np.asarray(y, float)
    x = np.arange(len(y), dtype=float)
    keep = ~np.isnan(y)
    y, x = y[keep], x[keep]
    n = len(y)
    if n < 8:
        return {"n": n, "s": None, "tau": None, "z": None, "p": None, "r1": None, "corrected": False}
    s = 0.0
    for i in range(n - 1):
        s += np.sign(y[i + 1:] - y[i]).sum()
    _, counts = np.unique(y, return_counts=True)
    var_s = (n * (n - 1) * (2 * n + 5) - (counts * (counts - 1) * (2 * counts + 5)).sum()) / 18.0
    slope = theil_sen(y, x)["slope"]
    resid = y - slope * x
    resid = resid - resid.mean()
    r1 = float((resid[:-1] * resid[1:]).sum() / (resid ** 2).sum()) if (resid ** 2).sum() > 0 else 0.0
    corrected = abs(r1) > 1.96 / math.sqrt(n)
    if corrected:
        ratio = 1 + 2 * sum((1 - k / n) * r1 ** k for k in range(1, n))
        var_s *= max(ratio, 1e-9)
    if s > 0:
        z = (s - 1) / math.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / math.sqrt(var_s)
    else:
        z = 0.0
    p = float(2 * (1 - norm.cdf(abs(z))))
    tau = s / (0.5 * n * (n - 1))
    return {"n": n, "s": float(s), "tau": float(tau), "z": float(z), "p": p, "r1": r1,
            "corrected": bool(corrected), "var_s": float(var_s)}


def theil_sen(y: np.ndarray, x: np.ndarray | None = None, alpha: float = 0.05) -> dict:
    """Theil–Sen slope with Sen (1968) rank-based confidence interval (uncorrected var S)."""
    y = np.asarray(y, float)
    x = np.arange(len(y), dtype=float) if x is None else np.asarray(x, float)
    keep = ~np.isnan(y)
    y, x = y[keep], x[keep]
    n = len(y)
    if n < 3:
        return {"slope": None, "lo": None, "hi": None, "intercept": None}
    i, j = np.triu_indices(n, 1)
    dx = x[j] - x[i]
    slopes = np.sort(((y[j] - y[i]) / dx)[dx != 0])
    slope = float(np.median(slopes))
    _, counts = np.unique(y, return_counts=True)
    var_s = (n * (n - 1) * (2 * n + 5) - (counts * (counts - 1) * (2 * counts + 5)).sum()) / 18.0
    # Gilbert (1987): lower = M1-th, upper = (M2+1)-th ordered slope (1-based),
    # M1 = (N' - C)/2, M2 = (N' + C)/2, C = z_{1-alpha/2} sqrt(Var S); rounded outward.
    c = norm.ppf(1 - alpha / 2) * math.sqrt(var_s)
    m = len(slopes)
    m1 = (m - c) / 2
    m2 = (m + c) / 2
    lo = float(slopes[min(max(int(math.floor(m1)) - 1, 0), m - 1)]) if m else None
    hi = float(slopes[min(max(int(math.ceil(m2)), 0), m - 1)]) if m else None
    intercept = float(np.median(y - slope * x))
    return {"slope": slope, "lo": lo, "hi": hi, "intercept": intercept}
