"""AEO SPI product: Standardized Precipitation Index from the AEO CHIRPS v3.0 unit series.

Input:  the published AEO precipitation product (monthly area-weighted means per unit,
        aeo_precip_monthly_{admin0,admin1,admin2}_v1.0.0.parquet, CHIRPS v3.0, 1981-01 onward).
Method: scripts/pipelines/aeo/spi.py (gamma, unbiased PWM, mixed distribution for zeros,
        reference 1991–2020, clipped to ±3.09), applied to each unit's series for k = 1, 3, 6, 12.
        SPI is computed on the unit-mean precipitation series (the spatial mean is taken first).
Flag:   units whose 1991–2020 normal is below 100 mm/year are flagged `arid`: rainfall is rare,
        many calendar months cannot be fitted, and SPI there is unstable.
Output: public/data/aeo/products/spi/v1.0.0/ (tables/, web/, map/map.json, manifest.json, PROVENANCE.json)

Usage: python scripts/pipelines/spi/build_spi.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "pipelines"))
from aeo.spi import spi as spi_index  # noqa: E402

VERSION = "1.0.0"
PRECIP = ROOT / "public/data/aeo/products/precipitation/v1.0.0"
OUT = ROOT / f"public/data/aeo/products/spi/v{VERSION}"
SITE = f"/data/aeo/products/spi/v{VERSION}"
SCALES = [1, 3, 6, 12]
REF = (1991, 2020)
ARID_MM = 100
BREAKS = [-2, -1.5, -1, 1, 1.5, 2]
COLORS = ["#b2182b", "#ef8a62", "#fddbc7", "#f7f7f7", "#d1e5f0", "#67a9cf", "#2166ac"]
LABELS = ["extremely dry (≤ −2)", "severely dry (−2 to −1.5)", "moderately dry (−1.5 to −1)", "near normal (−1 to 1)", "moderately wet (1 to 1.5)", "very wet (1.5 to 2)", "extremely wet (≥ 2)"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    pm = json.loads((PRECIP / "manifest.json").read_text(encoding="utf-8"))
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "web" / "admin2").mkdir(parents=True, exist_ok=True)
    (OUT / "map").mkdir(parents=True, exist_ok=True)
    assets, qc, inputs = [], [], {}
    for level in ["admin0", "admin1", "admin2"]:
        src = PRECIP / "tables" / f"aeo_precip_monthly_{level}_v1.0.0.parquet"
        inputs[level] = {"file": src.name, "sha256": sha256(src)}
        t = pd.read_parquet(src).sort_values(["unit_code", "year", "month"])
        normals = pd.read_parquet(PRECIP / "tables" / f"aeo_precip_annual_{level}_v1.0.0.parquet").groupby("unit_code")["normal_1991_2020_mm"].first()
        rows, web_units, web = [], [], {str(k): [] for k in SCALES}
        months = None
        stats = []
        for code, g in t.groupby("unit_code", sort=True):
            p = g.precip_mm.to_numpy(float)
            mon = g.month.to_numpy(int)
            ref = ((g.year >= REF[0]) & (g.year <= REF[1])).to_numpy()
            lab = [f"{y}-{m:02d}" for y, m in zip(g.year, g.month)]
            if months is None:
                months = lab
            assert lab == months, code
            out = {k: np.round(spi_index(p, mon, k, ref), 3) for k in SCALES}
            arid = bool(normals.get(code, np.nan) < ARID_MM)
            z3 = out[3][ref & ~np.isnan(out[3])]
            if not arid and z3.size > 200:
                stats.append((z3.mean(), z3.std()))
            gg = g.copy()
            for k in SCALES:
                gg[f"spi_{k}"] = out[k]
                web[str(k)].append([None if np.isnan(v) else round(float(v), 2) for v in out[k]])
            gg["arid"] = arid
            rows.append(gg[["level", "unit_code", "unit_name", "parent_code", "year", "month", "precip_mm", *[f"spi_{k}" for k in SCALES], "arid"]])
            web_units.append({"code": code, "name": g.unit_name.iloc[0], "parent": g.parent_code.iloc[0], "arid": arid})
        df = pd.concat(rows, ignore_index=True)
        m = np.array(stats)
        qc.append(f"{level}: SPI-3 over 1991–2020 in non-arid units has mean {m[:, 0].mean():+.3f} (max |mean| {np.abs(m[:, 0]).max():.3f}) and standard deviation {m[:, 1].mean():.3f} (range {m[:, 1].min():.3f}–{m[:, 1].max():.3f})")
        assert np.abs(m[:, 0]).max() < 0.15 and 0.85 < m[:, 1].min() and m[:, 1].max() < 1.15, (level, m.min(0), m.max(0))
        cov = df[~df.arid & (df.year >= 1982)]["spi_3"].notna().mean()
        qc.append(f"{level}: SPI-3 computed for {100 * cov:.1f} % of non-arid unit-months from 1982; arid units flagged: {int(sum(u['arid'] for u in web_units))} of {len(web_units)}")
        for fmt in (["csv", "parquet"] if level != "admin2" else ["parquet"]):
            p = OUT / "tables" / f"aeo_spi_monthly_{level}_v{VERSION}.{fmt}"
            (df.to_csv(p, index=False, lineterminator="\n") if fmt == "csv" else df.to_parquet(p, index=False, compression="snappy"))
            assets.append({"href": f"{SITE}/tables/{p.name}", "format": fmt.upper(), "level": level, "role": "statistics",
                           "title": f"Monthly SPI-1/3/6/12, {level}", "bytes": p.stat().st_size, "sha256": sha256(p)})
        # summary: latest values and drought frequency over the last 10 complete years
        last = df[df.year * 100 + df.month == df.year.max() * 100 + df[df.year == df.year.max()].month.max()]
        last10 = df[(df.year >= df.year.max() - 10) & (df.year < df.year.max())]
        summ = last[["level", "unit_code", "unit_name", "parent_code", "arid", "year", "month", "spi_3", "spi_12"]].rename(columns={"spi_3": "latest_spi_3", "spi_12": "latest_spi_12"})
        freq = last10.groupby("unit_code")["spi_12"].apply(lambda s: round(100 * (s <= -1).sum() / max(1, s.notna().sum()), 1)).rename(f"pct_months_spi12_le_-1_{df.year.max() - 10}_{df.year.max() - 1}")
        summ = summ.merge(freq, left_on="unit_code", right_index=True)
        p = OUT / "tables" / f"aeo_spi_summary_{level}_v{VERSION}.csv"
        summ.to_csv(p, index=False, lineterminator="\n")
        assets.append({"href": f"{SITE}/tables/{p.name}", "format": "CSV", "level": level, "role": "summary", "title": f"SPI summary (latest month, drought frequency), {level}", "bytes": p.stat().st_size, "sha256": sha256(p)})
        body = {"product": "aeo-dza-spi-chirps3", "version": VERSION, "level": level, "months": months, "reference": f"{REF[0]}-{REF[1]}", "units": web_units, "spi": web}
        if level == "admin2":
            for w in sorted({u["parent"] for u in web_units}):
                idx = [i for i, u in enumerate(web_units) if u["parent"] == w]
                sub = {**body, "units": [web_units[i] for i in idx], "spi": {k: [v[i] for i in idx] for k, v in web.items()}}
                (OUT / "web" / "admin2" / f"{w}.json").write_text(json.dumps(sub, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        else:
            (OUT / "web" / f"{level}.json").write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "map" / "map.json").write_text(json.dumps({"kind": "choropleth by wilaya", "breaks": BREAKS, "colors": COLORS, "labels": LABELS,
        "arid": {"color": "#e8dcc4", "label": f"arid wilaya (normal < {ARID_MM} mm/year): SPI unstable"}}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    now = dt.date.today().isoformat()
    manifest = {
        "product_id": "aeo-dza-spi-chirps3", "title": "Algeria Standardized Precipitation Index (SPI-1, 3, 6, 12) from CHIRPS v3.0: national, wilaya and commune",
        "status": "available", "version": VERSION, "geographic_scope": "Algeria",
        "available_levels": ["admin0", "admin1", "admin2"], "spatial_products_levels": [],
        "boundary_version": pm["boundary_version"],
        "source_product": "AEO Algeria precipitation v1.0.0 (CHIRPS v3.0 final, monthly; Climate Hazards Center, UC Santa Barbara)",
        "source_version": "CHIRPS v3.0", "source_doi": pm["source_doi"], "source_license": pm["source_license"], "license": "CC BY 4.0",
        "temporal_coverage": {"monthly": [months[0], months[-1]]}, "reference_period": list(REF),
        "spatial_resolution": "Administrative units (computed on unit-mean monthly precipitation from 0.05° CHIRPS cells)",
        "crs": "not applicable (tables by administrative unit; boundaries EPSG:4326)", "units": "SPI (dimensionless, standard normal)",
        "scales": SCALES, "formats": ["CSV", "PARQUET"], "processing_code": "scripts/pipelines/spi/build_spi.py", "methodology_url": "/docs/method-spi/",
        "created": now, "download_assets": assets,
        "web_assets": {"admin0": f"{SITE}/web/admin0.json", "admin1": f"{SITE}/web/admin1.json", "admin2": f"{SITE}/web/admin2/{{wilaya_code}}.json", "map": f"{SITE}/map/map.json"},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (OUT / "PROVENANCE.json").write_text(json.dumps({"product": "aeo-dza-spi-chirps3", "version": VERSION, "created": now, "inputs": inputs,
        "method": "gamma (unbiased PWM, Hosking PELGAM), mixed distribution for zero accumulations H = q + (1-q)G, per calendar month, reference 1991-2020, clip ±3.09; not computed where fewer than 10 of the 30 reference accumulations are positive",
        "validation": "tests/python/test_spi.py compares with R SPEI 1.8.1 spi() (Gamma, ub-pwm) on six wilaya series; agreement within 1e-6 where the reference sample has no zeros",
        "qc": qc}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n".join(qc))


if __name__ == "__main__":
    main()
