#!/usr/bin/env python3
import html
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {"k": "http://www.opengis.net/kml/2.2"}
LAYER_ID = "istoric-incidente-istorice"
LAYER_NAME = "Incidente istorice"


def plain_text(value):
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"</(?:h\d|p|div|li)>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


def main(kmz_path, output_path):
    with zipfile.ZipFile(kmz_path) as archive:
        root = ET.fromstring(archive.read("doc.kml"))

    features = []
    for index, placemark in enumerate(root.findall(".//k:Placemark", NS), 1):
        coordinates = placemark.findtext(".//k:Point/k:coordinates", default="", namespaces=NS)
        parts = [part.strip() for part in coordinates.strip().split(",")]
        if len(parts) < 2:
            continue
        try:
            longitude, latitude = float(parts[0]), float(parts[1])
        except ValueError:
            continue

        title = placemark.findtext("k:name", default="Incident", namespaces=NS).strip()
        match = re.search(r"\b(?:EVR|IMO)\d+\b", title, flags=re.I)
        incident = match.group(0).upper() if match else title
        details = plain_text(placemark.findtext("k:description", default="", namespaces=NS))
        description = "\n".join(filter(None, [
            title,
            f"{incident} · {LAYER_NAME}",
            "Descriere incident",
            details,
        ]))
        features.append({
            "type": "Feature",
            "id": f"{LAYER_ID}-{index}",
            "properties": {
                "Incident": incident,
                "Categorie": LAYER_NAME,
                "Titlu": title,
                "Descriere": description,
            },
            "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        })

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    xs = [feature["geometry"]["coordinates"][0] for feature in features]
    ys = [feature["geometry"]["coordinates"][1] for feature in features]
    print(json.dumps({
        "features": len(features),
        "bytes": output.stat().st_size,
        "bounds": [min(xs), min(ys), max(xs), max(ys)],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
