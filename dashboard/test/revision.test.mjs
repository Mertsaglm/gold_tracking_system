import test from 'node:test';
import assert from 'node:assert/strict';
import {freshness,candidatePanel,operatingPanel} from '../public/insights.js';

const snapshot=()=>({generated_at:'2026-09-25T16:47:00Z',monitoring:{phase:'valuation',
  calendar:{available:true,years:['2026'],full_days:[],half_days:[]},
  observation_window:{open:'10:15',close:'20:00',half_day_close:'20:00'},entry_window:{open:'10:15',close:'17:45',half_day_close:'12:15'}}});
test('overnight/weekend age is compared with expected observation, not wall time',()=>{
  const s=snapshot();assert.equal(freshness(s,Date.parse('2026-09-26T15:00:00Z')).stale,false);
  s.generated_at='2026-09-25T14:31:00Z';assert.equal(freshness(s,Date.parse('2026-09-26T15:00:00Z')).stale,true);
  s.generated_at='2026-09-26T19:00:00Z';assert.equal(freshness(s,Date.parse('2026-09-26T15:00:00Z')).stale,true);
});
test('candidate capital is explicitly excluded from wealth and zeros stay visible',()=>{
  const c={name:'<test>',strategy:{equity_try:50000},benchmark:{equity_try:49900},feedback:{twr_pct:0},evidence:{periods:0,minimum_periods:24},status:'Deneme'};
  const html=candidatePanel({budget:{initial_try:50000},candidates:[c]});
  assert.match(html,/50.000 TL/);assert.match(html,/0%/);assert.match(html,/0 \/ 24/);
  assert.match(html,/toplam servete eklenmez/);assert.ok(!html.includes('<test>'));
  assert.match(operatingPanel({...snapshot(),strategy:{account_fees_try:0},risk_control:{reasons:[],multiplier:.5}}),/Yalnız değerleme/);
});

import {combinedExposure,exposurePanel} from '../public/insights.js';
test('joint exposure counts only actual main books and refuses unknown values',()=>{
 const now=Date.parse('2026-09-25T17:00:00Z');
 const base={...snapshot(),account_id:'paper-new',strategy:{equity_try:50000,valuation_complete:true,positions:[]},risk_factors:{}};
 const bist=structuredClone(base),gold=structuredClone(base);
 bist.risk_factors.TRALT={factor:'gold_related',label:'Altın üreticisi'};
 gold.risk_factors.GRAM={factor:'gold_direct',label:'Gram'};
 bist.strategy.positions=[{symbol:'TRALT',value_try:5000},{symbol:'THYAO',value_try:10000}];
 gold.strategy.positions=[{symbol:'GRAM',value_try:20000}];
 bist.candidates=[{strategy:{equity_try:999999,positions:[{symbol:'TRALT',value_try:999999}]}}];
 const r=combinedExposure({bist,gold},now);
 assert.equal(r.total_try,100000);assert.equal(r.share_pct,25);assert.equal(r.review_required,true);
 assert.match(exposurePanel({bist,gold},now),/25%/);
 assert.equal(combinedExposure({bist},now).share_pct,null);
 gold.account_id='old';assert.equal(combinedExposure({bist,gold},now).share_pct,null);
 gold.account_id='paper-new';gold.strategy.positions[0].value_try=null;
 assert.equal(combinedExposure({bist,gold},now).complete,false);
 gold.strategy.positions[0].value_try=20000;gold.generated_at='2026-09-24T16:00:00Z';
 assert.equal(combinedExposure({bist,gold},now).complete,false);
});
