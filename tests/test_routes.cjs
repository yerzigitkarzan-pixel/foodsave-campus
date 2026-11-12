'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const routes=require('../static/routes.js');

test('existing pages remain valid and report links round-trip with the guide',()=>{
  for(const route of ['overview','reports','review','registry','agent','effect','settings']){
    assert.deepEqual(routes.parse(routes.format(route)),{route,reportId:null,guide:false});
  }
  for(const route of ['reports','review']){
    for(const id of [1,22,Number.MAX_SAFE_INTEGER]){
      const expected={route,reportId:id,guide:true};
      assert.deepEqual(routes.parse(routes.format(route,id,true)),expected);
    }
  }
});
test('malformed report identifiers cannot become a different report request',()=>{
  for(const hash of ['#reports/-1','#reports/0','#reports/1.5','#reports/22/entries','#reports/9007199254740992','#registry/22']){
    assert.deepEqual(routes.parse(hash),{route:'overview',reportId:null,guide:false});
  }
  assert.deepEqual(routes.parse('#reports/22?guide=0'),{route:'reports',reportId:22,guide:false});
  assert.equal(routes.format('unknown',22,true),'#overview');
});
