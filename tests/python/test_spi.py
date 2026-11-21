"""SPI (scripts/pipelines/aeo/spi.py) against the R package SPEI (spi, Gamma, ub-pwm, 1991–2020)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "pipelines"))
from aeo.spi import spi, pelgam, MIN_POSITIVE  # noqa: E402
from aeo.spei import accumulate  # noqa: E402

FIX = Path(__file__).resolve().parents[1] / "fixtures"
CASES = json.loads((FIX / "spi_r_cases.json").read_text())
INPUT = pd.read_csv(FIX / "spi_input.csv", dtype={"unit": str})


def series(unit):
    s = INPUT[INPUT.unit == unit].sort_values(["year", "month"])
    return s.precip_mm.to_numpy(float), s.month.to_numpy(int), ((s.year >= 1991) & (s.year <= 2020)).to_numpy()


def test_pelgam_known_values():
    # exponential distribution: L-CV = 1/2 -> shape 1 (rational approximation, |error| < 1e-3)
    a, b = pelgam(10.0, 0.5)
    assert abs(a - 1) < 2e-3 and abs(b - 10) < 2e-2


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: f"{c['unit']}-spi{c['scale']}")
def test_matches_r_where_methods_coincide(case):
    p, m, ref = series(case["unit"])
    k = case["scale"]
    ours = spi(p, m, k, ref, clip=False)
    r = np.array([np.nan if v is None else v for v in case["values"]], float)
    assert r.shape == ours.shape
    acc = accumulate(p, k)
    compared = 0
    for mon in range(1, 13):
        sel = m == mon
        refv = acc[sel & ref]
        refv = refv[~np.isnan(refv)]
        if (refv == 0).any() or (refv > 0).sum() < MIN_POSITIVE:
            continue  # zeros in the reference: R 1.8.1 ignores their probability (see aeo/spi.py)
        idx = np.flatnonzero(sel & ~np.isnan(acc) & (acc > 0))
        ok = idx[~np.isnan(r[idx])]
        np.testing.assert_allclose(ours[ok], r[ok], atol=1e-6, err_msg=f"{case['unit']} SPI-{k} month {mon}")
        compared += ok.size
    if case["unit"] in ("16", "19", "31") and k >= 3:
        assert compared > 400  # humid wilayas: nearly all values compared


def test_zero_accumulations_use_the_mixed_distribution():
    p, m, ref = series("01")  # Adrar: many dry months
    out = spi(p, m, 1, ref, clip=False)
    acc = accumulate(p, 1)
    checked = 0
    for mon in range(1, 13):
        sel = m == mon
        refv = acc[sel & ref]
        q = (refv == 0).mean()
        if q == 0 or (refv > 0).sum() < MIN_POSITIVE:
            continue
        zeros = np.flatnonzero(sel & (acc == 0))
        np.testing.assert_allclose(out[zeros], norm.ppf(q), atol=1e-12)
        checked += zeros.size
    assert checked > 50
    # zeros never give -inf when the reference has zeros (unlike R 1.8.1). -inf remains only for a
    # zero outside the reference in a calendar month without any reference zero (q = 0): an
    # unprecedented value; extreme wet months can likewise reach H = 1. Hence the ±3.09 clip.
    for i in np.flatnonzero(np.isneginf(out)):
        refv = acc[(m == m[i]) & ref]
        assert acc[i] == 0 and not ref[i] and (refv == 0).sum() == 0
    clipped = spi(p, m, 1, ref)
    assert np.all(np.isfinite(clipped[~np.isnan(clipped)])) and np.nanmax(np.abs(clipped)) <= 3.09


def test_reference_period_is_standardised():
    p, m, ref = series("19")
    z = spi(p, m, 3, ref, clip=False)
    zr = z[ref & ~np.isnan(z)]
    assert abs(zr.mean()) < 0.1 and abs(zr.std() - 1) < 0.1
