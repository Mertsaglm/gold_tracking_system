const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = n => typeof n === 'number' && Number.isFinite(n) ? n.toLocaleString('tr-TR',{maximumFractionDigits:2}) : '—';
const money = n => n == null ? '—' : `${number(n)} TL`;
const metric = (label,value) => `<div class="metric"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`;
const panel = (title,body,id='') => `<section class="panel" ${id?`data-testid="${id}"`:''}><div class="panel-head"><h2>${esc(title)}</h2></div><div class="panel-body body-copy">${body}</div></section>`;

export function decisionDetail(d) {
  if (!d.detail) return '';
  const x=d.detail, changes=d.change?.items||[];
  const change=changes.length ? `<ul>${changes.map(c=>`<li>${esc(c.label)}: ${esc(c.before ?? '—')} → ${esc(c.after ?? '—')}</li>`).join('')}</ul>`
    : `<p>${d.change?.first?'Bu varlığın ilk kaydı.':'Önceki kayda göre karar, gerekçe, model ve fiyat aynı.'}</p>`;
  return `<details class="decision-detail"><summary>Hesabı ve değişimi gör</summary><p>${esc(x.basis)}</p>
    ${metric('Miktar',x.quantity??'İşlem yok')}${metric('İşlem tutarı',money(x.notional_try))}${metric('İşlem masrafı',money(x.fee_try))}
    ${metric('Zarar sınırı',money(d.stop))}${metric('Hedef fiyat',money(d.target))}
    ${metric('Stopta tahmini kayıp',money(x.stop_risk_try))}${metric('Hedefte net sonuç',money(x.target_net_try))}
    <p>${esc(x.note)}</p>${d.checks?.length?`<h3>Karar kontrolleri</h3>${d.checks.map(c=>metric(`${c.check} · ${c.status}`,`${c.observed??'—'} / ${c.threshold??'—'}`)).join('')}`:''}<h3>Ne değişti?</h3>${change}</details>`;
}

export function portfolioExperimentPanel(s) {
  const experiment=s.portfolio_experiments;
  if (!experiment) return '';
  if (!experiment.accounts?.length) return panel('Çekirdek ve taktik deneyi',
    `<p>${esc(experiment.status)}. İki piyasanın ortak ileri başlangıç tarihi yayımdan sonra sabitlenecek; eski ana hesabın sonucu bu yeni yarışa katılmıyor.</p>`,'portfolio-experiment');
  const names={'legacy-control':'Mevcut politika','core-cash':'%80 çekirdek + %20 nakit',
    'core-passive':'Çekirdek + pasif yatırım','core-ridge':'Çekirdek + mevcut Ridge',
    'core-specialized':'Çekirdek + özel model'};
  const metrics=new Map((experiment.comparison?.arms||[]).map(a=>[a.id,a]));
  const rows=experiment.accounts.map(a=>{
    const r=metrics.get(a.id)||{},parts=a.strategy?.parts||{};
    return `<tr><td><strong>${esc(names[a.id]||a.id)}</strong><small>${esc(a.start_date)} başlangıç</small></td>`+
      `<td>${money(r.wealth_try)}<small>Katkı: ${money(r.contributed_try)}</small>${r.vs_passive?`<small>Pasife fark: ${money(r.vs_passive.wealth_difference_try)}</small>`:''}</td>`+
      `<td>${r.twr_pct==null?'—':`${number(r.twr_pct)}%`}<small>Düşüş: ${r.max_drawdown_pct==null?'—':`${number(r.max_drawdown_pct)}%`}</small></td>`+
      `<td>${money(parts.core?.equity_try)}<small>Taktik: ${money(parts.tactical?.equity_try)}</small></td>`+
      `<td>${number(r.trade_count,0)} işlem<small>İşlem masrafı: ${money(r.transaction_fees_try)}</small></td></tr>`;
  }).join('');
  const ridge=experiment.accounts.find(a=>a.id==='core-ridge');
  const targets=(ridge?.target_portfolio?.rows||[]).filter(r=>r.book==='tactical');
  return `<section class="panel" data-testid="portfolio-experiment"><div class="panel-head"><h2>Çekirdek ve taktik deneyi</h2></div>`+
    `<p class="panel-subtitle">Aynı başlangıç ve katkılar; her kolun parası ayrıdır. Sonuçlar ana servete eklenmez.</p>`+
    `<div class="table-wrap"><table><thead><tr><th>KOL</th><th>NET SERVET</th><th>KATKISIZ GETİRİ</th><th>ÇEKİRDEK / TAKTİK</th><th>İŞLEMLER</th></tr></thead><tbody>${rows}</tbody></table></div>`+
    `${targets.length?`<div class="panel-body"><h3>Mevcut Ridge taktik hedefi</h3>${targets.map(t=>metric(t.symbol,`şimdi ${number(t.current_weight_pct)}% · hedef ${number(t.target_weight_pct)}% · net beklenti ${number(t.net_forecast_pct)}%`)).join('')}</div>`:''}`+
    `<div class="note-strip">${esc(experiment.comparison?.evaluation_status||'Ölçüm bekleniyor')} · Otomatik terfi yok. Çekirdeğin stopu yoktur; piyasa riski sıfır değildir. BIST eşit ağırlıklı sepet, resmî BIST30 endeks getirisi değildir. Tarihsel banka dolumu varsayılmaz.</div></section>`;
}

