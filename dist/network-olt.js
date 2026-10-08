(function(){
'use strict';
const DATA_VERSION='20261008-integrated-3';
let fiberAlarms=[],oltAlarmAliases={};
function alarmOltName(name){const value=name.trim().toUpperCase();return (oltAlarmAliases[value]||value).trim().toUpperCase()}
function selectAlarmOlts(){if(!selectedData)return;for(const olt of selectedData.olts){if(olt.ports.some(p=>alarmsForPort(olt.name,p.port).length))selectedOlts.add(olt.name)}}
function alarmsForPort(olt,port){const bits=port.replace(/^Sl\.\s*/i,'').split('/').map(x=>/^\d+$/.test(x)?String(Number(x)):x);return fiberAlarms.filter(a=>alarmOltName(a.olt)===alarmOltName(olt)&&(bits.length===2?a.frame==='0'&&bits[0]===a.slot&&bits[1]===a.port:bits.length===3&&bits[0]===a.frame&&bits[1]===a.slot&&bits[2]===a.port))}
function activePortAlarms(olt,port){return alarmsForPort(olt,port).filter(a=>!a.cleared)}
function portOntCount(olt,port){return new Set(activePortAlarms(olt,port).filter(a=>a.kind==='ONT').map((a,i)=>a.onu==null?'unknown-'+i:String(a.onu))).size}
function portIsDown(olt,port){return downPorts.has(portKey(olt,port))||activePortAlarms(olt,port).some(a=>a.kind==='LOS')||portOntCount(olt,port)>=2}
function alarmTime(value){
 if(value==null||value===''||value==='--')return null;
 if(typeof value==='number'||/^\d{10,13}$/.test(String(value))){const n=Number(value);return n>0?(n<1e12?n*1000:n):null}
 const raw=String(value).trim(),local=raw.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?:\s+(DST|STD|ST))?$/);
 if(local){
  const [year,month,day,hour,minute,second]=local.slice(1,7).map(Number),target=Date.UTC(year,month-1,day,hour,minute,second);
  if(local[7]==='DST')return target-3*3600000;
  if(local[7]==='STD')return target-2*3600000;
  const formatter=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Bucharest',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  let epoch=target;for(let i=0;i<2;i++){const parts=Object.fromEntries(formatter.formatToParts(new Date(epoch)).map(p=>[p.type,p.value]));const wall=Date.UTC(+parts.year,+parts.month-1,+parts.day,+parts.hour,+parts.minute,+parts.second);epoch+=target-wall}return epoch;
 }
 const parsed=Date.parse(raw);return Number.isFinite(parsed)?parsed:null;
}
function latestAlarmTime(alarms,field){const values=alarms.map(a=>alarmTime(a[field])).filter(t=>t!==null);return values.length?Math.max(...values):null}
function displayAlarmTime(value){return value===null?'—':new Intl.DateTimeFormat('ro-RO',{timeZone:'Europe/Bucharest',dateStyle:'short',timeStyle:'medium'}).format(new Date(value))}
function portAlarmStyle(olt,port){
 const alarms=activePortAlarms(olt,port),last=latestAlarmTime(alarms,'occurred');
 if(downPorts.has(portKey(olt,port)))return {rank:4,color:'#ef4444'};
 if(portOntCount(olt,port)===1&&!alarms.some(a=>a.kind==='LOS'))return {rank:2,color:'#f97316'};
 if(alarms.length&&last!==null&&Date.now()-last>3*86400000)return {rank:3,color:'#3b82f6'};
 if(alarms.some(a=>a.kind==='LOS')||portOntCount(olt,port)>=2)return {rank:4,color:'#ef4444'};
 if(portOntCount(olt,port)===1)return {rank:2,color:'#f97316'};
 return {rank:0,color:'#22c55e'};
}

