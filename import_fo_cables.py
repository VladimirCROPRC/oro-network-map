import argparse
import json
import math
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


KML = "{http://www.opengis.net/kml/2.2}"
LAYER_ID = "fo-cables"
LAYER_FILE = "layers/fo-cables.geojson"
STYLE_COLORS = {
    "#style_blue": "b",
    "#style_lime": "g",
    "#style_red": "r",
}
FIELD_KEYS = {
    "data_instalarii": "di",
    "proprietar": "pr",
    "rec_id": "ri",
    "status": "st",
    "tip": "tp",
    "tip_structura_capat_a": "ta",
    "id_structura_capat_a": "ia",
    "tip_structura_capat_z": "tz",
    "id_structura_capat_z": "iz",
    "cabluri": "cb",
}


def coordinates(text):
    result = []
    for token in (text or "").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lng, lat = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        if math.isfinite(lng) and math.isfinite(lat) and -180 <= lng <= 180 and -90 <= lat <= 90:
            result.append([round(lng, 6), round(lat, 6)])
    return result


def main():
    parser = argparse.ArgumentParser(description="Import FO cables from KMZ")
    parser.add_argument("kmz", type=Path)
    parser.add_argument("--dist", type=Path, default=Path(__file__).resolve().parent / "dist")
    args = parser.parse_args()

    output = args.dist / LAYER_FILE
    output.parent.mkdir(parents=True, exist_ok=True)
    count = skipped = 0
    min_lng = min_lat = float("inf")
    max_lng = max_lat = float("-inf")

    with zipfile.ZipFile(args.kmz) as archive, archive.open("doc.kml") as source, output.open("w", encoding="utf-8") as target:
        target.write('{"type":"FeatureCollection","features":[')
        first = True
        for _, element in ET.iterparse(source, events=("end",)):
            if element.tag != KML + "Placemark":
                continue
            lines = []
            for line in element.iter(KML + "LineString"):
                points = coordinates(line.findtext(KML + "coordinates"))
                if len(points) >= 2:
                    lines.append(points)
            if not lines:
                skipped += 1
                element.clear()
                continue
            for line in lines:
                for lng, lat in line:
                    min_lng, max_lng = min(min_lng, lng), max(max_lng, lng)
                    min_lat, max_lat = min(min_lat, lat), max(max_lat, lat)
            geometry = {"type": "LineString", "coordinates": lines[0]} if len(lines) == 1 else {"type": "MultiLineString", "coordinates": lines}
            style = (element.findtext(KML + "styleUrl") or "").strip()
            properties = {"n": (element.findtext(KML + "name") or "Cablu FO").strip()}
            for field in element.iter(KML + "Data"):
                key = (field.get("name") or "").strip()
                value = (field.findtext(KML + "value") or "").strip()
                if key in FIELD_KEYS and value:
                    properties[FIELD_KEYS[key]] = value
            properties["_c"] = STYLE_COLORS.get(style, "c")
            feature = {
                "type": "Feature",
                "id": str(count + 1),
                "properties": properties,
                "geometry": geometry,
            }
            if not first:
                target.write(",")
            target.write(json.dumps(feature, ensure_ascii=False, separators=(",", ":")))
            first = False
            count += 1
            element.clear()
        target.write("]}")

    if not count:
        raise ValueError("No FO cable geometries found")

    manifest_path = args.dist / "layers.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    layer = {
        "id": LAYER_ID,
        "name": "FO Cables",
        "group": "FO Cables",
        "file": LAYER_FILE,
        "features": count,
        "sourceFeatures": count + skipped,
        "skipped": skipped,
        "geometryTypes": {"LineString": count},
        "bytes": output.stat().st_size,
        "source": args.kmz.name,
        "bounds": [min_lng, min_lat, max_lng, max_lat],
        "color": "#35d6ff",
    }
    manifest["layers"] = [item for item in manifest["layers"] if item["id"] != LAYER_ID] + [layer]
    manifest["errors"] = []
    manifest["totals"]["layers"] = len(manifest["layers"])
    manifest["totals"]["features"] = sum(item["features"] for item in manifest["layers"])
    manifest["totals"]["skipped"] = sum(item["skipped"] for item in manifest["layers"])
    manifest["totals"]["bytes"] = sum(item["bytes"] for item in manifest["layers"])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Imported {count} FO cables; skipped {skipped}; output {output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
