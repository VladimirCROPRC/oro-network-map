import argparse
import json
from pathlib import Path

import openpyxl


LAYER_ID = "orange-jonctiuni-oro"
LAYER_FILE = "layers/orange-jonctiuni-oro.geojson"
PUBLIC_FIELDS = ("ORO Alias", "Owner", "Owner Alias", "RF id", "Node Code")


def clean(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def main():
    parser = argparse.ArgumentParser(description="Import Orange ORO junctions into the map")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--dist", type=Path, default=Path(__file__).resolve().parent / "dist")
    args = parser.parse_args()

    workbook = openpyxl.load_workbook(args.workbook, read_only=True, data_only=True)
    sheet = workbook["Optical Splice Closure"]
    rows = sheet.iter_rows(values_only=True)
    headers = [str(value).strip() if value is not None else "" for value in next(rows)]
    required = {"ORO Alias", "Latitude", "Longitude"}
    if not required.issubset(headers):
        raise ValueError(f"Missing columns: {sorted(required - set(headers))}")

    features = []
    search_records = []
    skipped = 0
    for row_number, row in enumerate(rows, start=2):
        source_properties = {header: clean(value) for header, value in zip(headers, row) if header}
        try:
            latitude = float(source_properties["Latitude"])
            longitude = float(source_properties["Longitude"])
        except (TypeError, ValueError):
            skipped += 1
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            skipped += 1
            continue

        feature_id = str(row_number)
        point = [round(longitude, 7), round(latitude, 7)]
        properties = {key: source_properties.get(key) for key in PUBLIC_FIELDS if source_properties.get(key) is not None}
        features.append({
            "type": "Feature",
            "id": feature_id,
            "properties": properties,
            "geometry": {"type": "Point", "coordinates": point},
        })
        alias = source_properties.get("ORO Alias")
        if alias:
            search_records.append({"l": LAYER_ID, "f": feature_id, "o": str(alias), "p": point})

    if not features:
        raise ValueError("No valid Orange points found")

    layer_path = args.dist / LAYER_FILE
    layer_path.parent.mkdir(parents=True, exist_ok=True)
    collection = {"type": "FeatureCollection", "features": features}
    layer_path.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    longitudes = [feature["geometry"]["coordinates"][0] for feature in features]
    latitudes = [feature["geometry"]["coordinates"][1] for feature in features]
    layer = {
        "id": LAYER_ID,
        "name": "Joncțiuni ORO",
        "group": "Orange",
        "file": LAYER_FILE,
        "features": len(features),
        "sourceFeatures": len(features) + skipped,
        "skipped": skipped,
        "geometryTypes": {"Point": len(features)},
        "bytes": layer_path.stat().st_size,
        "source": args.workbook.name,
        "bounds": [min(longitudes), min(latitudes), max(longitudes), max(latitudes)],
        "color": "#ff7900",
    }

    manifest_path = args.dist / "layers.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generatedFrom"] = args.workbook.name
    manifest["layers"] = [layer]
    manifest["errors"] = []
    manifest["totals"]["layers"] = len(manifest["layers"])
    manifest["totals"]["features"] = sum(item["features"] for item in manifest["layers"])
    manifest["totals"]["skipped"] = sum(item["skipped"] for item in manifest["layers"])
    manifest["totals"]["bytes"] = sum(item["bytes"] for item in manifest["layers"])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    search_path = args.dist / "search-index.json"
    search_index = []
    search_path.write_text(json.dumps(search_index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"Imported {len(features)} Orange points and {len(search_records)} ORO aliases; skipped {skipped}")


if __name__ == "__main__":
    main()