export function funnelPanel(s) {
  const f=s.funnel;
  if (!f) return '';
  const detail=s.filter_diagnostics, interaction=detail?.bist_interaction;
  return panel('Kararlar nasıl dağıldı?',Object.entries(f.groups).map(([label,n])=>metric(label,`${number(n)} varlık`)).join('')+
    `<p>Toplam ${number(f.total)} varlık. Veri eksikliği, bütçe sınırı ve fırsat yokluğu ayrı sayılır.</p>`+
    (interaction?.fully_evaluated?`<h3>Filtre etkileşimi</h3>${metric('Dört kontrolü ölçülen',number(interaction.fully_evaluated))}`+
      `${metric('Hepsi geçti',number(interaction.all_pass))}${metric('R:R olmadan',number(interaction.without_rr))}`+
      `${metric('Trend olmadan',number(interaction.without_trend))}${metric('İkisi olmadan',number(interaction.without_both))}`+
      `<p>${esc(detail.note)}</p>`:'')
    ,'decision-funnel');
}

export function weeklyPanel(s) {
  const w=s.weekly;
  if (!w?.ready) return panel('Son 7 gün','<p>Yeni değerlemelerle haftalık özet oluşacak.</p>','weekly-summary');
  return panel('Son 7 gün',metric('Eklenen para',money(w.contributions_try))+metric('Yatırım sonucu',money(w.investment_result_try))+
    metric('Ödenen masraf',money(w.fees_try))+metric('Al-tut farkı',money(w.excess_try))+metric('En büyük gerileme',`${number(w.max_drawdown_pct)}%`)+
    `<p>${esc(w.note)}</p><small>Son değerleme: ${esc(w.through)}${w.stale?' · Güncel değerleme bekleniyor':''}</small>`,'weekly-summary');
}

export function riskPanel(s) {
  const r=s.risk;
  if (!r) return '';
  return panel('Hesabın toplam riski',metric('Stoplara kadar tahmini kayıp',money(r.stop_risk_try))+
    metric('Toplam stop riski',r.stop_risk_pct==null?'Değerleme eksik':`${number(r.stop_risk_pct)}%`)+
    metric('Yeni işlem için toplam risk tavanı',`${number(r.limit_pct)}%`)+
    r.stress.map(x=>metric(`Tüm varlıklar %${number(x.fall_pct)} düşerse`,money(x.loss_try))).join('')+
    `<p>${esc(r.note)}</p>${r.missing.length?`<p>Fiyatı doğrulanamayan: ${esc(r.missing.join(', '))}</p>`:''}`,'portfolio-risk');
}

