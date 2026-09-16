import test from 'node:test';
import assert from 'node:assert/strict';
import {decisionDetail,weeklyPanel,funnelPanel,riskPanel,evidencePanel} from '../public/insights.js';

test('decision details show real fees, zero values and escaped history',()=>{
 const html=decisionDetail({stop:95,target:120,detail:{quantity:'2',notional_try:200,fee_try:0,stop_risk_try:10,target_net_try:40,basis:'Sanal işlem'},
  change:{items:[{label:'Gerekçe',before:'<script>bad()</script>',after:'AL'}]}});
 assert.match(html,/200 TL/);assert.match(html,/0 TL/);assert.match(html,/10 TL/);
 assert.ok(!html.includes('<script>'));assert.match(html,/&lt;script&gt;/);
});
test('unknown risk and evidence stay unknown; contributions are separately labelled',()=>{
 const risk=riskPanel({risk:{stop_risk_try:null,stop_risk_pct:null,limit_pct:5,stress:[{fall_pct:10,loss_try:null}],missing:['AAA']}});
 assert.match(risk,/Değerleme eksik/);assert.ok(!risk.includes('0 TL'));
 const weekly=weeklyPanel({weekly:{ready:true,contributions_try:5000,investment_result_try:-10,fees_try:10,excess_try:null,max_drawdown_pct:-1}});
 assert.match(weekly,/5.000 TL/);assert.match(weekly,/-10 TL/);
 const proof=evidencePanel({feedback:{evidence:{periods:0,minimum_periods:24,lower_95_pct:null,status:'yetersiz'}}});
 assert.match(proof,/Henüz ölçülemiyor/);
 assert.equal(decisionDetail({}), '');assert.equal(funnelPanel({}), '');
});
