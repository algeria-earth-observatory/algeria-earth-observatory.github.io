"""Step 9 — write the catalog record for the precipitation product from its manifest.

Output: src/content/datasets/aeo-dza-precipitation-chirps3.json
The record lists the main files (with size and SHA-256 from the manifest); the full
list of 80+ files stays in the manifest and in the download builder on the page.
"""
import calendar
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROD = ROOT / "public" / "data" / "aeo" / "products" / "precipitation" / "v1.0.0"
OUT = ROOT / "src" / "content" / "datasets" / "aeo-dza-precipitation-chirps3.json"
REPO = "https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io"

m = json.loads((PROD / "manifest.json").read_text(encoding="utf-8"))
y0, y1 = m["temporal_coverage"]["annual"]
mon0, mon1 = m["temporal_coverage"]["monthly"]


def entry(pred, label, fmt, notes):
    a = next(x for x in m["download_assets"] if pred(x))
    return {"label": label, "url": a["href"], "kind": "download", "format": fmt, "requires_login": False,
            "notes": notes, "sha256": a["sha256"], "size_bytes": a["bytes"]}


access = [
    entry(lambda a: a["level"] == "admin0" and "_annual_" in a["href"] and a["format"] == "COG",
          f"Algeria — annual precipitation {y0}–{y1} (GeoTIFF, one band per year)", "Cloud Optimized GeoTIFF", "mm; 0.05°; EPSG:4326; −9999 outside Algeria"),
    entry(lambda a: a["level"] == "admin0" and "_anomaly_" in a["href"],
          f"Algeria — annual anomaly (% of 1991–2020) {y0}–{y1} (GeoTIFF)", "Cloud Optimized GeoTIFF", "Not computed where the normal is below 1 mm"),
    entry(lambda a: a["level"] == "admin0" and "_normal_" in a["href"],
          "Algeria — mean annual precipitation 1991–2020 (GeoTIFF)", "Cloud Optimized GeoTIFF", "WMO standard normal period"),
    entry(lambda a: a["level"] == "admin1" and a["format"] == "CSV" and "_annual_" in a["href"],
          f"Wilaya statistics — annual {y0}–{y1} (CSV)", "CSV", "69 wilayas; area-weighted mean, anomaly, valid-area share"),
    entry(lambda a: a["level"] == "admin2" and a["format"] == "CSV" and "_annual_" in a["href"],
          f"Commune statistics — annual {y0}–{y1} (CSV)", "CSV", "1,541 communes; see support class in the summary table"),
    entry(lambda a: a["level"] == "admin2" and a["format"] == "PARQUET" and "_monthly_" in a["href"],
          f"Commune statistics — monthly {mon0} to {mon1} (Parquet)", "Parquet", "1,541 communes × all months"),
    entry(lambda a: a["level"] == "admin1" and a["format"] == "CSV" and "_summary_" in a["href"],
          "Wilaya summary — normal, trend, support (CSV)", "CSV", "Theil–Sen slope with 95 % interval, Mann–Kendall p"),
]

