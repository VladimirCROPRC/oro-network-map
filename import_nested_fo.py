import argparse
import json
import math
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as ET


KML_NS = "http://www.opengis.net/kml/2.2"
KML = f"{{{KML_NS}}}"
NS = {"k": KML_NS}
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


def kml_color(value, fallback="#35d6ff"):
    value = (value or "").strip().lstrip("#")
    if len(value) == 8:
        return f"#{value[6:8]}{value[4:6]}{value[2:4]}".lower()
    if len(value) == 6:
        return f"#{value}".lower()
    return fallback


def coordinate_list(text):
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


def styles_for(root):
    styles = {}
    maps = {}
    for style in root.xpath(".//k:Style[@id]", namespaces=NS):
        color = style.findtext(f"{KML}LineStyle/{KML}color")
        if color:
            styles["#" + style.get("id")] = kml_color(color)
    for style_map in root.xpath(".//k:StyleMap[@id]", namespaces=NS):
        for pair in style_map.findall(KML + "Pair"):
            if (pair.findtext(KML + "key") or "").strip() == "normal":
                maps["#" + style_map.get("id")] = (pair.findtext(KML + "styleUrl") or "").strip()
                break
    return styles, maps


def feature_color(placemark, styles, maps, fallback):
    inline = placemark.findtext(f"{KML}Style/{KML}LineStyle/{KML}color")
    if inline:
        return kml_color(inline, fallback)
    style_url = (placemark.findtext(KML + "styleUrl") or "").strip()
    style_url = maps.get(style_url, style_url)
    return styles.get(style_url, fallback)


def properties_for(placemark, color):
    properties = {"_color": color}
    name = (placemark.findtext(KML + "name") or "").strip()
    if name:
        properties["n"] = name
    for field in placemark.iter(KML + "Data"):
        key = (field.get("name") or "").strip()
        value = (field.findtext(KML + "value") or "").strip()
        if key in FIELD_KEYS and value:
            properties[FIELD_KEYS[key]] = value
    return properties


