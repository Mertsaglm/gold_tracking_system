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
    <p>${esc(x.note)}</p><h3>Ne değişti?</h3>${change}</details>`;
}

export function funnelPanel(s) {
  const f=s.funnel;
  if (!f) return '';
  return panel('Kararlar nasıl dağıldı?',Object.entries(f.groups).map(([label,n])=>metric(label,`${number(n)} varlık`)).join('')+
    `<p>Toplam ${number(f.total)} varlık. Veri eksikliği, bütçe sınırı ve fırsat yokluğu ayrı sayılır.</p>`,'decision-funnel');
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
  return panel('Sanal sonuçların kanıtı',metric('Bağımsız dönem',`${number(e.periods)} / ${number(e.minimum_periods)}`)+
    metric('Al-tut farkı güven alt sınırı',e.lower_95_pct==null?'Henüz ölçülemiyor':`${number(e.lower_95_pct)} puan`)+
    `<p>${esc(e.status)}. Aynı gün yapılan çok sayıda işlem tek piyasa dönemini çoğaltmaz.</p>`+
    (shadow?`<h3>Önceki modelle karşılaştırma</h3>${metric('Olgunlaşmış bağımsız dönem',number(shadow.periods))}${metric('Tahmin hatasındaki iyileşme',shadow.mean_error_improvement_pct==null?'Henüz ölçülemiyor':`${number(shadow.mean_error_improvement_pct)} puan`)}<p>${esc(shadow.note)}</p>`:'')+
    (books?.ready?`<h3>Aynı bütçeyle iki gölge hesap</h3>${metric('Önceki model hesabı',money(books.reference_equity_try))}${metric('Günlük model hesabı',money(books.candidate_equity_try))}<p>${esc(books.note)}</p>`:''),'live-evidence');
}
