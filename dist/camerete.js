// Canvas symbols keep large Camerete layers responsive while retaining touch targets.
L.Canvas.include({
  _updateCamereta(layer) {
    if (!this._drawing || layer._empty()) return;
    const point=layer._point, radius=layer._radius, context=this._ctx;
    context.beginPath();
    context.rect(point.x-radius,point.y-radius,2*radius,2*radius);
    this._fillStroke(context,layer);
    if (layer.options.manhole) {
      context.save();
      context.beginPath();
      context.arc(point.x,point.y,radius*.53,0,Math.PI*2);
      context.strokeStyle="#061017";
      context.lineWidth=1.5;
      context.globalAlpha=1;
      context.setLineDash([]);
      context.stroke();
      context.restore();
    }
  }
});
const CameretaMarker=L.CircleMarker.extend({
  _updatePath(){this._renderer._updateCamereta(this);},
  _clickTolerance(){return L.CircleMarker.prototype._clickTolerance.call(this)+(L.Browser.touch?8:4);},
  _containsPoint(point){
    const tolerance=this._radius+this._clickTolerance();
    return Math.abs(point.x-this._point.x)<=tolerance&&Math.abs(point.y-this._point.y)<=tolerance;
  }
});
function cameretaMarker(feature,latlng){
  return new CameretaMarker(latlng,{
    radius:6,color:"#061017",weight:1.5,
    fillColor:feature.properties._color,fillOpacity:1,
    manhole:String(feature.properties.Type||"").trim().toLowerCase()==="manhole"
  });
}
