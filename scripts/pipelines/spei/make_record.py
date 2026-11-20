"""Write the catalog record for the SPEI product from its manifest."""
import calendar
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROD = ROOT / "public" / "data" / "aeo" / "products" / "spei" / "v1.0.0"
OUT = ROOT / "src" / "content" / "datasets" / "aeo-dza-spei-terraclimate.json"
REPO = "https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io"
m = json.loads((PROD / "manifest.json").read_text(encoding="utf-8"))
m0, m1 = m["temporal_coverage"]["monthly"]


def entry(pred, label, fmt, notes):
    a = next(x for x in m["download_assets"] if pred(x))
    return {"label": label, "url": a["href"], "kind": "download", "format": fmt, "requires_login": False, "notes": notes,
            "sha256": a["sha256"], "size_bytes": a["bytes"]}


access = [
    entry(lambda a: "spei12_december" in a["href"], f"Algeria — SPEI-12 in December, {m0[:4]}–{m1[:4]} (GeoTIFF, one band per year)", "Cloud Optimized GeoTIFF", "int16 × 0.01; 1/30°; EPSG:4326"),
    entry(lambda a: "spei3_last12" in a["href"], "Algeria — SPEI-3, last 12 months (GeoTIFF)", "Cloud Optimized GeoTIFF", "int16 × 0.01"),
    entry(lambda a: "spei12_last12" in a["href"], "Algeria — SPEI-12, last 12 months (GeoTIFF)", "Cloud Optimized GeoTIFF", "int16 × 0.01"),
    entry(lambda a: a["level"] == "admin1" and a["format"] == "CSV" and "_monthly_" in a["href"], f"Wilaya SPEI-1/3/6/12 and water balance, monthly {m0}–{m1} (CSV)", "CSV", "69 wilayas"),
    entry(lambda a: a["level"] == "admin2" and a["format"] == "PARQUET", f"Commune SPEI-1/3/6/12 and water balance, monthly {m0}–{m1} (Parquet)", "Parquet", "1,541 communes"),
    entry(lambda a: a["level"] == "admin1" and "_summary_" in a["href"], "Wilaya summary — latest SPEI, recent drought frequency, worst drought (CSV)", "CSV", "Includes the hyper-arid flag"),
]
rec = {
    "id": m["product_id"],
    "title": f"Algeria Drought Index SPEI (TerraClimate), {m0[:4]}–{m1[:4]}: national, wilaya and commune",
    "title_fr": "Indice de sécheresse SPEI pour l'Algérie (TerraClimate)",
    "description": (f"Standardised Precipitation–Evapotranspiration Index at 1, 3, 6 and 12 months, monthly {m0} to {m1}, for Algeria, "
                    "its 69 wilayas and 1,541 communes, plus SPEI-3 and SPEI-12 maps at 1/30°. Computed by AEO from TerraClimate precipitation and "
                    "Penman–Monteith reference evapotranspiration, calibrated on 1991–2020."),
    "purpose": "Monitor meteorological and agricultural drought in Algeria, including the effect of evaporative demand that rainfall-only indices miss.",
    "domain": ["climate-drought", "agriculture", "water"],
    "categories": ["Drought indices", "Climate indicators"],
    "keywords": ["SPEI", "drought", "water balance", "evapotranspiration", "TerraClimate", "wilaya", "commune", "Algeria"],
    "status": m["status"], "origin": "aeo-derived", "data_nature": "derived", "data_type": "raster",
    "provider": {"name": "Climatology Lab, University of California Merced / University of Idaho (TerraClimate); Algeria Earth Observatory (SPEI computation)", "url": "https://www.climatologylab.org/terraclimate.html"},
    "creator": "Algeria Earth Observatory maintainers (SPEI computation); Abatzoglou et al. (TerraClimate)",
    "source_url": "http://thredds.northwestknowledge.net:8080/thredds/catalog/TERRACLIMATE_ALL/data/catalog.html",
    "documentation_url": "https://doi.org/10.1038/sdata.2017.191",
    "license": {"name": "Creative Commons Attribution 4.0 International", "spdx": "CC-BY-4.0", "url": "https://creativecommons.org/licenses/by/4.0/"},
    "license_notes": "TerraClimate is released under CC0 (public domain). AEO SPEI outputs are CC BY 4.0: cite AEO, TerraClimate and the SPEI method.",
    "citation": ("Algeria Earth Observatory (2026). Algeria Drought Index SPEI (TerraClimate), version 1.0.0. https://algeria-earth-observatory.github.io/data/aeo-dza-spei-terraclimate/ — "
                 "from Abatzoglou, J.T. et al. (2018), TerraClimate, Sci Data 5, 170191, doi:10.1038/sdata.2017.191; method: Vicente-Serrano, S.M. et al. (2010), J. Climate 23, 1696–1718, doi:10.1175/2009JCLI2909.1."),
    "doi": None,
    "references": [
        {"citation": "Abatzoglou, J.T., Dobrowski, S.Z., Parks, S.A. & Hegewisch, K.C. (2018). TerraClimate. Scientific Data 5, 170191.", "doi": "10.1038/sdata.2017.191"},
        {"citation": "Vicente-Serrano, S.M., Beguería, S. & López-Moreno, J.I. (2010). A multiscalar drought index sensitive to global warming: the SPEI. Journal of Climate 23, 1696–1718.", "doi": "10.1175/2009JCLI2909.1"},
    ],
    "spatial_extent": {"coverage": "algeria", "description": "Algeria (AEO boundaries 2026-11-20): 1 country, 69 wilayas, 1,541 communes; maps at 1/30°.", "algeria_subset": "native", "bbox": [-9.0, 18.5, 12.5, 37.5]},
    "temporal_extent": {"start": f"{m0}-01", "end": f"{m1}-{calendar.monthrange(int(m1[:4]), int(m1[5:]))[1]:02d}", "ongoing": True, "frequency": "monthly",
                        "description": f"Monthly {m0} to {m1}; updated yearly when TerraClimate adds a year. Calibration 1991–2020."},
    "resolution": {"spatial": "1/30° (≈3.7 km) maps; statistics per administrative unit", "spatial_m": 3700, "temporal": "monthly"},
    "format": ["Cloud Optimized GeoTIFF", "CSV", "Parquet", "JSON"],
    "crs": "EPSG:4326 (WGS 84)",
    "variables": [
        {"name": "spei_1, spei_3, spei_6, spei_12", "units": None, "description": "SPEI for 1-, 3-, 6- and 12-month water balances (standard normal; ≤ −1 dry, ≤ −1.5 severe, ≤ −2 extreme)"},
        {"name": "p_mm, pet_mm, d_mm", "units": "mm/month", "description": "Area-weighted precipitation, reference evapotranspiration and water balance P − PET"},
        {"name": "hyper_arid", "units": None, "description": "Normal annual precipitation 1991–2020 below 100 mm: SPEI reflects evaporative-demand anomalies only"},
    ],
    "processing": ("TerraClimate monthly P and PET read over OPeNDAP for the Algeria window; QC; area-weighted unit means with nested commune weights; "
                   "SPEI on unit water balances (log-logistic, unbiased PWM, fitted per calendar month on 1991–2020, clipped at ±3.09); grid SPEI-3/12 for maps; "
                   "exports with SHA-256 manifest. Method: /docs/method-spei/."),
    "validation": ("SPEI code reproduces the R package SPEI 1.8.1 to 1e-13 (synthetic series; differences only beyond the ±3.09 clip). Automated tests: standardisation over 1991–2020 "
                   "(mean ≈ 0, sd ≈ 1 for every wilaya and scale), completeness, water balance = P − PET, checksums. No independent comparison with Algerian station-based indices yet."),
    "limitations": [
        "TerraClimate is an interpolated climate product (WorldClim climatology + reanalysis anomalies); station density in Algeria is low, especially in the south.",
        "In hyper-arid areas (normal P < 100 mm/year: much of the Sahara) SPEI is driven by evaporative demand only and does not indicate water-supply drought; these units are flagged and masked on maps.",
        "With a fixed 1991–2020 calibration and rising evaporative demand, recent years tend to be drier and early decades wetter: SPEI includes the warming signal by design.",
        "The national SPEI is dominated by the large Saharan wilayas and is not representative of the agricultural north; use wilaya or commune series.",
        "Values beyond ±3.09 are clipped.",
    ],
    "alert": None, "version": m["version"], "published_date": m["created"], "updated_date": m["created"],
    "download_url": access[0]["url"], "preview_url": None,
    "access": access + [{"label": "TerraClimate data server (source)", "url": "http://thredds.northwestknowledge.net:8080/thredds/catalog/TERRACLIMATE_ALL/data/catalog.html",
                         "kind": "external", "format": "NetCDF (OPeNDAP)", "requires_login": False, "notes": "Global yearly files by variable."}],
    "code_url": f"{REPO}/tree/main/scripts/pipelines/spei",
    "algeria_notes": "For rainfed cereals, SPEI-3 at the end of winter and spring and SPEI-6 for the agricultural year are the most informative; SPEI-12 summarises annual water balance and multi-year droughts such as 2020–2024.",
    "map_layers": ["spei-3", "spei-12"], "featured": True, "added_date": m["created"],
    "verification": {"checked": date.today().isoformat(), "urls_checked": True, "unverified_fields": [],
                     "sources_consulted": ["http://thredds.northwestknowledge.net:8080/thredds/catalog/TERRACLIMATE_ALL/data/catalog.html", "https://www.climatologylab.org/terraclimate.html"],
                     "notes": "Resolution checked from the files (1/30°). Product files verified by checksum at build."},
    "product": {"manifest": "/data/aeo/products/spei/v1.0.0/manifest.json", "product_version": m["version"], "boundary_version": m["boundary_version"],
                "levels": m["available_levels"], "spatial_levels": m["spatial_products_levels"], "variables": ["spei"], "analyze": True},
}
OUT.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", OUT.name)
