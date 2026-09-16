import {decisionDetail, funnelPanel, weeklyPanel, riskPanel, evidencePanel} from './insights.js';
const $ = s => document.querySelector(s);
const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = (n, digits=2) => n == null || !Number.isFinite(Number(n)) ? '—' : Number(n).toLocaleString('tr-TR', {minimumFractionDigits:digits, maximumFractionDigits:digits});
const money = n => n == null ? '—' : `${num(n)} ₺`;
const pct = n => n == null ? '—' : `${n > 0 ? '+' : ''}${num(n)}%`;
const tone = n => n == null || n === 0 ? 'neutral' : n > 0 ? 'positive' : 'negative';
const date = (s, time=false) => s && Number.isFinite(Date.parse(s)) ? new Date(s).toLocaleString('tr-TR', {day:'2-digit',month:'short', ...(time ? {hour:'2-digit',minute:'2-digit'} : {year:'numeric'}), timeZone:'Europe/Istanbul'}) : '—';
const trDay = s => new Date(s).toLocaleDateString('sv-SE', {timeZone:'Europe/Istanbul'});
const safeURL = s => {try {const u=new URL(s);return u.protocol === 'https:' ? esc(u.href) : '#';} catch {return '#';}};
const badge = (text, kind='') => `<span class="badge ${kind}">${esc(text)}</span>`;
const tag = action => `<span class="decision-tag ${action==='AL'?'buy':action==='SAT'?'sell':action==='BEKLE'?'wait':''}">${esc(action)}</span>`;
const empty = (title, text='') => `<div class="empty"><strong>${esc(title)}</strong>${esc(text)}</div>`;
let response = null, market = 'bist', view = 'overview', authorization = '', search = '', actionFilter = 'all';
const pages = {
  overview: ['Genel bakış', 'Birikiminin büyük resmi.', 'Kararları, paranın nerede olduğunu ve sistemin ne öğrendiğini birlikte gör.'],
  decisions: ['Kararlar', 'Bugün ne yapmak mantıklı?', 'Al, sat, tut veya bekle. Her kararın kısa gerekçesi ve fiyat referansı burada.'],
  portfolio: ['Sanal portföy', 'Paran nerede, sonuç ne?', 'Adetleri, gramları, nakdi ve işlem maliyetlerini tek tek takip et.'],
  learning: ['Gelişim karnesi', 'Model ne kadar isabetli?', 'Modelin geçmiş sınavı, gerçekleşen tahminler ve öğrendiği hatalar.'],
  legacy: ['Geçmiş raporlar', 'Nereden başladığımızı unutma.', 'Önceki analizlerin karnesi. Eski sonuçlar yeni sanal hesaplarla karıştırılmaz.']
};

function current() { return response?.portfolios?.[market]; }
function fresh(s) { return s && Date.now()-Date.parse(s.generated_at) < 1000*60*90; }
function accountCard(s, m) {
  const title = m==='bist' ? 'BIST portföyü' : 'Altın portföyü';
  const held = s?.strategy?.positions?.length || 0;
  return `<button class="account-card ${m==='gold'?'gold':''} ${m===market?'selected':''}" data-market="${m}" aria-pressed="${m===market}">
  <div class="account-top"><span><span class="symbol-icon">${m==='bist'?'↗':'◇'}</span> ${title}</span>${badge(s ? (s.health.quote_coverage ? 'Sanal hesap' : 'Fiyat bekleniyor') : 'Bağlantı eksik', s?.health.quote_coverage ? '' : 'warn')}</div>
  <div class="account-amount">${num(s?.strategy?.equity_try)}<small>TL</small></div>
  <div class="account-bottom"><span class="${tone(s?.strategy?.pnl_try)}">${s ? `${s.strategy.pnl_try > 0 ? '+' : ''}${money(s.strategy.pnl_try)} net sonuç` : 'Veri okunamadı'}</span><span>${held ? `${held} açık pozisyon` : 'Nakit bekliyor'} · Aylık ${num(s?.budget?.monthly_try,0)} TL</span></div></button>`;
}

