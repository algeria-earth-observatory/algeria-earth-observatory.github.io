"""Generate catalog records for planned AEO product families.

These are placeholders for products that do not exist yet. They carry no
data, maps, downloads, validation results or time series. Each record states
the intended scope only, and the build schema forbids download links for
status "in-preparation".
Run once: python scripts/processing/make_planned_products.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "src" / "content" / "datasets"
CHECKED = "2026-11-19"

COMMON_LIMITS = [
    "No data have been released. Methods, input versions, validation design and accuracy assessment will be documented and reviewed before any release.",
]

PRODUCTS = [
    {
        "id": "aeo-cropland-extent",
        "title": "AEO Cropland Extent — Algeria",
        "domain": ["agriculture"],
        "categories": ["Cropland extent and distribution", "Cropland classification and validation"],
        "keywords": ["cropland", "cropland extent", "Algeria", "classification"],
        "description": "A planned national cropland extent product for Algeria with an explicit cropland definition suited to dryland agriculture, documented inputs and a design-based accuracy assessment.",
        "scope": [
            "A stated cropland definition, including how temporarily fallow land is treated",
            "National coverage with documented reference period(s)",
            "Accuracy and area estimates with uncertainty from independent reference data",
            "Comparison notes against existing global cropland products",
        ],
    },
    {
        "id": "aeo-agricultural-land-use-change",
        "title": "AEO Agricultural Land-Use Change",
        "domain": ["agriculture", "human-change"],
        "categories": ["Agricultural land-use change", "Cropland expansion and contraction"],
        "keywords": ["land-use change", "cropland expansion", "cropland abandonment", "Algeria"],
        "description": "A planned product describing where and when agricultural land in Algeria expanded, contracted or changed use, with change definitions and error characterisation stated up front.",
        "scope": [
            "Expansion and contraction of cultivated land over multi-year periods",
            "Separation of real change from classification noise and inter-annual fallow cycles",
            "Change-area estimates with confidence intervals",
        ],
    },
    {
        "id": "aeo-winter-cereal-distribution",
        "title": "AEO Winter Cereal Distribution",
        "domain": ["agriculture"],
        "categories": ["Winter cereals", "Crop-type mapping"],
        "keywords": ["winter cereals", "wheat", "barley", "crop type", "Algeria"],
        "description": "A planned product on the distribution of winter cereals (principally wheat and barley) across Algeria's cereal-growing regions, intended to support area monitoring in rainfed and irrigated systems.",
        "scope": [
            "Winter cereal presence for documented agricultural seasons",
            "Clear treatment of mixed, intercropped and failed crops",
            "Reference data collection protocol and accuracy assessment",
        ],
    },
    {
        "id": "aeo-fallow-and-cropping-activity",
        "title": "AEO Fallow Land and Cropping Activity",
        "domain": ["agriculture", "land-ecosystems"],
        "categories": ["Active cropland and fallow land", "Crop calendars and growing seasons"],
        "keywords": ["fallow", "active cropland", "cropping intensity", "Algeria"],
        "description": "A planned product distinguishing actively cropped land from temporarily fallow and non-agricultural land in a given season — a central difficulty for monitoring dryland agriculture in Algeria.",
        "scope": [
            "Season-specific active versus fallow status within cropland",
            "Explicit decision rules for low-vegetation and drought-affected seasons",
            "Uncertainty reporting where active and fallow land are spectrally similar",
        ],
    },
    {
        "id": "aeo-agricultural-drought-indicators",
        "title": "AEO Agricultural Drought Indicators",
        "domain": ["agriculture", "climate-drought"],
        "categories": ["Agricultural drought", "Crop conditions and vegetation indices"],
        "keywords": ["agricultural drought", "SPEI", "vegetation condition", "Algeria"],
        "description": "A planned set of agricultural drought indicators for Algeria that combine climatic water balance and vegetation condition, summarised over cropland and by wilaya.",
        "scope": [
            "Indicators computed only over cropland masks with documented versions",
            "Wilaya-level summaries using a versioned boundary set",
            "Clear separation of observed, derived and modelled inputs",
        ],
    },
    {
        "id": "aeo-greenhouse-agriculture",
        "title": "AEO Greenhouse Agriculture Monitoring",
        "domain": ["agriculture", "human-change"],
        "categories": ["Greenhouse agriculture"],
        "keywords": ["greenhouses", "plasticulture", "protected agriculture", "Algeria"],
        "description": "A planned product mapping plastic greenhouse and protected agriculture in Algeria, where it has expanded in coastal plains and southern oases.",
        "scope": [
            "Greenhouse footprint for documented reference years",
            "Discrimination from other bright surfaces (buildings, bare soil, salt flats)",
            "Accuracy assessment from independent reference samples",
        ],
    },
    {
        "id": "aeo-climate-vegetation-time-series",
        "title": "AEO Climate and Vegetation Time Series",
        "domain": ["climate-drought", "agriculture"],
        "categories": ["Seasonal climate variability", "Vegetation dynamics"],
        "keywords": ["time series", "precipitation", "NDVI", "wilaya", "Algeria"],
        "description": "Planned harmonised time series of precipitation, temperature and vegetation indices aggregated to wilayas and agricultural zones, generated by published, reproducible code from documented source datasets.",
        "scope": [
            "Monthly series aggregated to a versioned wilaya boundary set",
            "Source dataset versions and aggregation code published with every release",
            "Machine-readable tables (CSV) with complete metadata",
        ],
    },
]

for p in PRODUCTS:
    rec = {
        "id": p["id"],
        "title": p["title"],
        "description": p["description"],
        "purpose": None,
        "domain": p["domain"],
        "categories": p["categories"],
        "keywords": p["keywords"],
        "status": "in-preparation",
        "origin": "aeo-original",
        "data_nature": None,
        "data_type": None,
        "provider": {"name": "Algeria Earth Observatory", "url": "https://algeria-earth-observatory.github.io/"},
        "creator": None,
        "source_url": None,
        "documentation_url": None,
        "license": None,
        "license_notes": "Licence to be decided before release; AEO intends to use an open licence.",
        "citation": None,
        "doi": None,
        "references": [],
        "spatial_extent": {
            "coverage": "algeria",
            "description": "Planned national coverage of Algeria.",
            "algeria_subset": "native",
            "bbox": None,
        },
        "temporal_extent": None,
        "resolution": None,
        "format": [],
        "crs": None,
        "variables": [],
        "processing": None,
        "validation": None,
        "limitations": COMMON_LIMITS,
        "version": None,
        "published_date": None,
        "updated_date": None,
        "download_url": None,
        "preview_url": None,
        "access": [],
        "code_url": None,
        "algeria_notes": None,
        "planned_scope": p["scope"],
        "verification": {
            "checked": CHECKED,
            "urls_checked": False,
            "unverified_fields": [],
            "sources_consulted": [],
            "notes": "Planned product family. Nothing in this record describes released data.",
        },
    }
    (OUT / f"{p['id']}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", p["id"])