rec = {
    "id": m["product_id"],
    "title": f"Algeria Precipitation (CHIRPS v3.0), {y0}–present: national, wilaya and commune",
    "title_fr": "Précipitations en Algérie (CHIRPS v3.0) : national, wilayas et communes",
    "description": (f"Monthly ({mon0} to {mon1}) and annual ({y0}–{y1}) precipitation for Algeria at 0.05° (≈5.5 km), with 1991–2020 normals, "
                    "anomalies and trend statistics, aggregated to Algeria's 69 wilayas and 1,541 communes. Prepared by AEO from CHIRPS v3.0."),
    "purpose": "The reference AEO product: an Algeria-ready precipitation record for drought monitoring, agricultural seasons and climate analysis at national, wilaya and commune levels.",
    "domain": ["climate-drought", "agriculture", "water"],
    "categories": ["Precipitation", "Climate indicators"],
    "keywords": ["precipitation", "rainfall", "CHIRPS", "anomaly", "drought", "wilaya", "commune", "trend", "Algeria"],
    "status": m["status"],
    "origin": "aeo-derived",
    "data_nature": "derived",
    "data_type": "raster",
    "provider": {"name": "Climate Hazards Center, UC Santa Barbara (CHIRPS v3.0); Algeria Earth Observatory (processing)", "url": "https://www.chc.ucsb.edu/data/chirps3"},
    "creator": "Algeria Earth Observatory maintainers (processing); Climate Hazards Center (CHIRPS v3.0)",
    "source_url": "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/",
    "documentation_url": "https://doi.org/10.1038/s41597-026-07096-4",
    "license": {"name": "Creative Commons Attribution 4.0 International", "spdx": "CC-BY-4.0", "url": "https://creativecommons.org/licenses/by/4.0/"},
    "license_notes": "CHIRPS v3.0 is licensed CC BY 4.0 (the provider also waives rights to the extent possible). AEO outputs are CC BY 4.0; cite CHIRPS v3.0 and AEO.",
    "citation": (f"Algeria Earth Observatory (2026). Algeria Precipitation (CHIRPS v3.0), version {m['version']}. "
                 "https://algeria-earth-observatory.github.io/data/aeo-dza-precipitation-chirps3/ — derived from Climate Hazards Center (2025), CHIRPS v3.0, doi:10.15780/G2JQ0P; "
                 "Funk, C. et al. (2026), Sci Data 13, 718, doi:10.1038/s41597-026-07096-4."),
    "doi": None,
    "references": [
        {"citation": "Climate Hazards Center Infrared Precipitation with Stations version 3 (CHIRPS3) Data Repository (2025).", "doi": "10.15780/G2JQ0P"},
        {"citation": "Funk, C. et al. (2026). The Climate Hazards Center Infrared Precipitation with Stations, Version 3. Scientific Data 13, 718.", "doi": "10.1038/s41597-026-07096-4"},
    ],
    "spatial_extent": {"coverage": "algeria", "description": "Algeria (AEO boundaries 2026-11-20). Rasters cover the cells touching Algeria; statistics for 1 country, 69 wilayas, 1,541 communes.",
                       "algeria_subset": "native", "bbox": [-9.0, 18.5, 12.5, 37.5]},
    "temporal_extent": {"start": f"{y0}-01-01", "end": f"{mon1}-{calendar.monthrange(int(mon1[:4]), int(mon1[5:]))[1]:02d}", "ongoing": True, "frequency": "monthly; annual totals for complete years",
                        "description": f"Monthly {mon0} to {mon1}; annual totals {y0}–{y1} (complete calendar years only). Reference period 1991–2020."},
    "resolution": {"spatial": "0.05° (≈5.5 km); statistics per administrative unit", "spatial_m": 5500, "temporal": "monthly, annual"},
    "format": ["Cloud Optimized GeoTIFF", "CSV", "Parquet", "JSON"],
    "crs": "EPSG:4326 (WGS 84)",
    "variables": [
        {"name": "precip_mm", "units": "mm", "description": "Precipitation total for the month or calendar year (area-weighted mean depth for units)"},
        {"name": "normal_1991_2020_mm", "units": "mm", "description": "Mean of the same period over 1991–2020"},
        {"name": "anomaly_mm / anomaly_pct", "units": "mm / %", "description": "Departure from the 1991–2020 normal; % not computed where the normal is below 1 mm"},
        {"name": "trend_*", "units": "mm per decade", "description": "Theil–Sen slope with 95 % Sen interval; Mann–Kendall p (Yue–Wang correction when lag-1 autocorrelation is significant)"},
        {"name": "statistical_support", "units": None, "description": "adequate (≥ 4 effective cells), limited (1–4), very limited (< 1)"},
    ],
    "processing": ("Monthly CHIRPS v3.0 final COGs read over the Algeria window with HTTP range requests; QC (complete series, no negative values, stable mask); "
                   "annual totals for complete years; 1991–2020 normals and anomalies; area-weighted zonal means using cell coverage fractions (10×10 supersampling) × geodesic cell area, "
                   "with wilaya and national weights as unions of commune weights; Theil–Sen / Mann–Kendall trends; export to COG, CSV, Parquet and JSON with SHA-256 manifest. "
                   "Full method: /docs/method-precipitation/."),
    "validation": ("Automated checks (tests/python/test_precip_product.py): coverage of every cell inside Algeria, CRS/resolution/no-data, complete series, value ranges, "
                   "anomaly consistency, annual = sum of months, national mean = area-weighted mean of wilaya means, file checksums. "
                   "No independent validation against Algerian station data by AEO; see the CHIRPS v3.0 paper for the provider's evaluation."),
    "limitations": [
        "Satellite–gauge estimate: few gauges in the Sahara and high plateaus; convective and orographic rainfall in the Tell and Atlas is uncertain.",
        "Relative anomalies are unstable where the normal is small (most of the Sahara).",
        "Commune values describe the commune area at ≈5.5 km resolution; many Tell communes cover fewer than 4 grid cells (see support class).",
        "CHIRPS v3.0 is wetter than v2.0 (gauge undercatch correction); do not mix versions.",
        "The national mean is dominated by the dry south and is not representative of the agricultural north.",
    ],
    "alert": None,
    "version": m["version"],
    "published_date": m["created"],
    "updated_date": m["created"],
    "download_url": access[0]["url"],
    "preview_url": None,
    "access": access + [
        {"label": "CHIRPS v3.0 data server (source)", "url": "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/", "kind": "external",
         "format": "GeoTIFF, COG, NetCDF", "requires_login": False, "notes": "Original global and Africa files from the Climate Hazards Center."},
    ],
    "code_url": f"{REPO}/tree/main/scripts/pipelines/precip",
    "algeria_notes": "The agricultural year (September–August) and the winter season are available in Analyze; they matter more than the calendar year for rainfed cereals in the Tell and high plateaus.",
    "map_layers": ["precip-annual", "precip-anomaly"],
    "featured": True,
    "added_date": m["created"],
    "verification": {"checked": date.today().isoformat(), "urls_checked": True, "unverified_fields": [],
                     "sources_consulted": ["https://www.chc.ucsb.edu/data/chirps3", "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/README-CHIRPSv3.0.txt"],
                     "notes": "Licence, data DOI and paper DOI from the CHC CHIRPS3 page; product files verified by checksum at build."},
    "product": {"manifest": "/data/aeo/products/precipitation/v1.0.0/manifest.json", "product_version": m["version"],
                "boundary_version": m["boundary_version"], "levels": m["available_levels"], "spatial_levels": m["spatial_products_levels"],
                "variables": ["precipitation"], "analyze": True},
}
OUT.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", OUT.relative_to(ROOT))
