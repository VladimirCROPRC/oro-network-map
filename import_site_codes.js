const fs = require("fs");

const input = process.argv[2];
const output = process.argv[3];
if (!input || !output) throw new Error("Usage: node import_site_codes.js INPUT OUTPUT");

const html = fs.readFileSync(input, "latin1");
const linkPattern = /href="http:\/\/maps\.google\.com\/maps\?q=([+-]?\d+(?:\.\d+)?),([+-]?\d+(?:\.\d+)?)"[^>]*>([\s\S]*?)<\/a>/gi;
const records = [];
let match;

while ((match = linkPattern.exec(html))) {
  const name = match[3].replace(/<[^>]+>/g, "").replace(/&nbsp;/gi, " ").replace(/\s+/g, " ").trim();
  const code = (name.match(/^[A-Za-z0-9_-]+/) || [""])[0];
  const lat = Number(match[1]);
  const lng = Number(match[2]);
  if (code && Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180) {
    records.push({ c: code, n: name, p: [lng, lat] });
  }
}

fs.writeFileSync(output, JSON.stringify(records));
console.log(`Imported ${records.length} site locations`);
