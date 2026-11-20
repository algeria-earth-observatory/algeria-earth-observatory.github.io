"""Unit tests for scripts/pipelines/aeo/stats.py using small SYNTHETIC fixtures.

Synthetic data are used only in tests; they are never published as observations.
"""
import math

import numpy as np
import pytest
from scipy.stats import kendalltau, theilslopes
from shapely.geometry import box

from aeo.stats import Grid, ZonalWeights, coverage_fractions, mann_kendall, theil_sen

GRID = Grid(west=0.0, north=2.0, res=0.5, ncol=4, nrow=4)  # 0–2°E, 0–2°N


def test_cell_area_matches_spherical_band():
    g = Grid(west=-180, north=90, res=1.0, ncol=360, nrow=180)
    total = (g.cell_area_km2() * g.ncol).sum()
    assert total == pytest.approx(4 * math.pi * 6371.0072 ** 2, rel=1e-9)


def test_cell_area_decreases_poleward():
    g = Grid(west=0, north=40, res=0.05, ncol=1, nrow=400)
    a = g.cell_area_km2().ravel()
    assert np.all(np.diff(a) > 0)  # rows go south, cells get larger towards the equator
    assert a[0] == pytest.approx(0.05 * 111.2 * 0.05 * 111.2 * math.cos(math.radians(39.975)), rel=2e-3)


def test_coverage_fractions_aligned_and_half_cells():
    full = box(0.0, 1.5, 0.5, 2.0)          # exactly the top-left cell
    half = box(0.5, 1.5, 0.75, 2.0)         # left half of the next cell
    f = coverage_fractions([full, half], GRID, supersample=10)
    assert f[0, 0, 0] == pytest.approx(1.0)
    assert f[0].sum() == pytest.approx(1.0)
    assert f[1, 0, 1] == pytest.approx(0.5, abs=0.1)


def test_adjacent_units_partition_cells():
    a = box(0.0, 0.0, 0.83, 2.0)
    b = box(0.83, 0.0, 2.0, 2.0)
    f = coverage_fractions([a, b], GRID, supersample=20)
    assert np.allclose(f.sum(0), 1.0, atol=1e-6)


def test_zonal_mean_weights_and_nan():
    unit = box(0.0, 0.0, 1.0, 2.0)  # first two columns
    f = coverage_fractions([unit], GRID)
    zw = ZonalWeights(f, GRID)
    field = np.zeros((4, 4))
    field[:, 0] = 10.0
    field[:, 1] = 20.0
    m, valid = zw.mean(field)
    # rows have different areas; columns are equal, so the mean is exactly 15
    assert m[0] == pytest.approx(15.0)
    assert valid[0] == pytest.approx(1.0)
    field[0, 1] = np.nan
    m, valid = zw.mean(field)
    assert 10 < m[0] < 15
    assert valid[0] == pytest.approx(1 - GRID.cell_area_km2()[0, 0] / (2 * GRID.cell_area_km2().sum()), rel=1e-6)


def test_zonal_mean_time_axis():
    f = coverage_fractions([box(0, 0, 2, 2)], GRID)
    zw = ZonalWeights(f, GRID)
    cube = np.stack([np.full((4, 4), v) for v in (1.0, 2.0, 3.0)])
    m, _ = zw.mean(cube)
    assert m.shape == (1, 3)
    assert np.allclose(m[0], [1, 2, 3])


def test_theil_sen_matches_scipy():
    rng = np.random.default_rng(42)
    y = 300 + 1.7 * np.arange(40) + rng.normal(0, 25, 40)
    ours = theil_sen(y)
    ref = theilslopes(y, np.arange(40))
    assert ours["slope"] == pytest.approx(ref.slope)
    assert ours["lo"] <= ours["slope"] <= ours["hi"]


def test_theil_sen_ignores_nan():
    y = np.array([1, 2, np.nan, 4, 5, 6, 7, 8.0])
    assert theil_sen(y)["slope"] == pytest.approx(1.0)


def test_mann_kendall_monotonic_series():
    y = np.arange(20, dtype=float)
    r = mann_kendall(y)
    assert r["s"] == 20 * 19 / 2
    assert r["tau"] == pytest.approx(1.0)
    assert r["p"] < 1e-6


def test_mann_kendall_tau_matches_scipy_without_ties():
    rng = np.random.default_rng(7)
    y = rng.normal(0, 1, 35)
    r = mann_kendall(y)
    assert r["tau"] == pytest.approx(kendalltau(np.arange(35), y).statistic)


def test_mann_kendall_no_trend_white_noise_not_significant():
    rng = np.random.default_rng(3)
    p = [mann_kendall(rng.normal(0, 1, 45))["p"] for _ in range(200)]
    # about 5 % false positives expected at alpha = 0.05
    assert 0 <= np.mean(np.array(p) < 0.05) <= 0.12


def test_mann_kendall_requires_eight_values():
    assert mann_kendall(np.array([1.0, 2, 3, 4, 5, 6, 7]))["p"] is None


def test_sparse_coverage_matches_dense():
    from aeo.stats import sparse_coverage
    geoms = [box(0.1, 0.2, 1.3, 1.7), box(1.3, 0.2, 1.9, 1.7)]
    dense = coverage_fractions(geoms, GRID, supersample=10)
    sparse, tiny = sparse_coverage(geoms, GRID, supersample=10)
    assert not tiny
    for k in range(2):
        rebuilt = np.zeros(GRID.nrow * GRID.ncol)
        rebuilt[sparse[k][0]] = sparse[k][1]
        assert np.allclose(rebuilt, dense[k].ravel())


def test_tiny_unit_gets_representative_cell():
    from aeo.stats import sparse_coverage
    tiny_geom = box(0.6, 1.6, 0.601, 1.601)  # far smaller than a sub-cell
    sparse, tiny = sparse_coverage([tiny_geom], GRID, supersample=10)
    assert tiny == [0]
    assert sparse[0][0].tolist() == [1]          # row 0, column 1
    assert 0 < sparse[0][1][0] < 1e-4


def test_merged_weights_equal_direct_weights():
    from aeo.stats import sparse_coverage
    a, b = box(0.1, 0.2, 1.3, 1.7), box(1.3, 0.2, 1.9, 1.7)
    sp, _ = sparse_coverage([a, b], GRID, supersample=20)
    child = ZonalWeights(sp, GRID)
    parent = ZonalWeights.merge(child, [[0, 1]])
    direct = ZonalWeights(sparse_coverage([box(0.1, 0.2, 1.9, 1.7)], GRID, supersample=20)[0], GRID)
    field = np.arange(16, dtype=float).reshape(4, 4)
    assert parent.mean(field)[0][0] == pytest.approx(direct.mean(field)[0][0], rel=1e-9)
    # parent mean = area-weighted mean of child means
    cm, _ = child.mean(field)
    wa = np.array([w.sum() for w in child.weights])
    assert parent.mean(field)[0][0] == pytest.approx((cm * wa).sum() / wa.sum(), rel=1e-12)
