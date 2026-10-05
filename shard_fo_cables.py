import json
import math
from collections import defaultdict
from pathlib import Path


DIST = Path(__file__).resolve().parent / "dist"
SOURCE = DIST / "layers" / "fo-cables.geojson"


def points(coordinates):
    if coordinates and isinstance(coordinates[0], (int, float)):
        yield coordinates
    else:
        for child in coordinates or []:
            yield from points(child)


data = json.loads(SOURCE.read_text(encoding="utf-8"))
groups = defaultdict(list)
for feature in data["features"]:
    coords = list(points(feature["geometry"]["coordinates"]))
    if not coords:
        continue
    anchor = coords[len(coords) // 2]
    key = f"{math.floor(anchor[0])}_{math.floor(anchor[1])}"
    groups[key].append(feature)

shards = []
for key, features in sorted(groups.items()):
    filename = f"layers/fo-cables-{key}.geojson"
    path = DIST / filename
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    all_points = [point for feature in features for point in points(feature["geometry"]["coordinates"])]
    longitudes = [point[0] for point in all_points]
    latitudes = [point[1] for point in all_points]
    shards.append({
        "file": filename,
        "features": len(features),
        "bytes": path.stat().st_size,
        "bounds": [min(longitudes), min(latitudes), max(longitudes), max(latitudes)],
    })

manifest_path = DIST / "layers.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
layer = next(item for item in manifest["layers"] if item["id"] == "fo-cables")
layer.pop("file", None)
layer["shards"] = shards
layer["bytes"] = sum(item["bytes"] for item in shards)
manifest["totals"]["bytes"] = sum(item["bytes"] for item in manifest["layers"])
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
SOURCE.unlink()
print(f"Created {len(shards)} geographic shards for {sum(item['features'] for item in shards)} cables")