function hero(s) {
  const ds = s.decisions, executable = ds.filter(d=>d.execution), selected = executable[0] || ds.find(d=>d.action==='SAT') || ds.find(d=>d.action==='AL') || ds.find(d=>d.action==='TUT') || ds[0];
  const titles = {'AL':'Alım için koşullar oluştu.', 'SAT':'Satış zamanı geldi.', 'TUT':'Elindekini tut.', 'BEKLE':'Şu an yeni alım yapma.', 'VERİ BEKLENİYOR':'Fiyatı doğrulamadan alma.'};
  return `<section class="decision-hero ${market==='gold'?'gold':''}"><p class="eyebrow">SİSTEMİN SON KARARI</p>${selected?tag(selected.action):''}<h2>${esc(titles[selected?.action] || 'Yeni analiz bekleniyor.')}</h2><p>${esc(selected?.reasons?.[0] || 'Henüz kayıtlı karar yok.')}</p>${selected?.reasons?.[1]?`<p>${esc(selected.reasons[1])}</p>`:''}<p class="bottom-note">${executable.length ? `${executable.length} sanal işlem kaydedildi.` : 'Bu koşuda yeni sanal işlem yapılmadı.'} ${selected ? esc(selected.symbol==='GRAM'?'İş Bankası gram altın':selected.symbol) : ''}</p></section>`;
}

function lineChart(s) {
  const points = s.history.filter(h => Number.isFinite(h.nav));
  const days = new Set(points.map(p=>trDay(p.at)));
  if (days.size < 2) return '<div class="chart-empty"><strong>Performans eğrisi burada oluşacak.</strong><p>Yeni sanal hesap açıldı. İlk iki günün değerlemesinden sonra sonuçları karşılaştırabilirsin.</p></div>';
  const daily = [...new Map(points.map(p=>[trDay(p.at),p])).values()];
  const rows = daily.map(p=>({...p, strategy:(p.nav-1)*100, baseline:p.benchmark_nav==null?null:(p.benchmark_nav-1)*100}));
  const values=rows.flatMap(p=>[p.strategy,p.baseline]).filter(n=>n!=null), min=Math.min(0,...values), max=Math.max(0,...values), span=Math.max(1,max-min);
  const x=i=>52+i*520/(rows.length-1), y=n=>185-(n-min)*150/span;
  const path=key=>rows.reduce((out,p,i)=>p[key]==null?out:out+`${!out||rows[i-1]?.[key]==null?'M':'L'}${x(i).toFixed(1)},${y(p[key]).toFixed(1)} `,'');
  return `<svg class="chart" viewBox="0 0 610 220" role="img" aria-label="Katkılardan arındırılmış sanal getiri ve al-tut karşılaştırması">${[0,1,2,3].map(i=>{const n=min+i*span/3;return `<line class="grid-line" x1="52" x2="576" y1="${y(n)}" y2="${y(n)}"/><text x="7" y="${y(n)+4}">${num(n,1)}%</text>`;}).join('')}<path class="benchmark-line" d="${path('baseline')}"/><path class="strategy-line" d="${path('strategy')}"/><text x="52" y="211">${esc(date(rows[0].at))}</text><text x="575" y="211" text-anchor="end">${esc(date(rows.at(-1).at))}</text></svg>`;
}

function chartPanel(s) {
  return `<section class="panel"><div class="panel-head"><h2>Birikiminin performansı</h2>${badge('Katkılar hariç','gray')}</div><p class="panel-subtitle">Aynı para ile alıp tutsaydık ne olurdu?</p>${lineChart(s)}<div class="chart-key"><span>Sistemin sanal portföyü</span><span>Aynı bütçeyle al-tut</span></div><div class="stat-row"><div><label>EKLENEN TOPLAM PARA</label><strong>${money(s.strategy.contributed_try)}</strong></div><div><label>NET SONUÇ</label><strong class="${tone(s.strategy.pnl_try)}">${money(s.strategy.pnl_try)}</strong></div><div><label>AL-TUT SONUCU</label><strong class="${tone(s.benchmark.pnl_try)}">${money(s.benchmark.pnl_try)}</strong></div></div></section>`;
}

