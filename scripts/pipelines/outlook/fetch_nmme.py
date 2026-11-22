"""Fetch NMME seasonal precipitation hindcasts and forecasts (multi-model ensemble mean) from NOAA CPC.

Source: https://ftp.cpc.ncep.noaa.gov/International/nmme/ (open, no login). Files are in the
CPT (IRI Climate Predictability Tool) text format, 1° global grid, 3-month mean precipitation
(mm/day) of the NMME multi-model ensemble mean:
  seasonal_nmme_hindcast_in_cpt_format/nmme_precip_hcst_<Mon>ic_<m1>-<m3>_<years>.txt   (1991–2020/21)
  seasonal_nmme_forecast_in_cpt_format/nmme_precip_fcst_<Mon>ic_<m1>-<m3>_<years>.txt   (latest issue)

Output: data-work/nmme/{hcst,fcst}/*.txt and data-work/nmme/files.json (URL, bytes, sha256)
Usage:  python scripts/pipelines/outlook/fetch_nmme.py
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data-work" / "nmme"
BASE = "https://ftp.cpc.ncep.noaa.gov/International/nmme/"
DIRS = {"hcst": "seasonal_nmme_hindcast_in_cpt_format/", "fcst": "seasonal_nmme_forecast_in_cpt_format/"}
UA = {"User-Agent": "aeo-pipeline"}


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read()


def main() -> None:
    files = {}
    for kind, d in DIRS.items():
        (OUT / kind).mkdir(parents=True, exist_ok=True)
        listing = get(BASE + d).decode("utf-8", "ignore")
        names = sorted(set(re.findall(rf'href="(nmme_precip_{kind}_[A-Za-z]+ic_\d+-\d+_\d+-\d+\.txt)"', listing)))
        print(kind, len(names), flush=True)
        for n in names:
            dst = OUT / kind / n
            if not dst.exists():
                dst.write_bytes(get(BASE + d + n))
            b = dst.read_bytes()
            files[f"{kind}/{n}"] = {"url": BASE + d + n, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
    (OUT / "files.json").write_text(json.dumps(files, indent=1), encoding="utf-8")
    print("total", len(files))


if __name__ == "__main__":
    main()
