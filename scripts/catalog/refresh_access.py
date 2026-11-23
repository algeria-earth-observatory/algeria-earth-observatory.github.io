"""Refresh the download entries of AEO product records from their manifests after a rebuild.

For every record with a `product.manifest`, each access entry whose URL is a manifest asset gets the
asset's current size and SHA-256, and `updated_date` becomes the manifest's `created` date. Nothing
else is changed. Fails if a record lists a download that the manifest no longer has.

Usage: python scripts/catalog/refresh_access.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    changed, errors = 0, []
    for f in sorted((ROOT / "src/content/datasets").glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        prod = rec.get("product")
        if not prod:
            continue
        mp = ROOT / "public" / prod["manifest"].lstrip("/")
        if not mp.exists():
            errors.append(f"{f.name}: manifest {prod['manifest']} missing")
            continue
        m = json.loads(mp.read_text(encoding="utf-8"))
        assets = {a["href"]: a for a in m.get("download_assets", [])}
        before = json.dumps(rec, ensure_ascii=False)
        base = prod["manifest"].rsplit("/", 1)[0] + "/"
        for a in rec.get("access", []):
            if a.get("kind") != "download" or not str(a.get("url", "")).startswith(base):
                continue
            if a["url"] not in assets:
                errors.append(f"{f.name}: {a['url']} not in manifest")
                continue
            a["size_bytes"] = assets[a["url"]]["bytes"]
            a["sha256"] = assets[a["url"]]["sha256"]
        rec["updated_date"] = m.get("created", rec.get("updated_date"))
        if json.dumps(rec, ensure_ascii=False) != before:
            f.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
    print(f"records refreshed: {changed}")
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
