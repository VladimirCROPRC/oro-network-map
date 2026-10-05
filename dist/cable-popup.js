function cablePopup(feature) {
  const p=feature.properties||{},escape=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const structure=(type,id)=>[type,id].filter(value=>value!==undefined&&value!==null&&value!=="").join(" · ");
  const rows=[["Proprietar",p.pr],["Status",p.st],["Tip",p.tp],["Structură capăt A",structure(p.ta,p.ia)],["Structură capăt Z",structure(p.tz,p.iz)],["Cabluri",p.cb]];
  return '<div class="cable-popup-title">'+escape(p.n||"Cablu")+'</div><table class="cable-popup-table"><tbody>'+rows.map(([label,value])=>'<tr><th scope="row">'+escape(label)+'</th><td>'+escape(value===undefined||value===null||value===""?"—":value)+'</td></tr>').join("")+'</tbody></table>';
}