export function evidencePanel(s) {
  const e=s.feedback?.evidence, shadow=s.feedback?.shadow, books=s.feedback?.shadow_portfolios;
  if (!e) return '';
  return panel('Sanal sonuçların kanıtı',metric('Örtüşmeyen dönem',`${number(e.periods)} / ${number(e.minimum_periods)}`)+
    metric('Al-tut farkı güven alt sınırı',e.lower_95_pct==null?'Henüz ölçülemiyor':`${number(e.lower_95_pct)} puan`)+
    `<p>${esc(e.status)}. Aynı gün yapılan çok sayıda işlem tek piyasa dönemini çoğaltmaz. Örtüşmeyen dönemler de birbirinden bağımsız olmayabilir.</p>`+
    (shadow?`<h3>Önceki modelle karşılaştırma</h3>${metric('Olgunlaşmış örtüşmeyen dönem',number(shadow.periods))}${metric('Tahmin hatasındaki iyileşme',shadow.mean_error_improvement_pct==null?'Henüz ölçülemiyor':`${number(shadow.mean_error_improvement_pct)} puan`)}<p>${esc(shadow.note)}</p>`:'')+
    (books?.ready?`<h3>Aynı bütçeyle iki gölge hesap</h3>${metric('Önceki model hesabı',money(books.reference_equity_try))}${metric('Günlük model hesabı',money(books.candidate_equity_try))}<p>${esc(books.note)}</p>`:''),'live-evidence');
}

export function candidatePanel(s) {
  if (!s.candidates?.length) return '';
  return panel('Aynı parayla yöntem sınavı', `<p>Her aday ayrı ${money(s.budget.initial_try)} ile başlar; aynı aylık katkı ve maliyet kuralları uygulanır. Adayların paraları toplam servete eklenmez. Ana hesap 20 seanslık kontrol olarak korunur.</p>`+
    s.candidates.map(c=>`<h3>${esc(c.name)}</h3><div class="metric-list">`+
      metric('Sanal hesap değeri',money(c.strategy?.equity_try))+metric('Katkılar hariç getiri',`${number(c.feedback?.twr_pct)}%`)+
      metric('Adayın al-tut hesabı',money(c.benchmark?.equity_try))+metric('Örtüşmeyen sınav dönemi',`${number(c.evidence?.periods)} / ${number(c.evidence?.minimum_periods)}`)+
      (c.style==='sma50'?metric('Karar kuralı','SMA50; getiri tahmini yok'):metric('Tahmin hatası / sabit tahmin',`${number(c.evaluation?.mae_pct)} / ${number(c.evaluation?.baseline_mae_pct)} puan`))+
      `</div><p>${esc(c.status)} Otomatik model değişimi yok.</p>`).join('')+
    '<p>Basit trend hesabı son kapanış SMA50 üzerindeyse alır, altına indiğinde satar; ortak stop, maliyet ve bütçe sınırları geçerlidir. Hedef fiyat veya getiri tahmini üretmez. Ridge adayları son 3 yıl ile sınırlı eğitimde yaklaşık son 6 aya daha çok ağırlık verir. 5 seans hedefi daha erken sonuçlanır; daha iyi tahmin veya kâr garantisi sağlamaz. Tahmin hatası, masraf sonrası portföy getirisi değildir.</p>','candidate-comparison');
}

export function operatingPanel(s) {
  if (!s.monitoring) return '';
  const m=s.monitoring, r=s.risk_control||{}, names={entry:'Yeni alım ve pozisyon takibi',protection:'Mevcut pozisyon takibi',valuation:'Yalnız değerleme',closed:'Gözlem kapalı'};
  return panel('Hesabın çalışma kuralları',metric('Kayıt anındaki çalışma',names[m.phase]||'Bilinmiyor')+
    metric('Yeni alım saatleri',`${m.entry_window.open}–${m.entry_window.close}`)+
    metric('Fiyat gözlem saatleri',`${m.observation_window.open}–${m.observation_window.close}`)+
    metric('Piyasa koşulu',r.regime||'Ölçülemiyor')+metric('Piyasa kaynaklı yeni risk çarpanı',`${number(r.multiplier)}×`)+
    metric('Hesaba yazılan dönemsel ücret',money(s.strategy.account_fees_try))+
    `<p>${esc(m.note)} Yarım gün ve tatil takvimi ayrıca uygulanır.</p><p>${esc(r.note)} ${(r.reasons||[]).map(esc).join(' ')}</p>`+
    `<p>${esc(s.custody?.note||'Nakit faiz kazanmaz.')} ${s.custody?.pending?.length?'Eksik günlük değerlemeler nedeniyle hesaplanamayan saklama dönemi var; toplam maliyet henüz tam değil.':''}</p>`,'operating-rules');
}

