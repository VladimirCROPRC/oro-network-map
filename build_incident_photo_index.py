#!/usr/bin/env python3
"""Build the compact incident-to-OneDrive-links index used by the map."""

import csv
import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def normalize_incident(value: str) -> str:
    value = value.strip().upper()
    match = re.fullmatch(r"IMO0*(\d+)", value)
    return f"IMO{int(match.group(1))}" if match else value


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: build_incident_photo_index.py INPUT.csv OUTPUT.json.gz")
    source, destination = map(Path, sys.argv[1:])
    links = defaultdict(list)
    with source.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            incident = normalize_incident(row.get("Tichet", ""))
            url = row.get("Link OneDrive", "").strip()
            if incident and url and url not in links[incident]:
                links[incident].append(url)
    payload = json.dumps(dict(sorted(links.items())), ensure_ascii=False, separators=(",", ":"))
    with destination.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as archive:
            archive.write(payload.encode("utf-8"))
    print(f"{len(links)} incidents indexed")


if __name__ == "__main__":
    main()
