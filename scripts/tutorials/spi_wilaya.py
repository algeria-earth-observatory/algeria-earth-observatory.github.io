"""AEO tutorial: compute SPI-3 for one wilaya and check it against the AEO SPI product.

Objective: from monthly area-mean precipitation (AEO, CHIRPS v3.0), compute the Standardized
Precipitation Index over 3 months with a gamma distribution fitted per calendar month on
1991–2020, exactly as the AEO product does, and compare.

Requires: numpy, pandas, pyarrow, scipy  (e.g. `pip install numpy pandas pyarrow scipy`)
Downloads two small files (about 0.2 MB) from the AEO website, or reads them from a local copy.

Usage:  python spi_wilaya.py [wilaya_code] [--local path/to/public]
"""
from __future__ import annotations

import argparse
import io
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import gamma, norm

SITE = "https://algeria-earth-observatory.github.io"
PRECIP = "/data/aeo/products/precipitation/v1.0.0/tables/aeo_precip_monthly_admin1_v1.0.0.parquet"
SPI = "/data/aeo/products/spi/v1.0.0/tables/aeo_spi_monthly_admin1_v1.0.0.parquet"


def read(path: str, local: Path | None) -> pd.DataFrame:
    if local:
        return pd.read_parquet(local / path.lstrip("/"))
    with urllib.request.urlopen(SITE + path, timeout=60) as r:
        return pd.read_parquet(io.BytesIO(r.read()))


def gamma_lmoments(x: np.ndarray) -> tuple[float, float]:
    """Gamma shape and scale from L-moments (unbiased PWMs; Hosking's approximation)."""
    x = np.sort(x)
    n = x.size
    b0 = x.mean()
    b1 = np.sum((np.arange(n) / (n - 1)) * x) / n
    l1, l2 = b0, 2 * b1 - b0
    t = l2 / l1  # L-CV
    if t < 0.5:
        z = np.pi * t * t
        a = (1 - 0.3080 * z) / (z - 0.05812 * z * z + 0.01765 * z ** 3)
    else:
        z = 1 - t
        a = (0.7213 * z - 0.5947 * z * z) / (1 - 2.1817 * z + 1.2113 * z * z)
    return a, l1 / a


def spi(precip: pd.Series, months: pd.Series, years: pd.Series, k: int = 3) -> np.ndarray:
    acc = precip.rolling(k).sum().to_numpy()          # k-month totals (first k-1 are NaN)
    out = np.full(acc.shape, np.nan)
    ref = ((years >= 1991) & (years <= 2020)).to_numpy()
    for m in range(1, 13):
        sel = (months == m).to_numpy()
        r = acc[sel & ref]
        r = r[~np.isnan(r)]
        q = np.mean(r == 0)                          # probability of a dry accumulation
        pos = r[r > 0]
        if pos.size < 10:
            continue                                 # too few rainy values to fit
        a, b = gamma_lmoments(pos)
        x = acc[sel]
        h = q + (1 - q) * gamma.cdf(np.nan_to_num(x), a, scale=b)   # mixed distribution
        z = np.clip(norm.ppf(h), -3.09, 3.09)
        z[np.isnan(x)] = np.nan
        out[sel] = z
    return out


def main(code: str = "19", local: Path | None = None) -> pd.DataFrame:
    p = read(PRECIP, local)
    p = p[p.unit_code == code].sort_values(["year", "month"]).reset_index(drop=True)
    p["spi_3_tutorial"] = spi(p.precip_mm, p.month, p.year, 3)
    aeo = read(SPI, local)
    aeo = aeo[aeo.unit_code == code][["year", "month", "spi_3"]]
    df = p.merge(aeo, on=["year", "month"])
    diff = (df.spi_3_tutorial - df.spi_3).abs().max()
    print(f"{p.unit_name.iloc[0]} (wilaya {code}): {df.spi_3.notna().sum()} months; "
          f"largest difference from the AEO product: {diff:.4f} (AEO values are rounded to 0.001)")
    last = df.dropna(subset=["spi_3"]).iloc[-1]
    print(f"Latest SPI-3 ({int(last.year)}-{int(last.month):02d}): {last.spi_3:+.2f}")
    dry = df[(df.year >= 2015) & (df.spi_3 <= -1)]
    print(f"Months with SPI-3 <= -1 since 2015: {len(dry)}")
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("wilaya", nargs="?", default="19")
    ap.add_argument("--local", type=Path, default=None, help="path to a local copy of the site's public/ folder")
    a = ap.parse_args()
    main(a.wilaya, a.local)