function decisionRows(s, limit) {
  const ds = s.decisions.filter(d=>(actionFilter==='all'||d.action===actionFilter)&&d.symbol.toLocaleLowerCase('tr').includes(search.toLocaleLowerCase('tr'))).sort((a,b)=>({SAT:0,AL:1,TUT:2,BEKLE:3}[a.action]??4)-({SAT:0,AL:1,TUT:2,BEKLE:3}[b.action]??4));
  if (!ds.length) return empty('Bu filtreyle karar bulunamadı.', 'Aramayı temizleyebilir veya tüm kararları seçebilirsin.');
  return `<div class="table-wrap"><table><thead><tr><th>VARLIK</th><th>KARAR</th><th>KISA GEREKÇE</th><th>REFERANS</th></tr></thead><tbody>${ds.slice(0,limit||ds.length).map(d=>`<tr><td><div class="ticker-title"><span class="ticker-logo">${esc(d.symbol.slice(0,2))}</span><div><strong>${esc(d.symbol==='GRAM'?'Gram altın':d.symbol)}</strong><small>${esc(d.sector?.replaceAll('_',' ')||'')}</small></div></div></td><td>${tag(d.action)}${d.execution?`<small>${esc(d.execution.quantity)} ${market==='gold'?'gram':'adet'} sanal</small>`:''}</td><td class="reason-cell">${esc(d.reasons[0])}${view==='decisions'?d.reasons.slice(1).map(r=>`<small>${esc(r)}</small>`).join('')+decisionDetail(d):''}</td><td>${money(d.price)}<small>${esc(date(s.quotes[d.symbol]?.quoted_at,true))}</small></td></tr>`).join('')}</tbody></table></div>`;
}
function decisionPanel(s, full=false) {
  return `<section class="panel"><div class="panel-head"><h2>${full?'Tüm kararlar':'Karar radarın'}</h2>${full?'<div class="filters"><input id="search" type="search" aria-label="Varlık ara" placeholder="Varlık ara…"><select id="action-filter" aria-label="Karar filtresi"><option value="all">Tüm kararlar</option><option>AL</option><option>SAT</option><option>TUT</option><option>BEKLE</option><option>VERİ BEKLENİYOR</option></select></div>':'<a href="#decisions" class="text-link">Tümünü gör ↗</a>'}</div><div id="decision-table">${decisionRows(s,full?null:5)}</div><div class="note-strip">${s.decisions.length} varlık değerlendirildi · Analiz kapanışı: ${esc(date(s.analysis_date))} · Kararlar sanal hesap içindir.</div></section>`;
}