def import_layer(kmz_path, dist, layer_id, layer_name, fallback_color):
    layers_dir = dist / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)
    for old in layers_dir.glob(f"{layer_id}-*.geojson"):
        old.unlink()

    temp_dir = Path(tempfile.mkdtemp(prefix=f"{layer_id}-", dir=dist.parent.resolve()))
    database = sqlite3.connect(temp_dir / "features.sqlite")
    database.execute("PRAGMA journal_mode=OFF")
    database.execute("PRAGMA synchronous=OFF")
    database.execute("CREATE TABLE features (shard TEXT NOT NULL, payload TEXT NOT NULL)")
    counts = defaultdict(int)
    shard_bounds = {}
    total_bounds = [float("inf"), float("inf"), float("-inf"), float("-inf")]
    count = skipped = feature_id = 0

    try:
        with ZipFile(kmz_path) as outer:
            nested_names = [name for name in outer.namelist() if name.lower().endswith(".kmz")]
            for nested_name in nested_names:
                with ZipFile(BytesIO(outer.read(nested_name))) as nested:
                    kml_name = next((name for name in nested.namelist() if name.lower().endswith(".kml")), None)
                    if not kml_name:
                        continue
                    root = ET.fromstring(nested.read(kml_name), parser=ET.XMLParser(recover=True, huge_tree=True))
                    styles, style_maps = styles_for(root)
                    for placemark in root.xpath(".//k:Placemark", namespaces=NS):
                        lines = []
                        for line in placemark.xpath(".//k:LineString", namespaces=NS):
                            points = coordinate_list(line.findtext(KML + "coordinates"))
                            if len(points) >= 2:
                                lines.append(points)
                        if not lines:
                            skipped += 1
                            continue

                        all_points = [point for line in lines for point in line]
                        anchor = all_points[len(all_points) // 2]
                        key = f"{math.floor(anchor[0] * 4)}_{math.floor(anchor[1] * 4)}"
                        bounds = shard_bounds.setdefault(key, [float("inf"), float("inf"), float("-inf"), float("-inf")])
                        for lng, lat in all_points:
                            bounds[0], bounds[1] = min(bounds[0], lng), min(bounds[1], lat)
                            bounds[2], bounds[3] = max(bounds[2], lng), max(bounds[3], lat)
                            total_bounds[0], total_bounds[1] = min(total_bounds[0], lng), min(total_bounds[1], lat)
                            total_bounds[2], total_bounds[3] = max(total_bounds[2], lng), max(total_bounds[3], lat)

                        feature_id += 1
                        color = feature_color(placemark, styles, style_maps, fallback_color)
                        geometry = {"type": "LineString", "coordinates": lines[0]} if len(lines) == 1 else {"type": "MultiLineString", "coordinates": lines}
                        compact_feature = [properties_for(placemark, color), geometry["coordinates"]]
                        if geometry["type"] == "MultiLineString":
                            compact_feature.append(1)
                        database.execute(
                            "INSERT INTO features (shard, payload) VALUES (?, ?)",
                            (key, json.dumps(compact_feature, ensure_ascii=False, separators=(",", ":"))),
                        )
                        counts[key] += 1
                        count += 1
                        if count % 10000 == 0:
                            database.commit()
        database.commit()
        database.execute("CREATE INDEX features_by_shard ON features (shard)")
        database.commit()

        shards = []
        for key in sorted(counts):
            filename = f"layers/{layer_id}-{key}.geojson"
            output = dist / filename
            with output.open("w", encoding="utf-8") as target:
                target.write('{"c":[')
                first = True
                written = 0
                for (payload,) in database.execute("SELECT payload FROM features WHERE shard = ?", (key,)):
                    if not first:
                        target.write(",")
                    target.write(payload)
                    first = False
                    written += 1
                target.write("]}")
            if written != counts[key]:
                raise RuntimeError(f"Shard {key} contains {written} of {counts[key]} expected features")
            shards.append({"file": filename, "features": counts[key], "bytes": output.stat().st_size, "bounds": shard_bounds[key]})
    finally:
        database.close()
        shutil.rmtree(temp_dir)

    if not count:
        raise ValueError(f"No cable geometries found in {kmz_path}")
    return {
        "id": layer_id,
        "name": layer_name,
        "group": "FO Cables",
        "features": count,
        "sourceFeatures": count + skipped,
        "skipped": skipped,
        "geometryTypes": {"LineString": count},
        "bytes": sum(shard["bytes"] for shard in shards),
        "source": kmz_path.name,
        "bounds": total_bounds,
        "color": fallback_color,
        "shards": shards,
    }


def main():
    parser = argparse.ArgumentParser(description="Import nested Orange and OROC cable KMZ collections")
    parser.add_argument("orange", type=Path)
    parser.add_argument("oroc", type=Path)
    parser.add_argument("--dist", type=Path, default=Path(__file__).resolve().parent / "dist")
    args = parser.parse_args()

    orange = import_layer(args.orange, args.dist, "fo-orange", "FO Orange", "#35d6ff")
    print(f"Imported {orange['features']} FO Orange cables", flush=True)
    oroc = import_layer(args.oroc, args.dist, "fo-oroc", "FO OROC", "#22c55e")
    print(f"Imported {oroc['features']} FO OROC cables", flush=True)

    manifest_path = args.dist / "layers.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_ids = {"fo-cables", "fo-orange", "fo-oroc"}
    current = manifest["layers"]
    insertion = next((index for index, layer in enumerate(current) if layer["id"] in old_ids), len(current))
    remaining = [layer for layer in current if layer["id"] not in old_ids]
    insertion = min(insertion, len(remaining))
    manifest["layers"] = remaining[:insertion] + [orange, oroc] + remaining[insertion:]
    manifest["errors"] = []
    manifest["totals"]["layers"] = len(manifest["layers"])
    manifest["totals"]["features"] = sum(layer["features"] for layer in manifest["layers"])
    manifest["totals"]["skipped"] = sum(layer["skipped"] for layer in manifest["layers"])
    manifest["totals"]["bytes"] = sum(layer["bytes"] for layer in manifest["layers"])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    layers_dir = args.dist / "layers"
    for old in layers_dir.glob("fo-cables-*.geojson"):
        old.unlink()


if __name__ == "__main__":
    main()
