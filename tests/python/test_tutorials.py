"""The Learn-with-AEO tutorials must run and reproduce the published products."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "public"
sys.path.insert(0, str(ROOT / "scripts" / "tutorials"))


@pytest.mark.skipif(not (PUBLIC / "data/aeo/products/spi/v1.0.0/manifest.json").exists(), reason="SPI product not built")
@pytest.mark.parametrize("code", ["19", "16", "31"])
def test_spi_tutorial_reproduces_product(code):
    import spi_wilaya
    df = spi_wilaya.main(code, PUBLIC)
    ok = df.spi_3.notna()
    assert ok.sum() > 500
    assert (df.spi_3_tutorial[ok] - df.spi_3[ok]).abs().max() < 1e-3  # product values are rounded to 0.001


def _rscript():
    for c in [os.environ.get("RSCRIPT"), shutil.which("Rscript"), *sorted(Path("C:/Program Files/R").glob("R-*/bin/Rscript.exe"), reverse=True)]:
        if c and Path(c).exists():
            ok = subprocess.run([str(c), "-e", "cat(requireNamespace('SPEI', quietly=TRUE))"], capture_output=True, text=True)
            if ok.stdout.strip() == "TRUE":
                return str(c)
    return None


@pytest.mark.skipif(_rscript() is None, reason="R with the SPEI package is not available")
def test_spei_r_tutorial_reproduces_product():
    out = subprocess.run([_rscript(), str(ROOT / "scripts/tutorials/spei_wilaya.R"), "19", str(PUBLIC)], capture_output=True, text=True, check=True).stdout
    diff = float(out.split("largest difference from the AEO product: ")[1].split()[0])
    assert diff < 0.01, out  # the published water balance is rounded to 0.1 mm


@pytest.mark.skipif(os.environ.get("AEO_NETWORK_TESTS") != "1", reason="needs network access to files.isric.org (set AEO_NETWORK_TESTS=1)")
def test_soil_tutorial_matches_product():
    import soil_wilaya
    r = soil_wilaya.main("19", PUBLIC)
    assert r["pixels"] > 5000
    assert abs(r["mean"] - r["aeo"]) < 0.05  # g/kg; edge pixels only