function metricsPanel(s) {
  return `<section class="panel"><div class="panel-head"><h2>Hesabın özeti</h2></div><div class="panel-body metric-list">${[['Kullanılabilir nakit',money(s.strategy.cash_try)],['Açık pozisyon',`${s.strategy.positions.length} varlık`],['Gerçekleşen sonuç',money(s.strategy.realized_try)], ...(market==='gold'?[['Altın karşılığı',num(s.strategy.gold_equivalent_grams,3)+' gram']]:[]), ['Aylık ek bütçe',money(s.budget.monthly_try)],['Başlangıç',date(s.budget.start_date)]].map(([label,value])=>`<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join('')}</div></section>`;
}
function newsPanel(s) {
  return `<section class="panel"><div class="panel-head"><h2>Kaynağından gündem</h2>${badge('Son 7 gün','gray')}</div><div class="panel-body">${(s.news.upcoming||[]).map(e=>`<a class="feed-item" href="${safeURL(e.url)}" target="_blank" rel="noopener noreferrer"><span>TAKVİM · ${esc(date(e.date))} ↗</span><strong>${esc(e.title)}</strong></a>`).join('')}${s.news.items.length?s.news.items.slice(0,5).map(n=>`<a class="feed-item" href="${safeURL(n.url)}" target="_blank" rel="noopener noreferrer"><span>${esc(n.source)} · ${esc(date(n.published_at))} ↗</span><strong>${esc(n.title)}</strong></a>`).join(''):empty('Güncel haber alınamadı.','Kaynakların durumu aşağıda gösterilir.')}<div class="source-pills">${s.news.sources.map(n=>`<span title="${esc(n.detail||'Kaynak okundu')}">${badge(n.source+(n.ok?' ✓':' · eksik'),n.ok?'gray':'warn')}</span>`).join('')}</div></div><div class="note-strip">${esc(s.news.note)}</div></section>`;
}
function positions(s) {
  return `<section class="panel"><div class="panel-head"><h2>Eldeki varlıklar</h2>${badge(`${s.strategy.positions.length} pozisyon`,'gray')}</div>${s.strategy.positions.length?`<div class="table-wrap"><table><thead><tr><th>VARLIK / MİKTAR</th><th>MALİYET</th><th>BUGÜNKÜ NET DEĞER</th><th>SONUÇ</th><th>SATIŞ SINIRLARI</th></tr></thead><tbody>${s.strategy.positions.map(p=>`<tr><td><strong>${esc(p.symbol)}</strong><small>${esc(p.quantity)} ${market==='gold'?'gram':'adet'}</small></td><td>${money(p.cost_try)}<small>Ort. ${money(p.average_cost)}</small></td><td>${money(p.value_try)}<small>${p.valuation_problem?esc(p.valuation_problem)+' Son bilinen: '+money(p.last_known_value_try):'Satış masrafı dahil'}</small></td><td class="${tone(p.pnl_try)}">${money(p.pnl_try)}</td><td>Zarar ${money(p.stop)}<small>Hedef ${money(p.target)}</small></td></tr>`).join('')}</tbody></table></div>`:empty('Henüz açık pozisyon yok.','Koşullar oluşana kadar para nakitte bekler.')}<div class="note-strip">Temettü alacağı: ${money(s.strategy.receivable_try||0)} · Ödeme tarihi doğrulanmayan alacak harcanabilir nakde eklenmez.</div></section>`;
}
function trades(s) {
  return `<section class="panel"><div class="panel-head"><h2>İşlem defteri</h2><button class="export-button" id="export">Kayıtları indir ↓</button></div>${s.strategy.fills.length?`<div class="table-wrap"><table><thead><tr><th>ZAMAN</th><th>VARLIK / İŞLEM</th><th>MİKTAR × FİYAT</th><th>MASRAF</th><th>FİYAT KAYNAĞI</th></tr></thead><tbody>${[...s.strategy.fills].reverse().map(f=>`<tr><td>${esc(date(f.at,true))}</td><td><strong>${esc(f.symbol)}</strong><small>${f.side==='BUY'?'Sanal alış':'Sanal satış'}</small></td><td>${esc(f.quantity)} × ${money(f.price)}</td><td>${money(f.fee_cents/100)}</td><td>${esc(f.quote.source)}<small>${esc(date(f.quote.quoted_at,true))}</small></td></tr>`).join('')}</tbody></table></div>`:empty('İlk işlem henüz yapılmadı.','Her sanal alış ve satış; zamanı, fiyatı, miktarı ve masrafıyla burada görünecek.')}</section>`;
}
function costs(s) {
  return `<section class="panel"><div class="panel-head"><h2>Fiyat ve maliyet nasıl hesaplanıyor?</h2></div><div class="panel-body body-copy"><ul>${(s.cost_notes||[]).map(n=>`<li>${esc(n)}</li>`).join('')}</ul>${Object.values(s.quotes).slice(0,1).map(q=>`<p><a href="${safeURL(q.url)}" target="_blank" rel="noopener noreferrer">${esc(q.source)} ↗</a> · ${esc(q.note)}</p><p>Kaynak zamanı: ${esc(date(q.quoted_at,true))} · Okunma: ${esc(date(q.observed_at,true))}</p>`).join('')}</div></section>`;
}
function learningPage(s) {
  const e=s.learning.evaluation||{}, f=s.feedback, card=f.scorecard||{};
  return `<div class="learning-stats"><div class="mini-stat"><label>GEÇMİŞTE BAĞIMSIZ DÖNEM</label><strong>${num(e.periods,0)}</strong><p>Örtüşen fiyat hareketleri tekrar başarı sayılmaz.</p></div><div class="mini-stat"><label>ORTALAMA TAHMİN HATASI</label><strong>${num(e.mae_pct)} puan</strong><p>Yüzde puan. Sabit tahminin hatası: ${num(e.baseline_mae_pct)}.</p></div><div class="mini-stat"><label>SONUÇLANAN SANAL TAHMİN</label><strong>${num(card.resolved_forecasts||0,0)}</strong><p>${num(card.independent_periods||0,0)} bağımsız dönem · ${f.roundtrips} kapanmış işlem.</p></div></div><div class="grid"><div><section class="panel"><div class="panel-head"><h2>Modelin sınav sonucu</h2>${badge(s.learning.approved?'Geçmiş sınavı geçti':'Üstünlük kanıtlanmadı',s.learning.approved?'':'warn')}</div><div class="panel-body body-copy"><p>${esc(e.method||'Yeterli veri bekleniyor.')}</p><div class="metric-list"><div class="metric"><span>Al-tut üstü ortalama fark</span><strong>${pct(e.mean_excess_pct)}</strong></div><div class="metric"><span>%95 aralığının alt sınırı</span><strong>${pct(e.lower_95_pct)}</strong></div><div class="metric"><span>Eğitimdeki gün sayısı</span><strong>${num(s.learning.training_dates,0)}</strong></div><div class="metric"><span>Model sürümü</span><strong>${esc(s.learning.id||'—')}</strong></div></div><p>Geçmiş sınav ve yeni sanal işlemler birlikte yeterli kanıt üretmeden tam deneme bütçesi kullanılmaz.</p><h3>Masraf artarsa ne oluyor?</h3>${(e.cost_stress||[]).map(x=>`<div class="metric"><span>Toplam maliyet %${num(x.cost_pct)}</span><strong>${pct(x.mean_excess_pct)} fark</strong></div>`).join('')}</div></section><section class="panel"><div class="panel-head"><h2>Hatalardan öğrenme</h2></div><div class="panel-body body-copy"><p>Her tahmin ${market==='gold'?'20 veri günü':'20 seans'} sonunda çözülür. Gerçekleşen hareket tahminle karşılaştırılır. Yeterli bağımsız dönem birikince ölçülen yanlılık, en fazla 2 yüzde puanlık düzeltmeyle sonraki tahminlere uygulanır.</p><div class="metric"><span>Şu anki hata düzeltmesi</span><strong>${num(card.correction_pct||0)} puan</strong></div><div class="metric"><span>Küçültülmüş risk çarpanı</span><strong>${num(f.risk_multiplier||1)}×</strong></div><p>${esc(card.note||'Yeni sonuçlar birikiyor.')}</p></div></section></div><div class="side-column"><section class="decision-hero"><p class="eyebrow">SİSTEMİN ÇALIŞMA İLKESİ</p><h2>Önce küçük tutarla kanıt.</h2><p>Geçmiş arşiv bir başlangıç. Asıl ölçü, bundan sonra tarih ve fiyatıyla kaydedilen sanal sonuçlar.</p><p class="bottom-note">Tarihsel veri sonradan düzeltilmiş olabilir; bu nedenle geçmiş başarı tek başına yeterli sayılmaz.</p></section><section class="panel"><div class="panel-head"><h2>Testin sınırları</h2></div><div class="panel-body body-copy"><ul>${(s.learning.limitations||[]).map(l=>`<li>${esc(l)}</li>`).join('')}</ul></div></section></div></div>`;
}
function legacyPage(s) {
  return `<section class="panel"><div class="panel-head"><h2>Önceki sistemin karnesi</h2>${badge('V1 arşivi','gray')}</div><p class="panel-subtitle">${esc(s.legacy.note)}</p><div class="table-wrap"><table><thead><tr><th>KAYNAK</th><th>TAHMİN KAYDI</th><th>SONUÇLANAN / GİRİLEN</th><th>ÖLÇÜLEN SONUÇ</th></tr></thead><tbody>${s.legacy.sources.map(r=>`<tr><td><strong>${esc(r.source)}</strong><small>${esc(r.decision||'')}</small></td><td>${num(r.decisions,0)}</td><td>${num(r.entered??r.resolved,0)}</td><td>${pct(r.average_trade_return_pct??r.gram_effect_pct)}<small>${market==='bist'?'İşlem ortalaması':'Gram etkisi'} · Portföy getirisi değildir</small></td></tr>`).join('')}</tbody></table></div><div class="note-strip">Replay verisi canlı kararlardan ayrı gösterilir. Küçük örneklem ve seçilmiş işlemler başarı iddiasını sınırlıyor.</div></section><section class="panel"><div class="panel-head"><h2>Son eski analizlerin gerekçeleri</h2></div>${s.legacy.recent.length?s.legacy.recent.map(d=>`<details><summary>${esc(d.symbol)} · ${esc(d.signal)} · ${esc(d.action)}</summary><p class="body-copy">${esc(d.thesis)}</p><p class="body-copy">Risk: ${esc(d.key_risk)}</p><p class="body-copy">Eski LLM yorumu. Haber dayanağı ayrıca doğrulanmalıdır.</p></details>`).join(''):empty('Eski strateji özeti yukarıdaki tabloda.','Ayrıntılı günlük raporlar proje içindeki reports klasöründe korunuyor.')}</section>`;
}

function renderContent() {
  const s=current();
  if (!s) { $('#content').innerHTML=empty('Bu portföy henüz yüklenemedi.',response?.errors?.[market]||'Veri bekleniyor.'); return; }
  $('#analysis-date').textContent=`Analiz: ${date(s.analysis_date)} · ${s.health.quote_coverage}/${s.health.expected_quotes} fiyat`;
  let content='';
  if (view==='overview') content=`<div class="grid"><div>${chartPanel(s)}${decisionPanel(s)}</div><div class="side-column">${hero(s)}${metricsPanel(s)}${weeklyPanel(s)}${newsPanel(s)}</div></div>`;
  if (view==='decisions') content=funnelPanel(s)+decisionPanel(s,true)+costs(s);
  if (view==='portfolio') content=positions(s)+riskPanel(s)+weeklyPanel(s)+trades(s)+chartPanel(s)+costs(s);
  if (view==='learning') content=evidencePanel(s)+learningPage(s);
  if (view==='legacy') content=legacyPage(s);
  $('#content').innerHTML=content;
  if ($('#search')) { $('#search').value=search; $('#action-filter').value=actionFilter; }
}
function render() {
  const names=pages[view]; $('#crumb').textContent=names[0]; $('#page-title').textContent=names[1]; $('#page-description').textContent=names[2];
  document.querySelectorAll('[data-view]').forEach(a=>{a.classList.toggle('active',a.dataset.view===view);if(a.dataset.view===view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  document.querySelectorAll('.market-switch [data-market]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.market===market));
  $('#account-cards').innerHTML=['bist','gold'].map(m=>accountCard(response?.portfolios?.[m],m)).join('');
  const s=current(), alerts=[];
  if (response && Object.keys(response.errors).length) alerts.push(Object.values(response.errors).join(' '));
  if (s && !fresh(s)) alerts.push(`Gösterilen son kayıt ${date(s.generated_at,true)} tarihinden. Güncel karar için yeni koşu gerekli.`);
  if (s && s.health.errors.length) alerts.push(...s.health.errors);
  if (s && s.health.quote_coverage < s.health.expected_quotes) alerts.push('Güncel fiyat kapsamı eksik. Eksik fiyatla yeni sanal işlem yapılmaz.');
  $('#global-alert').innerHTML=alerts.length?`<div class="notice">${esc(alerts.join(' '))}</div>`:'';
  $('#updated').textContent=s?`Son kayıt ${date(s.generated_at,true)}`:'Bağlantı bekleniyor';
  renderContent();
}
async function load() {
  $('#refresh').disabled=true;
  try {
    const r=await fetch('/api/status',{headers:authorization?{Authorization:authorization}:{},signal:AbortSignal.timeout(25000),cache:'no-store'});
    if(r.status===401){if(!$('#login').open)$('#login').showModal(); if(authorization)$('#login-error').textContent='Parola doğrulanamadı.';return;}
    const data=await r.json(); if(!r.ok)throw new Error(data.error||'Panel bağlantısı kurulamadı.');
    response=data; if($('#login').open)$('#login').close(); render();
  } catch(e) {$('#global-alert').innerHTML=`<div class="notice error">${esc(e.name==='TimeoutError'?'Veri isteği zaman aşımına uğradı. Tekrar yenileyebilirsin.':e.message)}</div>`;if(!response)$('#content').innerHTML=empty('Portföy bağlantısı bekleniyor.','Bağlantı sağlandığında bu ekran otomatik dolacak.');}
  finally {$('#refresh').disabled=false;}
}
document.addEventListener('click',e=>{
  const button=e.target.closest('[data-market]');if(button){market=button.dataset.market;search='';actionFilter='all';render();}
  if(e.target.closest('#export')){const blob=new Blob([JSON.stringify(current(),null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`birikim-${market}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
});
document.addEventListener('input',e=>{if(e.target.id==='search'){search=e.target.value;$('#decision-table').innerHTML=decisionRows(current());}});
document.addEventListener('change',e=>{if(e.target.id==='action-filter'){actionFilter=e.target.value;$('#decision-table').innerHTML=decisionRows(current());}});
window.addEventListener('hashchange',()=>{view=location.hash.slice(1) in pages?location.hash.slice(1):'overview';search='';actionFilter='all';render();});
$('#refresh').addEventListener('click',load);
$('#login-form').addEventListener('submit',e=>{e.preventDefault();const bytes=new TextEncoder().encode(`mert:${$('#password').value}`);authorization='Basic '+btoa(String.fromCharCode(...bytes));$('#password').value='';load();});
view=location.hash.slice(1) in pages?location.hash.slice(1):'overview';
load(); setInterval(()=>{if(!document.hidden)load();},5*60*1000);
