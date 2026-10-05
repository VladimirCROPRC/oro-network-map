const fs = require("fs");

const records = JSON.parse(fs.readFileSync("dist/site-codes.json", "utf8"));
const validRecords = records.filter((record) => {
  const [lng, lat] = record.p || [];
  return Number.isFinite(lng) && Number.isFinite(lat) && lng >= 19 && lng <= 30 && lat >= 43 && lat <= 49;
});
const features = validRecords.map((record, index) => ({
  type: "Feature",
  id: String(index),
  properties: { Cod: record.c, Nume: record.n },
  geometry: { type: "Point", coordinates: record.p },
}));

const bounds = features.reduce(
  (box, feature) => {
    const [lng, lat] = feature.geometry.coordinates;
    box[0] = Math.min(box[0], lng);
    box[1] = Math.min(box[1], lat);
    box[2] = Math.max(box[2], lng);
    box[3] = Math.max(box[3], lat);
    return box;
  },
  [Infinity, Infinity, -Infinity, -Infinity],
);

const collection = { type: "FeatureCollection", features };
const output = JSON.stringify(collection);
fs.writeFileSync("dist/layers/site-locations.geojson", output);

const manifest = JSON.parse(fs.readFileSync("dist/layers.json", "utf8"));
manifest.layers = manifest.layers.filter((layer) => layer.id !== "site-locations");
manifest.layers.splice(1, 0, {
  id: "site-locations",
  name: "Site-uri",
  group: "Site-uri",
  file: "layers/site-locations.geojson",
  features: features.length,
  sourceFeatures: records.length,
  skipped: records.length - features.length,
  geometryTypes: { Point: features.length },
  bytes: Buffer.byteLength(output),
  source: "google_2602.htm.html",
  bounds,
  color: "#ffe500",
});
manifest.totals.layers = manifest.layers.length;
manifest.totals.features = manifest.layers.reduce((sum, layer) => sum + layer.features, 0);
fs.writeFileSync("dist/layers.json", JSON.stringify(manifest));

console.log(`Built Site-uri layer with ${features.length} labeled points`);
