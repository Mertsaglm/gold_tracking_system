import test from 'node:test';
import assert from 'node:assert/strict';
import {authorized, validate, collect, readRemote} from '../lib/status.mjs';
import handler from '../api/status.js';

const snapshot = market => ({schema_version:2,market,mode:'paper',generated_at:'2026-09-15T10:00:00Z',decisions:[],strategy:{cash_try:5000}});
test('private endpoint refuses missing or wrong passwords before fetching', async()=>{
  assert.equal(authorized(undefined,'secret'),false);
  assert.equal(authorized('Basic '+Buffer.from('mert:wrong').toString('base64'),'secret'),false);
  assert.equal(authorized('Basic '+Buffer.from('mert:güvenli').toString('base64'),'güvenli'),true);
  const old=process.env.ADVISOR_DASHBOARD_PASSWORD; delete process.env.ADVISOR_DASHBOARD_PASSWORD;
  let code,body; const res={setHeader(){},status(n){code=n;return this;},json(x){body=x;}};
  await handler({method:'GET',headers:{}},res);assert.equal(code,503);assert.equal(body.portfolios,undefined);
  process.env.ADVISOR_DASHBOARD_PASSWORD='secret';
  await handler({method:'GET',headers:{}},res);assert.equal(code,401);
  if(old===undefined)delete process.env.ADVISOR_DASHBOARD_PASSWORD;else process.env.ADVISOR_DASHBOARD_PASSWORD=old;
});
test('a corrupt or unavailable account cannot hide the healthy account',async()=>{
  const data=await collect(async m=>m==='bist'?{bad:true}:snapshot(m));
  assert.equal(data.portfolios.gold.strategy.cash_try,5000); assert.ok(data.errors.bist);
  assert.throws(()=>validate({...snapshot('gold'),mode:'live'},'gold'));
});
test('GitHub credentials stay at a fixed server-side destination',async()=>{
  let called=false;
  await assert.rejects(()=>readRemote('bist',{fetcher:()=>{called=true;}}),/okuma bağlantısı/);assert.equal(called,false);
  const s=await readRemote('bist',{token:'fixture-only',fetcher:async(url,opts)=>{
    assert.equal(new URL(url).hostname,'api.github.com');assert.equal(opts.headers.Authorization,'Bearer fixture-only');
    assert.equal(opts.redirect,'error');return new Response(JSON.stringify(snapshot('bist')));
  }});assert.equal(s.market,'bist');assert.equal(JSON.stringify(s).includes('fixture-only'),false);
});
test('only read operations are offered by the API',async()=>{
  let code;const res={setHeader(){},status(n){code=n;return this;},json(){}};
  await handler({method:'POST',headers:{}},res); assert.equal(code,405);
});
