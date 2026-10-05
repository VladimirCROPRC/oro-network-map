"""Import Camerete.xlsx into the three Camerete map layers."""
import argparse, gzip, json, math, re
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as ET

COLORS={'green':'#22c55e','red':'#ef4444','orange':'#ff7900','pink':'#e6007e','blue':'#2f80ed'}

def normalize(value):
    return ' '.join(str(value or '').strip().lower().split())

def owner_group(owner):
    text=normalize(owner)
    if text=='orange romania sa':return 'oro'
    if text in {'orange comunication sa','orange communication sa','orange communications sa','orange comunications sa'}:return 'oroc'
    return 'third-party'

def color_for(equipment,owner):
    text=normalize(equipment)
    if 'spt' in text:return COLORS['red']
    if 'osc' in text:return COLORS['green']
    return COLORS[{'oro':'orange','oroc':'pink','third-party':'blue'}[owner_group(owner)]]

def rows(path):
    with ZipFile(path) as archive:
        strings=[]
        if 'xl/sharedStrings.xml' in archive.namelist():
            for _,item in ET.iterparse(archive.open('xl/sharedStrings.xml'),events=['end'],tag='{*}si'):
                strings.append(''.join(t.text or '' for t in item.findall('.//{*}t')))
                item.clear()
                while item.getprevious() is not None:del item.getparent()[0]
        for _,row in ET.iterparse(archive.open('xl/worksheets/sheet1.xml'),events=['end'],tag='{*}row'):
            number=int(row.get('r'))
            values={}
            for cell in row:
                value=cell.findtext('{*}v')
                if cell.get('t')=='s' and value is not None:value=strings[int(value)]
                if cell.get('t')=='inlineStr':value=''.join(t.text or '' for t in cell.findall('.//{*}t'))
                values[re.sub(r'\d+','',cell.get('r'))]=value
            yield number,values
            row.clear()
            while row.getprevious() is not None:del row.getparent()[0]

def bounds(points):
    return [min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook',type=Path)
    parser.add_argument('--dist',type=Path,default=Path(__file__).resolve().parent/'dist')
    args=parser.parse_args()
    grouped=defaultdict(lambda:defaultdict(list));source_counts=Counter();colors=Counter();shapes=Counter();skipped=[]
    columns={'E':'n','D':'ID','F':'Construction Status','G':'Type','H':'Specification',
             'I':'Owner','J':'Owner Alias','K':'ORO Alias','L':'Equipment(s)'}
    for number,row in rows(args.workbook):
        if number==4:
            assert row.get('G')=='Type' and row.get('I')=='Owner' and row.get('L')=='Equipment(s)'
            assert row.get('M')=='Longitude (degrees)' and row.get('N')=='Latitude (degrees)'
        if number<5:continue
        group=owner_group(row.get('I'));source_counts[group]+=1
        try:
            lng,lat=float(row['M']),float(row['N'])
            assert math.isfinite(lng) and math.isfinite(lat) and -180<=lng<=180 and -90<=lat<=90 and (lng!=0 or lat!=0)
        except (KeyError,ValueError,TypeError,AssertionError):skipped.append(number);continue
        properties={key:str(row[col]).strip() for col,key in columns.items() if row.get(col) not in (None,'')}
        properties['n']=properties.get('n') or str(row.get('B') or row.get('A') or '')
        properties['_color']=color_for(row.get('L'),row.get('I'))
        color=properties['_color'];colors[color]+=1;shapes['square-circle' if normalize(row.get('G'))=='manhole' else 'square']+=1
        shard=f'{math.floor(lng*4)}_{math.floor(lat*4)}'
        grouped[group][shard].append([properties,[lng,lat]])
    manifest_path=args.dist/'layers.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    layers=[];keep=set()
    for group,name,color_name in [('oro','ORO','orange'),('oroc','OROC','pink'),('third-party','3th Party','blue')]:
        layer_id='camerete-'+group;shards=[];all_bounds=[]
        for shard,items in sorted(grouped[group].items()):
            filename=f'layers/{layer_id}-{shard}.json.gz';path=args.dist/filename
            blob=gzip.compress(json.dumps({'p':items},ensure_ascii=False,separators=(',',':')).encode(),compresslevel=6,mtime=0)
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(blob);keep.add(filename)
            extent=bounds([item[1] for item in items]);all_bounds.extend([extent[:2],extent[2:]])
            shards.append({'file':filename,'features':len(items),'bytes':len(blob),'bounds':extent})
        assert shards,'Expected nonempty Camerete layer: '+group
        count=sum(s['features'] for s in shards)
        layers.append({'id':layer_id,'name':name,'group':'Camerete','features':count,'sourceFeatures':source_counts[group],
                       'skipped':source_counts[group]-count,'geometryTypes':{'Point':count},'bytes':sum(s['bytes'] for s in shards),
                       'source':args.workbook.name,'bounds':bounds(all_bounds),'color':COLORS[color_name],'shards':shards})
    for layer in manifest['layers']:
        if layer['group']=='Camerete':
            for shard in layer.get('shards',[layer]):
                if shard.get('file') not in keep:(args.dist/shard['file']).unlink(missing_ok=True)
    manifest['layers']=[l for l in manifest['layers'] if l['group']!='Camerete']+layers
    for key in ['features','bytes','skipped']:manifest['totals'][key]=sum(l.get(key,0) for l in manifest['layers'])
    manifest['totals']['layers']=len(manifest['layers'])
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'sourceRecords':sum(source_counts.values()),'layers':{l['name']:l['features'] for l in layers},
                     'skippedRows':skipped,'colors':dict(colors),'symbols':dict(shapes)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
