#!/usr/bin/env python3
import html
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {"k": "http://www.opengis.net/kml/2.2"}
LAYERS = {
    "Backbone": ("istoric-incidente-backbone", "Backbone", "#ef4444", "files/Backbone.png"),
    "Local": ("istoric-incidente-local", "Local", "#f59e0b", "files/Local.png"),
    "Solutie provizorie - atenuari": (
        "istoric-incidente-solutii-provizorii",
        "Soluții provizorii - atenuări",
        "#a855f7",
        "files/Provizorie.png",
    ),
}


def plain_text(value):
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"</(?:h\d|p|div|li)>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


def bounds(features):
    xs = [f["geometry"]["coordinates"][0] for f in features]
    ys = [f["geometry"]["coordinates"][1] for f in features]
    return [min(xs), min(ys), max(xs), max(ys)]


def main(kmz_path, dist_path):
    dist = Path(dist_path)
    layer_dir = dist / "layers"
    with zipfile.ZipFile(kmz_path) as archive:
        root = ET.fromstring(archive.read("doc.kml"))
        icon_data = {source: archive.read(source) for *_, source in LAYERS.values()}

    generated = []
    for folder in root.findall(".//k:Folder", NS):
        folder_name = folder.findtext("k:name", default="", namespaces=NS).strip()
        if folder_name not in LAYERS:
            continue
        layer_id, display_name, color, icon_source = LAYERS[folder_name]
        features = []
        for index, placemark in enumerate(folder.findall("k:Placemark", NS), 1):
            coordinates = placemark.findtext(".//k:Point/k:coordinates", default="", namespaces=NS)
            parts = [part.strip() for part in coordinates.strip().split(",")]
            if len(parts) < 2:
                continue
            try:
                longitude, latitude = float(parts[0]), float(parts[1])
            except ValueError:
                continue
            incident = placemark.findtext("k:name", default="Incident", namespaces=NS).strip()
            description = plain_text(placemark.findtext("k:description", default="", namespaces=NS))
            features.append({
                "type": "Feature",
                "id": f"{layer_id}-{index}",
                "properties": {
                    "Incident": incident,
                    "Categorie": display_name,
                    "Descriere": description,
                },
                "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
            })

        output = layer_dir / f"{layer_id}.geojson"
        output.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        icon_output = dist / "icons" / f"{layer_id}.png"
        icon_output.write_bytes(icon_data[icon_source])
        generated.append({
            "id": layer_id,
            "name": display_name,
            "group": "Istoric incidente",
            "file": f"layers/{output.name}",
            "features": len(features),
            "sourceFeatures": len(features),
            "skipped": 0,
            "geometryTypes": {"Point": len(features)},
            "bytes": output.stat().st_size,
            "source": Path(kmz_path).name,
            "bounds": bounds(features),
            "color": color,
            "icon": f"icons/{icon_output.name}",
        })

    manifest_path = dist / "layers.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    old = [layer for layer in manifest["layers"] if layer.get("group") != "Istoric incidente"]
    manifest["layers"] = old + generated
    manifest["totals"]["layers"] = len(manifest["layers"])
    manifest["totals"]["features"] = sum(layer["features"] for layer in manifest["layers"])
    manifest["totals"]["bytes"] = sum(layer.get("bytes", 0) for layer in manifest["layers"])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"layers": [{"name": x["name"], "features": x["features"], "bytes": x["bytes"]} for x in generated], "total": sum(x["features"] for x in generated)}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
