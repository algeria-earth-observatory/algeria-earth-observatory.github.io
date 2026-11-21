"""Build the AEO bibliography from DOIs, using only verified metadata.

Input:  scripts/references/references.input.json  (DOI, category, domain, what it supports, why)
Output: src/data/publications.json                  (metadata from Crossref + verification record)

For every DOI:
  1. the DOI must be registered: doi.org handle API returns responseCode 1;
  2. metadata (title, authors, year, journal, volume, issue, pages, type) are taken from the
     Crossref REST API, never typed by hand;
  3. if `expect` fields are given in the input (title fragment, first author, year), they must
     match Crossref, so a wrong DOI cannot silently attach to a reference.
A DOI that fails any check is reported and left out of the output.

Usage: python scripts/references/verify_references.py
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INP = ROOT / "scripts" / "references" / "references.input.json"
OUT = ROOT / "src" / "data" / "publications.json"
UA = "AEO-reference-check/1.0 (+https://algeria-earth-observatory.github.io)"


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            if i == 3:
                raise
            time.sleep(2 * (i + 1))
    return {}


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", html.unescape(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def clean_title(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", html.unescape(t))
    return re.sub(r"\s+", " ", t).strip()


def main() -> None:
    items = json.loads(INP.read_text(encoding="utf-8"))
    out, failed = [], []
    for it in items:
        doi = it["doi"].lower()
        try:
            h = get(f"https://doi.org/api/handles/{urllib.parse.quote(doi)}")
            if h.get("responseCode") != 1:
                raise ValueError(f"DOI not registered (handle responseCode {h.get('responseCode')})")
            m = get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")["message"]
        except Exception as e:  # noqa: BLE001
            failed.append((doi, str(e)))
            continue
        title = clean_title((m.get("title") or [""])[0])
        authors = [{"family": a.get("family") or a.get("name", ""), "given": a.get("given", "")} for a in m.get("author", [])]
        parts = (m.get("published-print") or m.get("published-online") or m.get("issued") or {}).get("date-parts", [[None]])[0]
        year = parts[0]
        journal = (m.get("container-title") or [""])[0]
        exp = it.get("expect", {})
        problems = []
        if exp.get("title") and fold(exp["title"]) not in fold(title):
            problems.append(f"title mismatch: {title!r}")
        if exp.get("first_author") and (not authors or fold(exp["first_author"]) != fold(authors[0]["family"])):
            problems.append(f"first author mismatch: {authors[0]['family'] if authors else None!r}")
        if exp.get("year") and exp["year"] != year:
            problems.append(f"year mismatch: {year}")
        if problems:
            failed.append((doi, "; ".join(problems)))
            continue
        out.append({
            "doi": doi,
            "url": f"https://doi.org/{doi}",
            "title": title,
            "authors": authors,
            "year": year,
            "journal": journal,
            "volume": m.get("volume"),
            "issue": m.get("issue"),
            "pages": m.get("page") or m.get("article-number"),
            "type": m.get("type"),
            "publisher": m.get("publisher"),
            "category": it["category"],
            "domain": it["domain"],
            "topic": it["topic"],
            "supports": it.get("supports", []),
            "why": it["why"],
            "verified": {"date": dt.date.today().isoformat(), "doi_registered": True, "metadata_source": "Crossref REST API"},
        })
        time.sleep(0.3)
    out.sort(key=lambda r: (r["topic"], r["year"] or 0, r["authors"][0]["family"] if r["authors"] else ""))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"verified {len(out)} of {len(items)} references -> {OUT.relative_to(ROOT)}")
    for doi, why in failed:
        print(f"  REJECTED {doi}: {why}")
    if failed:
        sys.exit(2)


if __name__ == "__main__":
    main()
