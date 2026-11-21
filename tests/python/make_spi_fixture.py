"""Write the SPI reference fixture: six wilaya precipitation series -> R SPEI::spi().

Run once (needs R with the SPEI and jsonlite packages):
  python tests/python/make_spi_fixture.py [path/to/Rscript]
"""
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures"
UNITS = ["16", "19", "31", "17", "47", "01"]  # Alger, Sétif, Oran, Djelfa, Ghardaïa, Adrar (wet to hyper-arid)

t = pd.read_parquet(ROOT / "public/data/aeo/products/precipitation/v1.0.0/tables/aeo_precip_monthly_admin1_v1.0.0.parquet")
t = t[t.unit_code.isin(UNITS) & (t.year <= 2025)].sort_values(["unit_code", "year", "month"])
t[["unit_code", "year", "month", "precip_mm"]].rename(columns={"unit_code": "unit"}).to_csv(FIX / "spi_input.csv", index=False)
rscript = sys.argv[1] if len(sys.argv) > 1 else "Rscript"
subprocess.run([rscript, str(FIX / "make_spi_fixture.R"), str(FIX)], check=True)
import json
r = pd.read_csv(FIX / "spi_r_output.csv", dtype={"unit": str})
first = t.iloc[0]
cases = [{"unit": u, "scale": int(k), "values": [None if pd.isna(v) else float(v) for v in g.sort_values("i")["value"]]} for (u, k), g in r.groupby(["unit", "scale"])]
(FIX / "spi_r_cases.json").write_text(json.dumps({"reference": (FIX / "spi_r_version.txt").read_text().strip(), "start": [int(first.year), int(first.month)], "cases": cases}) + "\n")
for f in ["spi_r_output.csv", "spi_r_version.txt"]:
    (FIX / f).unlink()
print("wrote", FIX / "spi_r_cases.json")