const $=id=>document.getElementById('olt-'+id),esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let index=[],mode='sites',selected=null,selectedData=null,request=0;
let selectedOlts=new Set(),selectedOdbPorts=new Set(),downPorts=new Set(),dpMap=null,dpMarkers=null,odbMarkers=null,blinkTimer=null,blinkEnabled=true,redMarkers=[],onlyDown=false;
let siteMarker=null,cableGroups=null,cableVisible=new Map(),cableRun=0,cableTimer=null,cableManifestPromise=null;
let measuring=false,measurePoints=[],measureLayer=null;
const CABLE_SOURCE='https://oro.proconect.online/';
const dpNumbers=aliases=>Array.from(new Set(aliases.flatMap(alias=>Array.from(alias.matchAll(/DP[\s_-]*(\d+)/gi),m=>'DP'+m[1])))).sort(natural);
const natural=(a,b)=>a.localeCompare(b,'ro',{numeric:true,sensitivity:'base'});
const portKey=(olt,port)=>JSON.stringify([olt,port]);
const coordinateKey=point=>JSON.stringify([point.lat,point.lng]);
function popupAttributes(point){return 'ORO-C Alias: '+esc(point.orocAlias||'—')+'<br>Node code: '+esc(point.nodeCode||'—')+'<br>'}
function locationLinks(lat,lng){
 const point=encodeURIComponent(lat+','+lng);
 return '<div class="location-links"><a href="https://www.google.com/maps/search/?api=1&query='+point+'" target="_blank" rel="noopener noreferrer">Google Maps ↗</a><a href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint='+point+'" target="_blank" rel="noopener noreferrer">Street View ↗</a></div>';
}
function disposeMap(){
 clearInterval(blinkTimer);blinkTimer=null;redMarkers=[];
 for(const layer of [dpMarkers,odbMarkers,siteMarker,measureLayer])if(layer)window.NetworkMapBridge.map.removeLayer(layer);
 dpMap=null;dpMarkers=null;odbMarkers=null;siteMarker=null;measureLayer=null;$('port-panel').innerHTML='';
}
function renderResults(){
 const q=$('search').value.trim().toUpperCase();
 const matches=index.filter(s=>(mode==='sites'?!!s.code:!s.code)&&(!q||(s.code+' '+s.name).toUpperCase().includes(q))).sort((a,b)=>Number(b.code===q)-Number(a.code===q)||Number(!!b.olts)-Number(!!a.olts)||natural(a.code||a.name,b.code||b.name));
 $('search-count').textContent=matches.length.toLocaleString('ro')+' rezultate'+(matches.length>100?' · primele 100 afișate':'');
 $('results').innerHTML=matches.slice(0,100).map(s=>`<button class="result ${selected?.id===s.id?'selected':''}" type="button" data-id="${s.id}" ${selected?.id===s.id?'aria-current="true"':''}><strong>${esc(s.code||s.name)}</strong>${s.code?`<span class="name">${esc(s.name||'Denumire absentă din lista de site-uri')}</span>`:''}<span class="counts">${s.olts?s.olts+' OLT · '+s.ports.toLocaleString('ro')+' porturi':'Fără OLT în fișierul Excel'}</span></button>`).join('')||'<p class="no-results">Niciun rezultat. Încearcă alt cod sau nume.</p>';
}
async function selectSite(s){
 window.NetworkMapBridge.showPanel('olt');$('search').value=s.code||s.name;mode=s.code?'sites':'unknown';changeMode(mode);const run=++request;disposeMap();selectedOlts.clear();selectedOdbPorts.clear();downPorts.clear();blinkEnabled=true;onlyDown=false;selected=s;selectedData=null;renderResults();location.hash='olt='+encodeURIComponent(s.code||s.name);
 $('detail').innerHTML='<p class="muted">Se încarcă porturile…</p>';
 try{
  const data=s.file?await fetch('olt/'+s.file+'?v='+DATA_VERSION,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json()}):{code:s.code,name:s.name,location:s.location,olts:[]};
  if(run!==request)return;data.location=data.location||s.location||null;selectedData=data;renderDetail();
 }catch{if(run===request)$('detail').innerHTML='<p class="error">Porturile nu au putut fi încărcate. Selectează din nou site-ul.</p>'}
}
function renderDetail(){
 const d=selectedData,ports=d.olts.reduce((n,o)=>n+o.ports.length,0);
 $('detail').innerHTML=`<span class="eyebrow">${d.code?'Site selectat':'OLT fără cod de site'}</span><h1 class="site-title">${esc(d.code||d.name)}</h1>${d.code?`<p class="site-name">${esc(d.name||'Denumire absentă din lista de site-uri')}</p>`:'<p class="site-name">Codul site-ului nu este identificabil din denumirea OLT-ului.</p>'}${d.code&&!d.location?'<p class="note">Coordonatele site-ului lipsesc din lista HTML.</p>':''}<div class="metrics"><div class="metric"><strong>${d.olts.length}</strong><span>OLT-uri</span></div><div class="metric"><strong>${ports.toLocaleString('ro')}</strong><span>Porturi înregistrate</span></div></div>${ports||d.location?'<div class="map-toolbar"><button id="olt-all-olts" class="secondary" type="button">Toate OLT-urile</button><button id="olt-no-olts" class="secondary" type="button">Niciun OLT</button><button id="olt-clear-down" class="secondary" type="button">Resetează DOWN</button><button id="olt-only-down" class="secondary" type="button" aria-pressed="false">Arata doar selectie</button><button id="olt-blink-toggle" class="secondary" type="button" disabled>Stop blink</button></div><div class="map-legend"><span class="map-blue">Site</span><span class="map-green">DP normal</span><span>■ ODB SPL-2</span><span class="map-red">DP cu port DOWN</span><span style="color:#3b82f6">Albastru: &gt;3 zile</span><span style="color:#f97316">Portocaliu: 1 ONT</span></div><div id="olt-dp-map" aria-label="Harta DP-urilor OLT selectate"></div><span id="olt-map-count" hidden></span><span id="olt-cable-status" hidden></span><div class="port-tools"><input id="olt-port-filter" type="search" aria-label="Filtrează porturile" placeholder="Filtrează OLT / placă / port"></div><div id="olt-olt-list"></div>':'<p class="note">Acest site există în lista HTML, dar nu are conexiuni OLT asociate în coloana M a Excelului.</p>'}`;
 if(ports||d.location){
  const portPanel=$('port-panel');portPanel.append($('detail').querySelector('.port-tools'),$('olt-list'));document.querySelector('.olt-workspace').classList.add('has-site');
  initMap();selectAlarmOlts();renderPorts();renderMap(true);$('port-filter').addEventListener('input',renderPorts);
  $('all-olts').addEventListener('click',()=>{selectedData.olts.forEach(o=>selectedOlts.add(o.name));renderPorts();renderMap(true)});
  $('no-olts').addEventListener('click',()=>{selectedOlts.clear();selectedOdbPorts.clear();downPorts.clear();renderPorts();renderMap(false)});
  $('clear-down').addEventListener('click',()=>{downPorts.clear();renderPorts();renderMap(false)});
  $('blink-toggle').addEventListener('click',()=>{blinkEnabled=!blinkEnabled;updateBlink()});
  $('only-down').addEventListener('click',()=>{onlyDown=!onlyDown;$('only-down').setAttribute('aria-pressed',String(onlyDown));$('only-down').classList.toggle('active',onlyDown);renderMap(false)});
  $('olt-list').addEventListener('change',onSelectionChange);
 }
}
function renderPorts(){
 const q=$('port-filter').value.trim().toUpperCase();
 const openOlts=new Map(Array.from($('olt-list').querySelectorAll('details[data-olt]')).map(d=>[d.dataset.olt,d.open]));
 $('olt-list').innerHTML=selectedData.olts.map((o,oi)=>{
  const ports=o.ports.filter(p=>(o.name+' '+p.port+' '+p.speeds.join(' ')).toUpperCase().includes(q));
  if(!ports.length)return '';
  const checked=selectedOlts.has(o.name);
  return `<details class="olt" data-olt="${oi}" ${openOlts.get(String(oi))!==false?'open':''}><summary><strong>${esc(o.name)}</strong><span>${ports.length} porturi</span></summary><label class="olt-select"><input type="checkbox" data-olt-check="${oi}" ${checked?'checked':''}> Afișează DP pentru ${esc(o.name)} pe hartă</label><div class="table-wrap"><table><thead><tr><th>DOWN</th><th>Placă / port</th><th>Viteză</th><th>ODB</th></tr></thead><tbody>${ports.map(p=>{
   const down=portIsDown(o.name,p.port),pi=o.ports.indexOf(p),alarms=alarmsForPort(o.name,p.port),ontCount=portOntCount(o.name,p.port),odbCount=(p.odbs||[]).length;
   return `<tr class="${down?'down-row':''}"><td><label class="down-choice"><input type="checkbox" data-port-check="${pi}" data-olt-index="${oi}" aria-label="DOWN ${esc(o.name)} / ${esc(p.port)}" ${down?'checked':''} ${checked?'':'disabled'}><span>${down?'DOWN':'—'}</span>${ontCount?'<small class="ont-alarm">'+ontCount+' ONT</small>':''}</label></td><td class="port-name">${esc(p.port.replace(/unset/gi,'nespecificat'))}</td><td>${p.speeds.length?p.speeds.map(s=>'<span class="speed">'+esc(s)+'</span>').join(' '):'—'}</td><td><label class="odb-choice"><input type="checkbox" data-odb-check="${pi}" data-olt-index="${oi}" aria-label="Afișează ODB ${esc(o.name)} / ${esc(p.port)}" ${selectedOdbPorts.has(portKey(o.name,p.port))?'checked':''} ${odbCount?'':'disabled'}>${odbCount}</label></td></tr>`;
  }).join('')}</tbody></table></div></details>`;
 }).join('')||'<p class="no-results">Niciun port corespunde filtrului.</p>';
}
function onSelectionChange(event){
 const input=event.target;
 if(input.dataset.oltCheck!==undefined){
  const o=selectedData.olts[Number(input.dataset.oltCheck)];
  if(input.checked)selectedOlts.add(o.name);else{selectedOlts.delete(o.name);o.ports.forEach(p=>{downPorts.delete(portKey(o.name,p.port))})}
  renderPorts();renderMap(true);
 }else if(input.dataset.odbCheck!==undefined){
  const o=selectedData.olts[Number(input.dataset.oltIndex)],p=o.ports[Number(input.dataset.odbCheck)],key=portKey(o.name,p.port);
  input.checked?selectedOdbPorts.add(key):selectedOdbPorts.delete(key);renderPorts();renderMap(true);
 }else if(input.dataset.portCheck!==undefined){
  const o=selectedData.olts[Number(input.dataset.oltIndex)],p=o.ports[Number(input.dataset.portCheck)],key=portKey(o.name,p.port);
  if(input.checked){downPorts.add(key);selectedOdbPorts.add(key)}else downPorts.delete(key);renderPorts();renderMap(true);
 }
}
function initMap(){
 dpMap=window.NetworkMapBridge.map;
 dpMarkers=L.layerGroup().addTo(dpMap);odbMarkers=L.layerGroup().addTo(dpMap);
 if(selectedData.location){
  siteMarker=L.circleMarker(selectedData.location,{radius:9,color:'#f4faff',weight:2,fillColor:'#2388ff',fillOpacity:1}).addTo(dpMap);
  siteMarker.bindPopup('<strong>'+esc(selectedData.code||selectedData.name)+'</strong><br>'+esc(selectedData.name)+locationLinks(...selectedData.location));
  siteMarker.bindTooltip(esc(selectedData.code||selectedData.name),{permanent:true,direction:'top',className:'site-code-label'});
  dpMap.setView(selectedData.location,14);
  window.NetworkMapBridge.focusSite(selectedData.location,selectedData.code||selectedData.name).then(()=>{dpMarkers?.eachLayer(marker=>marker.bringToFront());siteMarker?.bringToFront()});
 }
 dpMap.invalidateSize();
}
function renderMap(fit){
 clearInterval(blinkTimer);blinkTimer=null;redMarkers=[];dpMarkers.clearLayers();const points=new Map();let missing=0,downMissing=0;
 for(const o of selectedData.olts){
  if(!selectedOlts.has(o.name))continue;
  for(const p of o.ports){
   const down=portIsDown(o.name,p.port),style=portAlarmStyle(o.name,p.port);
   if(!p.dps?.length){missing++;if(down)downMissing++}
   for(const dp of p.dps||[]){
    const key=coordinateKey(dp);let point=points.get(key);
    if(!point){point={lat:dp.lat,lng:dp.lng,down:false,rank:0,color:'#22c55e',connections:new Map()};points.set(key,point)}
    point.down=point.down||down;if(style.rank>point.rank){point.rank=style.rank;point.color=style.color}
    point.connections.set(JSON.stringify([o.name,p.port,dp.alias]),{olt:o.name,port:p.port,alias:dp.alias,orocAlias:dp.orocAlias,nodeCode:dp.nodeCode,down});
   }
  }
 }
 for(const point of points.values()){
  if(onlyDown&&!point.down&&point.rank===0)continue;
  const color=point.color;
  const marker=L.circleMarker([point.lat,point.lng],{radius:7,weight:2,color:'#07151e',fillColor:color,fillOpacity:.95,down:point.down}).addTo(dpMarkers);
  marker.bindPopup('<strong>DP / splitter nivel 1</strong><div class="dp-popup">'+Array.from(point.connections.values()).map(c=>`<div><strong>${esc(c.alias||'Alias lipsă')}</strong><br>${popupAttributes(c)}${esc(c.olt)} / ${esc(c.port)}${c.down?' <b class="down-label">DOWN</b>':''}</div>`).join('')+'</div>'+locationLinks(point.lat,point.lng),{maxWidth:360});
  const numbers=dpNumbers(Array.from(point.connections.values()).map(c=>c.alias));
  if(numbers.length)marker.bindTooltip(esc(numbers.join(', ')),{permanent:true,direction:'right',offset:[8,0],className:'dp-number-label'+(point.down?' dp-number-down':'')});
  if(point.down)redMarkers.push(marker);
 }
 const odbExtent=renderOdbs();
 if(fit&&(points.size||odbExtent.length)){const extent=Array.from(points.values()).map(p=>[p.lat,p.lng]).concat(odbExtent);if(selectedData.location)extent.push(selectedData.location);dpMap.fitBounds(L.latLngBounds(extent),window.NetworkMapBridge.fitOptions())}
 siteMarker?.bringToFront();
 $('map-count').textContent=selectedOlts.size?`${onlyDown?redMarkers.length:points.size} DP pe hartă · ${redMarkers.length} DOWN${missing?' · '+missing+' porturi fără DP SPL-1 cu coordonate':''}${downMissing?' ('+downMissing+' marcate DOWN)':''}`:'Bifează un OLT pentru a afișa DP-urile pe hartă.';
 updateBlink();
}
function renderOdbs(){
 odbMarkers.clearLayers();const points=new Map();
 for(const o of selectedData.olts){
  for(const p of o.ports){
   if(!selectedOdbPorts.has(portKey(o.name,p.port)))continue;
   const style=portAlarmStyle(o.name,p.port);
   if(onlyDown&&!portIsDown(o.name,p.port)&&style.rank===0)continue;
   for(const odb of p.odbs||[]){
    const key=coordinateKey(odb);let point=points.get(key);
    if(!point){point={lat:odb.lat,lng:odb.lng,rank:0,color:'#22c55e',connections:new Map()};points.set(key,point)}
    if(style.rank>point.rank){point.rank=style.rank;point.color=style.color}
    point.connections.set(JSON.stringify([o.name,p.port,odb.id,odb.alias]),{olt:o.name,port:p.port,alias:odb.alias,id:odb.id,orocAlias:odb.orocAlias,nodeCode:odb.nodeCode});
   }
  }
 }
 for(const point of points.values()){
  const connections=Array.from(point.connections.values());
  const marker=L.marker([point.lat,point.lng],{icon:L.divIcon({className:'odb-map-icon',html:'<span style="background:'+point.color+'"></span>',iconSize:[24,24],iconAnchor:[12,12]})}).addTo(odbMarkers);
  marker.bindPopup('<strong>ODB / splitter nivel 2</strong><div class="dp-popup">'+connections.map(c=>'<div><strong>'+esc(c.alias||'Alias lipsă')+'</strong><br>'+popupAttributes(c)+esc(c.olt)+' / '+esc(c.port)+'</div>').join('')+'</div><small>Culoarea indică starea portului OLT.</small>'+locationLinks(point.lat,point.lng),{maxWidth:360});
  const labels=Array.from(new Set(connections.flatMap(c=>Array.from(c.alias.matchAll(/ODB[\s_-]*(\d+)/gi),m=>'ODB'+m[1]))));
  marker.bindTooltip(esc(labels.join(', ')||'SPL-2'),{direction:'top',permanent:true,className:'odb-number-label'});
 }
 return Array.from(points.values()).map(p=>[p.lat,p.lng]);
}
function updateBlink(){
 clearInterval(blinkTimer);blinkTimer=null;redMarkers.forEach(m=>m.setStyle({fillOpacity:.95,opacity:1}));
 $('blink-toggle').textContent=blinkEnabled?'Stop blink':'Pornește blink';$('blink-toggle').disabled=!redMarkers.length;
 if(blinkEnabled&&redMarkers.length){let bright=true;blinkTimer=setInterval(()=>{bright=!bright;redMarkers.forEach(m=>m.setStyle({fillOpacity:bright?.95:.2,opacity:bright?1:.35}))},700)}
}
window.NetworkOlt={selectCode:async code=>{await indexReady;const match=index.find(s=>s.code?.toUpperCase()===String(code).toUpperCase());if(match)await selectSite(match);else{window.NetworkMapBridge.showPanel('olt');$('search').value='';changeMode('sites');$('search-count').textContent='Locația '+code+' nu are un cod de site OLT identificat. Caută site-ul sau denumirea OLT.'}},getSelection:()=>({selectedData,selectedOlts,selectedOdbPorts,downPorts,dpMarkers,odbMarkers})};
$('search').addEventListener('input',renderResults);
$('results').addEventListener('click',e=>{const b=e.target.closest('[data-id]');if(b)selectSite(index.find(s=>s.id===b.dataset.id))});
function changeMode(value){mode=value;$('sites-tab').classList.toggle('selected',mode==='sites');$('unknown-tab').classList.toggle('selected',mode==='unknown');renderResults()}
$('sites-tab').addEventListener('click',()=>changeMode('sites'));
$('unknown-tab').addEventListener('click',()=>changeMode('unknown'));
let finishIndex;const indexReady=new Promise(resolve=>finishIndex=resolve);
fetch('olt/index.json?v='+DATA_VERSION,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(data=>{
 index=data.sites;finishIndex();renderResults();const hash=decodeURIComponent(location.hash.slice(1).replace(/^olt=/,''));const s=hash?index.find(s=>s.code===hash||s.name===hash):null;
 if(s){$('search').value=s.code||s.name;changeMode(s.code?'sites':'unknown');selectSite(s)}
}).catch(()=>{finishIndex();$('search-count').textContent='Datele nu au putut fi încărcate. Reîncarcă pagina.'});


})();
