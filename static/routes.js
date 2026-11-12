/* Pure route parsing shared by startup, sign-in and report links. */
'use strict';
(function(root){
  const routes=new Set(['overview','reports','review','registry','agent','effect','settings']);
  const reportRoutes=new Set(['reports','review']);
  const validId=value=>Number.isSafeInteger(value)&&value>0;
  function parse(hash=''){
    const [path,query='']=String(hash).replace(/^#/,'').split('?');
    const parts=path.split('/');
    const route=routes.has(parts[0])?parts[0]:'overview';
    const candidate=/^\d+$/.test(parts[1]||'')?Number(parts[1]):null;
    const reportId=parts.length===2&&reportRoutes.has(route)&&validId(candidate)?candidate:null;
    const validPath=parts.length===1||reportId!==null;
    return {route:validPath?route:'overview',reportId:validPath?reportId:null,guide:validPath&&reportId!==null&&new URLSearchParams(query).get('guide')==='1'};
  }
  function format(route,reportId=null,guide=false){
    route=routes.has(route)?route:'overview';
    const detail=reportRoutes.has(route)&&validId(reportId);
    return '#'+route+(detail?'/'+reportId:'')+(detail&&guide?'?guide=1':'');
  }
  root.FoodSaveRoutes=Object.freeze({parse,format});
  if(typeof module!=='undefined'&&module.exports)module.exports=root.FoodSaveRoutes;
})(globalThis);
