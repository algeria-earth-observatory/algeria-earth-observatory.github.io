"""Write the catalog records of the AEO water, cropland and climate products from their manifests.

Descriptive text is maintained here; access entries (URL, size, SHA-256) come from each product's
manifest so that the record and the published files cannot disagree.

Usage: python scripts/catalog/aeo_product_records.py [product ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/algeria-earth-observatory/algeria-earth-observatory.github.io/tree/main/scripts/pipelines"
CCBY = {"name": "Creative Commons Attribution 4.0 International", "spdx": "CC-BY-4.0", "url": "https://creativecommons.org/licenses/by/4.0/"}
AEO = "Algeria Earth Observatory maintainers"


def manifest(path: str) -> dict:
    return json.loads((ROOT / "public" / path.lstrip("/")).read_text(encoding="utf-8"))


def access(m: dict, labels: dict[str, str], extra: list[dict] = ()) -> list[dict]:
    out = []
    for a in m["download_assets"]:
        name = a["href"].split("/")[-1]
        if name not in labels:
            continue
        out.append({"label": labels[name], "url": a["href"], "kind": "download", "format": a["format"].upper() if a["format"] != "PARQUET" else "Parquet",
                    "requires_login": False, "size_bytes": a["bytes"], "sha256": a["sha256"], "notes": None})
    missing = set(labels) - {a["url"].split("/")[-1] for a in out}
    assert not missing, missing
    return out + list(extra)


def base(m: dict, mpath: str, **kw) -> dict:
    rec = {
        "status": m["status"], "origin": "aeo-derived", "data_type": "tabular", "license": CCBY,
        "doi": None, "version": m["version"], "published_date": m["created"], "updated_date": m["created"],
        "featured": False, "added_date": m["created"],
        "product": {"manifest": mpath, "product_version": m["version"], "boundary_version": m["boundary_version"],
                    "levels": m["available_levels"], "spatial_levels": [], "variables": kw.pop("pvars"), "analyze": False},
    }
    rec.update(kw)
    rec["download_url"] = rec["access"][0]["url"]
    return rec


def write(rec: dict) -> None:
    order = ["id", "title", "title_fr", "title_ar", "description", "purpose", "domain", "categories", "keywords", "status", "origin",
             "data_nature", "data_type", "provider", "creator", "source_url", "documentation_url", "license", "license_notes", "citation", "doi",
             "references", "spatial_extent", "temporal_extent", "resolution", "format", "crs", "variables", "processing", "validation",
             "limitations", "algeria_notes", "version", "published_date", "updated_date", "download_url", "access", "code_url", "map_layers",
             "featured", "added_date", "verification", "product"]
    out = {k: rec[k] for k in order if k in rec}
    out.update({k: v for k, v in rec.items() if k not in out})
    (ROOT / "src/content/datasets" / f"{rec['id']}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", rec["id"])


DZ = {"coverage": "algeria", "algeria_subset": "native", "bbox": [-8.67, 18.96, 11.99, 37.09]}
GACED_REF = {"citation": "GACED30: Global 30-m Annual Cropland Extent Dynamics (2000–2024), version 1. Zenodo.", "doi": "10.5281/zenodo.18199675"}


def stable_cropland():
    mp = "/data/aeo/products/stable-cropland/v1.0.0/manifest.json"
    m = manifest(mp)
    return base(m, mp, pvars=["stable_cropland_ha"],
        id="aeo-dza-stable-cropland-gaced30",
        title="Algeria stable cropland 2000–2024 (from GACED30): area by commune, wilaya and Algeria",
        title_fr="Terres cultivées stables de l'Algérie 2000–2024 (d'après GACED30) : superficies par commune, wilaya et pour l'Algérie",
        title_ar=None,
        description="Land that the GACED30 30 m annual cropland maps classify as cropland in at least 20 of the 25 years 2000–2024, summarised by AEO as true areas (ha) for Algeria, its 69 wilayas and 1,541 communes, with the full distribution of cropland years. The per-cell stable-cropland area on the grids of the other AEO products is published as the AEO cropland mask.",
        purpose="Restrict drought, evapotranspiration, soil-moisture, water-storage and climate statistics, and the seasonal outlook, to land that is actually and persistently farmed.",
        domain=["agriculture", "land-ecosystems"], categories=["Cropland", "Agricultural statistics", "Masks"],
        keywords=["cropland", "stable cropland", "GACED30", "agriculture", "mask", "fallow", "wilaya", "commune", "Algeria"],
        data_nature="derived",
        provider={"name": "Algeria Earth Observatory (from GACED30 v1)", "url": "https://doi.org/10.5281/zenodo.18199675"},
        creator=f"{AEO}; GACED30 authors (source maps)",
        source_url="https://doi.org/10.5281/zenodo.18199675", documentation_url="https://algeria-earth-observatory.github.io/docs/method-stable-cropland/",
        license_notes="GACED30 is CC BY 4.0. AEO statistics are CC BY 4.0: cite AEO and GACED30.",
        citation="Algeria Earth Observatory (2026). Algeria stable cropland 2000–2024 (from GACED30), version 1.0.0. https://algeria-earth-observatory.github.io/data/aeo-dza-stable-cropland-gaced30/ — from GACED30 v1, doi:10.5281/zenodo.18199675.",
        references=[GACED_REF, {"citation": "GACED30 data descriptor, Earth System Science Data 18, 7071 (2026).", "doi": "10.5194/essd-18-7071-2026"}],
        spatial_extent={**DZ, "description": "Algeria (AEO boundaries 2026-11-20): 1 country, 69 wilayas, 1,541 communes, from 30 m pixels."},
        temporal_extent={"start": "2000-01-01", "end": "2024-12-31", "ongoing": False, "frequency": "single epoch (2000–2024 summary)", "description": "Summary of 25 annual maps, 2000–2024."},
        resolution={"spatial": "Administrative units, from 30 m pixels (true pixel areas)", "spatial_m": 30, "temporal": "2000–2024 summary"},
        format=["CSV", "Parquet", "NPZ"], crs="Areas on the authalic sphere; boundaries EPSG:4326",
        variables=[{"name": "stable_cropland_ha", "units": "ha", "description": "Cropland in at least 20 of 25 years"},
                   {"name": "cropland_any_year_ha", "units": "ha", "description": "Cropland in at least one year"},
                   {"name": "cropland_majority_ha", "units": "ha", "description": "Cropland in at least 13 years"},
                   {"name": "cropland_all_years_ha", "units": "ha", "description": "Cropland in all 25 years"},
                   {"name": "years_<k>_ha", "units": "ha", "description": "Area cropland in exactly k years (commune histogram)"}],
        processing="Count of cropland years per 30 m pixel over the 25 GACED30 maps; true pixel areas summed by commune (pixel centre) and merged into wilayas and Algeria; the same pixels accumulated onto the CHIRPS, WaPOR, CMIP6, GRACE and NMME grids.",
        validation="Areas checked against the boundaries (231.3 Mha mapped vs 231.0 Mha of polygons); national stable cropland 6.40 Mha, cropland in most years 8.35 Mha (close to the commonly cited utilised agricultural area of about 8.5 Mha — a plausibility check, not a validation).",
        limitations=["GACED30 has no published accuracy assessment for Algeria; its authors report confusion between active fallow and bare land in drylands.",
                     "Stable cropland is not the cultivated area of a given year.",
                     "Cropland that appeared after about 2005 has fewer than 20 cropland years and is excluded."],
        algeria_notes="The largest stable-cropland areas are in Tiaret, Oum El Bouaghi, Mascara, Sidi Bel Abbès, Sétif and Tlemcen (about 0.29–0.58 Mha each); in the Sahara stable cropland is limited to oasis strips and irrigated perimeters.",
        access=access(m, {"aeo_stable_cropland_admin1_v1.0.0.csv": "Wilayas — stable cropland area (CSV)",
                          "aeo_stable_cropland_admin2_v1.0.0.csv": "Communes — stable cropland area (CSV)",
                          "aeo_stable_cropland_admin0_v1.0.0.csv": "Algeria — stable cropland area (CSV)",
                          "aeo_cropland_years_histogram_admin2_v1.0.0.csv": "Communes — area by number of cropland years (CSV)",
                          "aeo_stable_cropland_grids_v1.0.0.npz": "Cropland mask on the AEO product grids (NPZ)"}),
        code_url=f"{REPO}/cropland", map_layers=["stable-cropland"],
        verification={"checked": m["created"], "urls_checked": True, "unverified_fields": [], "sources_consulted": ["https://doi.org/10.5281/zenodo.18199675"], "notes": "See PROVENANCE.json."},
    )


def et_sm():
    mp = "/data/aeo/products/et-soil-moisture/v1.0.0/manifest.json"
    m = manifest(mp)
    t = m["temporal_coverage"]["monthly"]
    return base(m, mp, pvars=["aeti_mm", "ret_mm", "rsm_pct"],
        id="aeo-dza-et-soil-moisture-wapor3",
        title="Algeria evapotranspiration and soil moisture (FAO WaPOR v3), monthly: national, wilaya and commune, all land and stable cropland",
        title_fr="Évapotranspiration et humidité du sol de l'Algérie (FAO WaPOR v3), mensuelles : nation, wilayas et communes, toutes terres et terres cultivées stables",
        title_ar=None,
        description=f"Monthly actual evapotranspiration and interception (AETI), reference evapotranspiration (RET) and relative root-zone soil moisture from FAO WaPOR v3 Level 1, averaged by AEO over Algeria, its 69 wilayas and 1,541 communes — over all land and over stable cropland only — from {t[0]} to {t[1]}, with departures from the 2018–2025 mean.",
        purpose="Follow crop and rangeland water use and soil moisture month by month, and see whether this month is unusual on farmland.",
        domain=["water", "climate-drought", "agriculture"], categories=["Evapotranspiration", "Soil moisture", "Agricultural water"],
        keywords=["evapotranspiration", "ET", "AETI", "reference evapotranspiration", "soil moisture", "WaPOR", "FAO", "cropland", "wilaya", "commune", "Algeria"],
        data_nature="modeled",
        provider={"name": "FAO WaPOR v3; Algeria Earth Observatory (regional statistics)", "url": "https://data.apps.fao.org/wapor/"},
        creator=f"{AEO} (regional statistics); FAO WaPOR (source maps)",
        source_url="https://data.apps.fao.org/wapor/", documentation_url="https://algeria-earth-observatory.github.io/docs/method-et-soil-moisture/",
        license_notes="WaPOR data are CC BY 4.0 (FAO). AEO statistics are CC BY 4.0: cite AEO and FAO WaPOR v3.",
        citation="Algeria Earth Observatory (2026). Algeria evapotranspiration and soil moisture (FAO WaPOR v3), version 1.0.0. https://algeria-earth-observatory.github.io/data/aeo-dza-et-soil-moisture-wapor3/ — from FAO (2026), WaPOR v3, https://data.apps.fao.org/wapor/.",
        references=[GACED_REF],
        spatial_extent={**DZ, "description": "Algeria (AEO boundaries 2026-11-20): 1 country, 69 wilayas, 1,541 communes."},
        temporal_extent={"start": f"{t[0]}-01", "end": None, "ongoing": True, "frequency": "monthly", "description": f"Monthly {t[0]} to {t[1]}; updated as FAO publishes new months."},
        resolution={"spatial": "Administrative units (from 300 m WaPOR maps averaged to 1.2 km)", "spatial_m": None, "temporal": "monthly"},
        format=["CSV", "Parquet"], crs="not applicable (tables by administrative unit; boundaries EPSG:4326)",
        variables=[{"name": "aeti_mm", "units": "mm/month", "description": "Actual evapotranspiration and interception"},
                   {"name": "ret_mm", "units": "mm/month", "description": "Reference evapotranspiration (FAO-56)"},
                   {"name": "rsm_pct", "units": "%", "description": "Relative soil moisture (monthly mean of dekads)"},
                   {"name": "*_cropland_*", "units": "as above", "description": "Same variables over stable cropland only"},
                   {"name": "*_departure_*", "units": "% or percentage points", "description": "Departure from the 2018–2025 mean of the calendar month"}],
        processing="WaPOR Level-1 rasters read from FAO's open cloud files at the 1.17 km average overview; dekadal soil moisture averaged by month; area-weighted means by commune merged into wilayas and Algeria; cropland means weighted by stable-cropland area.",
        validation="National mean equals the area-weighted mean of wilayas (checked each build); soil moisture within 0–100 %.",
        limitations=["Modelled from satellite data (WaPOR surface energy balance), not measured.",
                     "Departures use only 8 years (2018–2025) and are not drought classes.",
                     "Relative soil moisture is derived from land surface temperature. In the Sahara, with almost no vegetation, WaPOR relative soil moisture is not meaningful (values come from its surface-temperature method); read it for vegetated land and cropland.",
                     "Recent months can be revised by FAO."],
        algeria_notes="Evapotranspiration is highest in spring over the cropland of the Tell and in irrigated oases; most of the Sahara evaporates almost nothing.",
        access=access(m, {"aeo_et_sm_monthly_admin1_v1.0.0.csv": "Wilayas — monthly ET and soil moisture (CSV)",
                          "aeo_et_sm_monthly_admin0_v1.0.0.csv": "Algeria — monthly ET and soil moisture (CSV)",
                          "aeo_et_sm_monthly_admin2_v1.0.0.parquet": "Communes — monthly ET and soil moisture (Parquet)"}),
        code_url=f"{REPO}/wapor", map_layers=["et-aeti", "sm-rsm"],
        verification={"checked": m["created"], "urls_checked": True, "unverified_fields": [], "sources_consulted": ["https://data.apps.fao.org/gismgr/api/v2/catalog/workspaces/WAPOR-3/mapsets"], "notes": "The WaPOR catalogue lists soil moisture in % with scale 0.001, but scaled values are fractions; AEO converts them to %. See PROVENANCE.json."},
    )


def water_storage():
    mp = "/data/aeo/products/water-storage/v1.0.0/manifest.json"
    m = manifest(mp)
    t = m["temporal_coverage"]["monthly"]
    return base(m, mp, pvars=["tws_anomaly_cm"],
        id="aeo-dza-water-storage-grace",
        title="Algeria terrestrial water storage anomaly (downscaled GRACE/GRACE-FO): national and wilaya, 2002–2025",
        title_fr="Anomalie du stock d'eau terrestre de l'Algérie (GRACE/GRACE-FO désagrégé) : nation et wilayas, 2002–2025",
        title_ar=None,
        description=f"Monthly change in total water stored on and below the land surface, in cm of water relative to 2004–2009, averaged by AEO over Algeria and its 69 wilayas from the 0.25° downscaled GRACE/GRACE-FO dataset of Li & Kusche (2026), {t[0]} to {t[1]}, with uncertainty and Theil–Sen trends.",
        purpose="Show long-term gains and losses of water storage, including the decline of Algeria's large aquifer systems, at the scales GRACE can support.",
        domain=["water", "climate-drought"], categories=["Terrestrial water storage", "Groundwater (indirect)", "Satellite gravimetry"],
        keywords=["GRACE", "GRACE-FO", "water storage", "TWS", "groundwater", "downscaling", "trend", "wilaya", "Algeria"],
        data_nature="modeled",
        provider={"name": "Li & Kusche (University of Bonn), from NASA JPL mascons; Algeria Earth Observatory (regional statistics)", "url": "https://doi.org/10.5281/zenodo.17265162"},
        creator=f"{AEO} (regional statistics); F. Li and J. Kusche (downscaled dataset)",
        source_url="https://doi.org/10.5281/zenodo.17265162", documentation_url="https://algeria-earth-observatory.github.io/docs/method-water-storage/",
        license_notes="The downscaled dataset is CC BY 4.0 (Zenodo). AEO statistics are CC BY 4.0.",
        citation="Algeria Earth Observatory (2026). Algeria terrestrial water storage anomaly (downscaled GRACE/GRACE-FO), version 1.0.0. — from Li, F. (2025), Zenodo, doi:10.5281/zenodo.17265162, and Li & Kusche (2026), GRL, doi:10.1029/2025GL119881.",
        references=[{"citation": "Li, F. & Kusche, J. (2026). Reproducing GRACE Total Water Storage Change at Finer Spatial Scales. Geophysical Research Letters 53, e2025GL119881.", "doi": "10.1029/2025GL119881"},
                    {"citation": "Li, F. (2025). Global high-resolution (0.25°) total water storage anomaly dataset derived by reproducing GRACE data, v2. Zenodo.", "doi": "10.5281/zenodo.17265162"}],
        spatial_extent={**DZ, "description": "Algeria and its 69 wilayas (AEO boundaries 2026-11-20); communes not published. Tipaza has no value (coastal cells are ocean in the source)."},
        temporal_extent={"start": f"{t[0]}-01", "end": f"{t[1]}-28", "ongoing": False, "frequency": "monthly", "description": f"{t[0]} to {t[1]} with 33 missing months, including the 2017–2018 gap between missions."},
        resolution={"spatial": "Wilayas (0.25° cells; GRACE resolves about 300 km)", "spatial_m": None, "temporal": "monthly"},
        format=["CSV", "Parquet"], crs="not applicable (tables by administrative unit)",
        variables=[{"name": "tws_anomaly_cm", "units": "cm", "description": "Water storage anomaly vs the unit's 2004–2009 mean"},
                   {"name": "uncertainty_cm", "units": "cm", "description": "Unit mean of the downscaling uncertainty"},
                   {"name": "tws_anomaly_cropland_cm", "units": "cm", "description": "Same, weighted by stable-cropland area"},
                   {"name": "trend_cm_per_year", "units": "cm/year", "description": "Theil–Sen trend with Mann–Kendall p-value"}],
        processing="Area-weighted means of the 0.25° cells; re-referenced to 2004–2009; Theil–Sen trend and Mann–Kendall test on the deseasonalised series.",
        validation="Downloaded file checked against the Zenodo MD5; national trend −0.25 cm/yr (95 % −0.26 to −0.23), Mann–Kendall p < 0.0001.",
        limitations=["Total storage, not groundwater.", "GRACE resolves about 300 km: only 9 wilayas are at least one mascon in area; values of the others are mostly model detail.",
                     "Missing months are left empty.", "The source ends in March 2025."],
        algeria_notes="Storage declines over most of the country; the strongest declines are in the north-east (about −1.2 cm/year), where the value rests largely on the downscaling.",
        access=access(m, {"aeo_tws_monthly_admin1_v1.0.0.csv": "Wilayas — monthly water storage anomaly (CSV)",
                          "aeo_tws_monthly_admin0_v1.0.0.csv": "Algeria — monthly water storage anomaly (CSV)",
                          "aeo_tws_trends_admin0-1_v1.0.0.csv": "Trends by wilaya (CSV)"}),
        code_url=f"{REPO}/grace", map_layers=["tws-grace"],
        verification={"checked": m["created"], "urls_checked": True, "unverified_fields": [], "sources_consulted": ["https://zenodo.org/api/records/17265162", "https://api.crossref.org/works/10.1029/2025gl119881"], "notes": "See PROVENANCE.json."},
    )


def outlook():
    mp = "/data/aeo/products/seasonal-outlook/v0.1.0/manifest.json"
    m = manifest(mp)
    return base(m, mp, pvars=["p_below", "p_normal", "p_above"],
        id="aeo-dza-seasonal-outlook-nmme",
        title="Algeria seasonal rainfall outlook over stable cropland (NMME, verified test, experimental)",
        title_fr="Prévision saisonnière des pluies sur les terres cultivées stables de l'Algérie (NMME, test vérifié, expérimental)",
        title_ar=None,
        description=f"Experimental tercile probabilities of 3-month rainfall over each wilaya's stable cropland, from the NMME multi-model forecast issued {m['temporal_coverage']['issued']}, recalibrated against CHIRPS v3.0 over 1991–2021 and published only where cross-validated hindcasts beat climatology; full verification tables included.",
        purpose="Test whether seasonal forecasts can give usable early warning of dry seasons on Algerian farmland, and show plainly where they cannot.",
        domain=["climate-drought", "agriculture"], categories=["Seasonal forecast", "Drought early warning", "Verification"],
        keywords=["seasonal forecast", "outlook", "NMME", "tercile", "RPSS", "verification", "hindcast", "cropland", "rainfall", "Algeria"],
        data_nature="modeled",
        provider={"name": "Algeria Earth Observatory (calibration and verification); NOAA CPC (NMME forecasts)", "url": "https://www.cpc.ncep.noaa.gov/products/NMME/"},
        creator=f"{AEO}",
        source_url="https://ftp.cpc.ncep.noaa.gov/International/nmme/", documentation_url="https://algeria-earth-observatory.github.io/docs/method-seasonal-outlook/",
        license_notes="NMME forecasts are distributed openly by NOAA CPC; CHIRPS is CC BY 4.0. AEO outlooks and verification are CC BY 4.0.",
        citation="Algeria Earth Observatory (2026). Algeria seasonal rainfall outlook over stable cropland (NMME, experimental), version 0.1.0. — NMME: Kirtman et al. (2014), BAMS, doi:10.1175/BAMS-D-12-00050.1.",
        references=[{"citation": "Kirtman, B. P. et al. (2014). The North American Multimodel Ensemble: Phase-1 seasonal-to-interannual prediction; Phase-2 toward developing intraseasonal prediction. Bulletin of the American Meteorological Society 95, 585–601.", "doi": "10.1175/BAMS-D-12-00050.1"},
                    {"citation": "Funk, C. et al. (2026). The Climate Hazards Center Infrared Precipitation with Stations, Version 3. Scientific Data.", "doi": "10.1038/s41597-026-07096-4"}],
        spatial_extent={**DZ, "description": "Stable cropland of the wilayas with at least 10,000 ha of it (45 wilayas) and of Algeria as a whole."},
        temporal_extent={"start": "1991-01-01", "end": None, "ongoing": True, "frequency": "monthly issue, 3-month targets", "description": f"Hindcasts 1991–2021; latest issue {m['temporal_coverage']['issued']} (targets up to 6 months ahead)."},
        resolution={"spatial": "Wilayas (stable cropland; NMME 1°)", "spatial_m": None, "temporal": "3-month seasons"},
        format=["CSV", "Parquet"], crs="not applicable",
        variables=[{"name": "p_below / p_normal / p_above", "units": "probability", "description": "Published tercile probabilities (equal chances where not skilful)"},
                   {"name": "rpss, roc_below, r", "units": "-", "description": "Leave-one-year-out verification 1991–2021"},
                   {"name": "skilful", "units": "boolean", "description": "Local skill and field significance (≥ 20 % of wilayas, lead ≤ 3 months)"}],
        processing="Regression of observed CHIRPS seasonal totals on the NMME ensemble mean over stable cropland, leave-one-year-out; Gaussian tercile probabilities; publication gated by RPSS, ROC area, correlation and field significance.",
        validation="3,036 combinations verified (wilaya × start month × lead); 17 % locally skilful against about 5 % expected by chance; skill is concentrated in leads of 1–3 months and in some seasons.",
        limitations=["Experimental test; not an official forecast.", "Seasonal rainfall forecasts for North Africa have low skill; most outlooks are 'equal chances'.",
                     "Calibration on 31 years; skill estimates are uncertain.", "NMME ensemble mean only (no member spread)."],
        algeria_notes="Skill exists mainly for forecasts started in March, May, July, September and November, one to three months ahead, and for the north of the country; forecasts started in October, December and January show almost none.",
        access=access(m, {"aeo_outlook_latest_admin1_v0.1.0.csv": "Latest outlook by wilaya (CSV)",
                          "aeo_outlook_verification_admin1_v0.1.0.csv": "Hindcast verification by wilaya, start month and lead (CSV)"}),
        code_url=f"{REPO}/outlook", map_layers=["outlook-nmme"],
        verification={"checked": m["created"], "urls_checked": True, "unverified_fields": [], "sources_consulted": ["https://ftp.cpc.ncep.noaa.gov/International/nmme/", "https://www.cpc.ncep.noaa.gov/products/NMME/"], "notes": "See PROVENANCE.json for every input file with its SHA-256."},
    )


def projections():
    mp = "/data/aeo/products/climate-projections/v1.0.0/manifest.json"
    m = manifest(mp)
    return base(m, mp, pvars=["tx_mean", "hd35", "hd40", "spring32", "prcptot", "pr_ndjfma", "cdd"],
        id="aeo-dza-climate-projections-nexgddp",
        title="Algeria climate hazard projections (NASA NEX-GDDP-CMIP6, 8 models): national and wilaya, all land and stable cropland",
        title_fr="Projections des aléas climatiques pour l'Algérie (NASA NEX-GDDP-CMIP6, 8 modèles) : nation et wilayas, toutes terres et terres cultivées stables",
        title_ar=None,
        description="Projected changes in heat (mean maximum temperature, days above 35 °C and 40 °C, March–May days above 32 °C), rainfall (annual and November–April) and dry spells for 2041–2070 and 2071–2100 under SSP2-4.5 and SSP5-8.5, relative to 1985–2014, from 8 bias-corrected CMIP6 models (NEX-GDDP-CMIP6, 0.25°), by wilaya and for Algeria, over all land and over stable cropland: model median, range and agreement.",
        purpose="Give planners and researchers wilaya-level climate hazard projections with their uncertainty, including for farmland.",
        domain=["hazards", "climate-drought", "agriculture"], categories=["Climate projections", "Heat", "Drought", "Climate risk"],
        keywords=["CMIP6", "NEX-GDDP", "climate change", "projections", "heat", "extreme heat", "precipitation", "dry spell", "SSP2-4.5", "SSP5-8.5", "wilaya", "Algeria"],
        data_nature="modeled",
        provider={"name": "NASA NEX-GDDP-CMIP6; Algeria Earth Observatory (indicators and regional statistics)", "url": "https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6"},
        creator=f"{AEO} (indicators); NASA Ames / NCCS (NEX-GDDP-CMIP6)",
        source_url="https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6", documentation_url="https://algeria-earth-observatory.github.io/docs/method-climate-projections/",
        license_notes="NEX-GDDP-CMIP6 files carry the licence of each CMIP6 model (CC BY 4.0 for the models used here unless stated otherwise in the NEX-GDDP-CMIP6 documentation). AEO indicators are CC BY 4.0.",
        citation="Algeria Earth Observatory (2026). Algeria climate hazard projections (NEX-GDDP-CMIP6), version 1.0.0. — from Thrasher, B. et al. (2022), Scientific Data 9, 262, doi:10.1038/s41597-022-01393-4.",
        references=[{"citation": "Thrasher, B. et al. (2022). NASA Global Daily Downscaled Projections, CMIP6. Scientific Data 9, 262.", "doi": "10.1038/s41597-022-01393-4"}],
        spatial_extent={**DZ, "description": "Algeria and its 69 wilayas (AEO boundaries 2026-11-20); cropland values for wilayas with ≥ 10,000 ha of stable cropland."},
        temporal_extent={"start": "1985-01-01", "end": "2100-12-31", "ongoing": False, "frequency": "30-year periods", "description": "Baseline 1985–2014; future 2041–2070 and 2071–2100."},
        resolution={"spatial": "Wilayas (0.25° cells)", "spatial_m": None, "temporal": "30-year means"},
        format=["CSV", "Parquet"], crs="not applicable (tables by administrative unit)",
        variables=[{"name": k, "units": u, "description": d} for k, u, d in [("tx_mean", "°C", "Mean daily maximum temperature"), ("hd35", "days/year", "Days above 35 °C"), ("hd40", "days/year", "Days above 40 °C"),
                   ("spring32", "days/year", "Days above 32 °C in March–May"), ("prcptot", "% change", "Annual precipitation"), ("pr_ndjfma", "% change", "November–April precipitation"), ("cdd", "days", "Longest dry spell (< 1 mm/day)")]],
        processing="Daily tasmax and pr subset to Algeria from NASA NCCS THREDDS; annual indicators per cell and model; 30-year means; area-weighted unit means; change against each model's own 1985–2014; ensemble median, range and sign agreement.",
        validation="Each model is compared with its own historical run; QC lists the national changes for every indicator and scenario.",
        limitations=["Projections, not forecasts.", "8 models do not span the full CMIP6 range.", "Statistical downscaling at 0.25° cannot represent local relief.", "Fixed thresholds (32, 35, 40 °C) are indicators, not crop-specific damage thresholds."],
        algeria_notes="Warming is projected everywhere; rainfall changes are uncertain in sign in the south and mostly negative in the north, with model disagreement shown for each wilaya.",
        access=access(m, {"aeo_cmip6_change_admin0-1_v1.0.0.csv": "Projected change by wilaya — model median and range (CSV)",
                          "aeo_cmip6_change_by_model_admin0-1_v1.0.0.csv": "Projected change by wilaya and model (CSV)"}),
        code_url=f"{REPO}/cmip6", map_layers=[f"cmip6-{k}" for k in ["tx_mean", "hd40", "spring32", "prcptot", "pr_ndjfma"]],
        verification={"checked": m["created"], "urls_checked": True, "unverified_fields": [], "sources_consulted": ["https://ds.nccs.nasa.gov/thredds/catalog/AMES/NEX/GDDP-CMIP6/catalog.html", "https://doi.org/10.1038/s41597-022-01393-4"], "notes": "See PROVENANCE.json."},
    )


def reservoirs():
    mp = "/data/aeo/products/reservoirs/v1.0.0/manifest.json"
    m = manifest(mp)
    t = m["temporal_coverage"]["monthly"]
    return base(m, mp, pvars=["wet_area_km2", "pct_of_observed_max"],
        id="aeo-dza-reservoirs-deafrica",
        title="Algeria reservoir monitor: monthly water surface area of the main reservoirs (Landsat, 1984–present)",
        title_fr="Suivi des barrages de l'Algérie : surface en eau mensuelle des principales retenues (Landsat, depuis 1984)",
        title_ar=None,
        description=f"Monthly water surface area of Algeria's reservoirs of 0.5 km² or more in Global Dam Watch, from the Digital Earth Africa Waterbodies Landsat observations aggregated by AEO per reservoir, {t[0]} to {t[1]}, with the latest observation and the share of the largest area observed since 1984.",
        purpose="Follow how full Algeria's main reservoirs are from satellite, month by month, with an open and reproducible method.",
        domain=["water"], categories=["Reservoirs", "Surface water", "Dams"],
        keywords=["reservoir", "dam", "barrage", "water surface", "Landsat", "DE Africa", "Global Dam Watch", "Algeria"],
        data_nature="derived", data_type="point",
        provider={"name": "Digital Earth Africa (Waterbodies); Global Dam Watch; Algeria Earth Observatory (aggregation)", "url": "https://www.digitalearthafrica.org/en_za/waterbodies-continental-service/"},
        creator=f"{AEO} (aggregation); Digital Earth Africa; Global Dam Watch consortium",
        source_url="https://www.digitalearthafrica.org/en_za/waterbodies-continental-service/", documentation_url="https://algeria-earth-observatory.github.io/docs/method-reservoirs/",
        license_notes="DE Africa Waterbodies and GDW are CC BY 4.0. GDW authors ask that their database not be re-hosted in whole; AEO publishes only dam points, names and capacities for Algeria with derived series. Attribution: 'This product incorporates data from the GDW database © Global Dam Watch (2024).'",
        citation="Algeria Earth Observatory (2026). Algeria reservoir monitor (DE Africa Waterbodies), version 1.0.0. — from Digital Earth Africa Waterbodies and Global Dam Watch v1.0 (doi:10.6084/m9.figshare.25988293).",
        references=[{"citation": "Global Dam Watch database version 1.0 (2024). figshare.", "doi": "10.6084/m9.figshare.25988293"}],
        spatial_extent={**DZ, "description": "Reservoirs of at least 0.5 km² listed in Global Dam Watch for Algeria."},
        temporal_extent={"start": f"{t[0]}-01", "end": None, "ongoing": True, "frequency": "monthly", "description": f"{t[0]} to {t[1]}; DE Africa updates weekly."},
        resolution={"spatial": "Reservoirs (Landsat 30 m)", "spatial_m": 30, "temporal": "monthly"},
        format=["CSV", "Parquet", "GeoJSON"], crs="EPSG:4326 (points)",
        variables=[{"name": "wet_area_km2", "units": "km²", "description": "Median water surface area of the month's valid scenes"},
                   {"name": "pct_of_observed_max", "units": "%", "description": "Share of the largest monthly area observed since 1984 (surface, not volume)"},
                   {"name": "valid_scenes", "units": "count", "description": "Landsat scenes with ≥ 85 % of the reservoir observed"}],
        processing="DE Africa waterbody polygons matched to GDW reservoir polygons (500 m buffer); wet area summed per scene; scenes with < 85 % observed dropped; monthly median.",
        validation="Prototype check at Beni Haroun: Sentinel-2 MNDWI areas of 25–32 km² in November 2026 agree with the Landsat series and the GDW outline (36 km²).",
        limitations=["Surface area, not stored volume; not an official ANBT filling rate.", "Clouds and shadows reduce valid scenes; some months are empty.",
                     "Landsat 30 m misses narrow arms and is affected by turbid or very shallow water.", "Dams built after the GDW compilation (2024) are missing."],
        algeria_notes="63 of 65 reservoirs have Landsat observations up to July–November 2026. Saharan reservoirs such as Djorf Torba are rarely observed well enough (85 % of the area) to give a monthly value.",
        access=access(m, {"aeo_reservoirs_points_v1.0.0.csv": "Reservoirs — attributes and latest water area (CSV)",
                          "aeo_reservoir_area_monthly_points_v1.0.0.csv": "Reservoirs — monthly water surface area (CSV)"}),
        code_url=f"{REPO}/reservoirs", map_layers=[],
        verification={"checked": m["created"], "urls_checked": True, "unverified_fields": [], "sources_consulted": ["https://docs.digitalearthafrica.org/en/latest/data_specs/Waterbodies_specs.html", "https://doi.org/10.6084/m9.figshare.25988293"], "notes": "See PROVENANCE.json for matched waterbody ids."},
    )


ALL = {"stable-cropland": stable_cropland, "et-soil-moisture": et_sm, "water-storage": water_storage, "seasonal-outlook": outlook,
       "climate-projections": projections, "reservoirs": reservoirs}

if __name__ == "__main__":
    for k in sys.argv[1:] or ALL:
        write(ALL[k]())
