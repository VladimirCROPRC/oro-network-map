"""Replace only FO Orange from a KMZ, retaining cable details and KML colors."""
import argparse
import gzip
import io
import json
import math
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as ET
from import_nested_fo import coordinate_list, styles_for, NS, KML

FIELDS = {
    'proprietar': 'pr', 'status': 'st', 'tip': 'tp',
    'tip_structura_capat_a': 'ta', 'id_structura_capat_a': 'ia',
    'tip_structura_capat_z': 'tz', 'id_structura_capat_z': 'iz', 'cabluri': 'cb',
}


def documents(source):
    with ZipFile(source) as archive:
        for name in archive.namelist():
            if name.lower().endswith('.kml'):
                yield name, archive.read(name)
            elif name.lower().endswith('.kmz'):
                yield from documents(io.BytesIO(archive.read(name)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kmz', type=Path)
    parser.add_argument('--dist', type=Path, default=Path(__file__).resolve().parent / 'dist')
    args = parser.parse_args()
    manifest_path = args.dist / 'layers.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    index = next(i for i, layer in enumerate(manifest['layers']) if layer['id'] == 'fo-orange')
    old_layer = manifest['layers'][index]
    counts, geometry_types, colors, field_counts = Counter(), Counter(), Counter(), Counter()
    bounds_by_shard = {}
    total_bounds = [math.inf, math.inf, -math.inf, -math.inf]
    source_count = skipped = count = missing_colors = 0
    with tempfile.TemporaryDirectory(prefix='orange-snapshot-') as temporary:
        staging = Path(temporary)
        db = sqlite3.connect(staging / 'features.sqlite')
        db.execute('PRAGMA journal_mode=OFF')
        db.execute('PRAGMA synchronous=OFF')
        db.execute('CREATE TABLE features(shard TEXT, payload TEXT)')
        for filename, content in documents(args.kmz):
            root = ET.fromstring(content, ET.XMLParser(recover=True, huge_tree=True))
            _, maps = styles_for(root)
            styles = {('#' + style.get('id')): style.findtext(KML+'LineStyle/'+KML+'color')
                      for style in root.xpath('.//k:Style[@id]', namespaces=NS)}
            for pm in root.xpath('.//k:Placemark', namespaces=NS):
                line_elements = pm.xpath('.//k:LineString', namespaces=NS)
                if not line_elements:
                    continue
                source_count += 1
                lines = [coordinate_list(line.findtext(KML+'coordinates')) for line in line_elements]
                lines = [line for line in lines if len(line) >= 2]
                if not lines:
                    skipped += 1
                    continue
                style_url = (pm.findtext(KML+'styleUrl') or '').strip()
                color = pm.findtext(KML+'Style/'+KML+'LineStyle/'+KML+'color') or styles.get(maps.get(style_url, style_url))
                color = (color or '').strip().lstrip('#')
                if len(color) != 8:
                    missing_colors += 1
                    color = 'ffffd635'
                properties = {'n': (pm.findtext(KML+'name') or '').strip(),
                              '_color': ('#'+color[6:8]+color[4:6]+color[2:4]).lower(),
                              '_opacity': int(color[:2], 16)/255}
                values = {(field.get('name') or '').strip(): field.findtext(KML+'value') or ''
                          for field in pm.iter(KML+'Data')}
                values.update({(field.get('name') or '').strip(): field.text or ''
                               for field in pm.iter(KML+'SimpleData')})
                for field, key in FIELDS.items():
                    properties[key] = values.get(field, '').strip()
                    field_counts[key] += bool(properties[key])
                all_points = [point for line in lines for point in line]
                anchor = all_points[len(all_points)//2]
                shard = f'{math.floor(anchor[0]*4)}_{math.floor(anchor[1]*4)}'
                bounds = bounds_by_shard.setdefault(shard, [math.inf, math.inf, -math.inf, -math.inf])
                for lng, lat in all_points:
                    for target in (bounds, total_bounds):
                        target[0], target[1] = min(target[0], lng), min(target[1], lat)
                        target[2], target[3] = max(target[2], lng), max(target[3], lat)
                payload = [properties, lines[0]] if len(lines) == 1 else [properties, lines, 1]
                db.execute('INSERT INTO features VALUES(?,?)', (shard, json.dumps(payload, ensure_ascii=False, separators=(',', ':'))))
                counts[shard] += 1
                colors[properties['_color']] += 1
                geometry_types['LineString' if len(lines)==1 else 'MultiLineString'] += 1
                count += 1
            db.commit()
            if count and count % 30000 == 0:
                print(f'Imported {count} cables', flush=True)
        if not count or missing_colors:
            raise ValueError(f'Import rejected: cables={count}, unresolved KML colors={missing_colors}')
        db.execute('CREATE INDEX feature_shards ON features(shard)')
        db.commit()
        shards = []
        for shard in sorted(counts):
            filename = f'fo-orange-{shard}.geojson.gz'
            path = staging / filename
            with path.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=6, mtime=0) as output:
                output.write(b'{"c":[')
                written = 0
                for (payload,) in db.execute('SELECT payload FROM features WHERE shard=?', (shard,)):
                    output.write(((',' if written else '')+payload).encode('utf-8'))
                    written += 1
                output.write(b']}')
            assert written == counts[shard]
            shards.append({'file': 'layers/'+filename, 'features': written,
                           'bytes': path.stat().st_size, 'bounds': bounds_by_shard[shard]})
        db.close()
        replacement = {'id': 'fo-orange', 'name': 'FO Orange', 'group': old_layer['group'],
                       'features': count, 'sourceFeatures': source_count, 'skipped': skipped,
                       'geometryTypes': dict(geometry_types), 'bytes': sum(s['bytes'] for s in shards),
                       'source': args.kmz.name, 'bounds': total_bounds,
                       'color': old_layer['color'], 'shards': shards}
        # Commit replacement only after the complete new source was parsed and packaged.
        for shard in shards:
            target = args.dist / shard['file']
            target.write_bytes((staging / target.name).read_bytes())
        keep = {s['file'] for s in shards}
        for shard in old_layer.get('shards', [old_layer]):
            if shard.get('file') and shard['file'] not in keep:
                (args.dist / shard['file']).unlink(missing_ok=True)
        manifest['layers'][index] = replacement
        for key in ('features', 'skipped', 'bytes'):
            manifest['totals'][key] = sum(layer.get(key, 0) for layer in manifest['layers'])
        manifest['totals']['layers'] = len(manifest['layers'])
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        print(json.dumps({'imported': count, 'skipped': skipped, 'colors': dict(colors),
                          'fieldsPopulated': dict(field_counts), 'shards': len(shards),
                          'compressedBytes': replacement['bytes']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