export function freshness(s, now=Date.now()) {
  const at=Date.parse(s?.generated_at);
  if (!Number.isFinite(at)||at>now+60000) return {stale:true, note:'Kayıt zamanı doğrulanamadı.'};
  if (!s.monitoring?.calendar?.available) return {stale:now-at>90*60000,note:'Çalışma takvimi bulunamadı; kayıt yaşını kontrol edin.'};
  const m=s.monitoring, cal=m.calendar, cutoff=new Date(now-90*60000+3*3600000);
  if (!cal.years.includes(String(cutoff.getUTCFullYear()))) return {stale:true,note:'Bu yılın çalışma takvimi eksik.'};
  for(let offset=0;offset<370;offset++) {
    const date=new Date(cutoff);date.setUTCDate(date.getUTCDate()-offset);
    const day=date.toISOString().slice(0,10);
    if([0,6].includes(date.getUTCDay())||cal.full_days.includes(day)) continue;
    const w=m.observation_window, close=cal.half_days.includes(day)?w.half_day_close:w.close;
    const end=Math.min(Date.parse(`${day}T${close}:00+03:00`),now-90*60000);
    let slot=Date.parse(`${day}T${w.open.slice(0,2)}:17:00+03:00`), due=null;
    while(slot<=end){due=slot;slot+=30*60000;}
    if(due!==null) return {stale:at<due,note:at<due?'Beklenen fiyat gözlemi eksik; yeni koşu gerekli.':'Çalışma takvimine göre son beklenen gözlem mevcut; bu ifade anlık fiyat garantisi değildir.'};
  }
  return {stale:true,note:'Beklenen çalışma zamanı hesaplanamadı.'};
}


export function combinedExposure(portfolios, now=Date.now()) {
  const b=portfolios?.bist,g=portfolios?.gold;
  const result={complete:false,total_try:null,direct_try:null,related_try:null,share_pct:null,review_required:false};
  if (!b||!g||!b.account_id||b.account_id!==g.account_id) return {...result,reason:'İki eşleşen ana hesap bekleniyor.'};
  if ([b,g].some(s=>freshness(s,now).stale||!s.strategy?.valuation_complete||!Number.isFinite(s.strategy.equity_try)||!s.risk_factors))
    return {...result,reason:'İki hesabın güncel değerlemesi ve risk etiketleri gerekli.'};
  const sum=(s,factor)=>s.strategy.positions.filter(p=>s.risk_factors[p.symbol]?.factor===factor).reduce((v,p)=>v+p.value_try,0);
  if ([b,g].some(s=>s.strategy.positions.some(p=>!Number.isFinite(p.value_try)))) return {...result,reason:'Pozisyon değeri eksik.'};
  const direct=sum(g,'gold_direct'),related=sum(b,'gold_related'),total=b.strategy.equity_try+g.strategy.equity_try;
  return {...result,complete:true,total_try:total,direct_try:direct,related_try:related,
    share_pct:total>0?(direct+related)/total*100:null,review_required:related>0,
    reason:related>0?'Altın ilişkili hisse pozisyonu var: toplam yoğunlaşma sınırı için değerlendirme gerekli.':'Altın ilişkili hisse pozisyonu yok; izleme sürüyor.'};
}

export function exposurePanel(portfolios, now=Date.now()) {
  const r=combinedExposure(portfolios,now);
  return panel('İki hesabın ortak altın ilişkisi',
    metric('İki ana hesabın toplam değeri',money(r.total_try))+metric('Doğrudan gram altın',money(r.direct_try))+
    metric('Altın ilişkili hisseler',money(r.related_try))+metric('Toplam içindeki pay',r.share_pct==null?'Ölçülemiyor':`${number(r.share_pct)}%`)+
    `<p>${esc(r.reason)}</p><p>TRALT altın üreticisi olarak işaretlidir. Bu tutar bilinen etiketlerin toplamıdır; bütün dolaylı ilişkileri kapsamaz ve ölçülmüş korelasyon değildir. Hisse ile gram altın eşdeğer sayılmaz. Aday hesaplar toplama katılmaz; sert ortak sınır henüz tanımlı değildir.</p>`+
    `<p>BIST kayıt: ${esc(portfolios?.bist?.generated_at||'yok')} · Altın kayıt: ${esc(portfolios?.gold?.generated_at||'yok')}. Değerlemeler aynı ana ait olmayabilir.</p>`,'combined-exposure');
}
