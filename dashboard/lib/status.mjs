import {timingSafeEqual, createHash} from 'node:crypto';

export const REPOSITORIES = {bist: 'Mertsaglm/bist-analiz', gold: 'Mertsaglm/gold_tracking_system'};
export function authorized(header, password) {
  if (!password || !header?.startsWith('Basic ')) return false;
  let given;
  try { given = Buffer.from(header.slice(6), 'base64').toString('utf8'); } catch { return false; }
  const hash = s => createHash('sha256').update(s).digest();
  return timingSafeEqual(hash(given), hash(`mert:${password}`));
}

export function validate(data, market) {
  const obj = x => x && typeof x === 'object' && !Array.isArray(x);
  const num = x => typeof x === 'number' && Number.isFinite(x);
  const nullable = x => x === null || num(x);
  const account = a => obj(a) && ['cash_try','contributed_try','realized_try'].every(k=>num(a[k]))
    && ['equity_try','pnl_try'].every(k=>nullable(a[k])) && Array.isArray(a.positions) && Array.isArray(a.fills)
    && a.positions.every(p=>obj(p) && typeof p.symbol==='string' && typeof p.quantity==='string' && num(p.cost_try)
      && nullable(p.value_try) && nullable(p.pnl_try))
    && a.fills.every(f=>obj(f) && typeof f.symbol==='string' && ['BUY','SELL'].includes(f.side)
      && num(f.price) && num(f.notional_cents) && num(f.fee_cents));
  if (!data || data.schema_version !== 2 || data.market !== market || data.mode !== 'paper'
    || !Array.isArray(data.decisions) || !account(data.strategy) || !account(data.benchmark)
    || !Number.isFinite(Date.parse(data.generated_at)) || !Number.isFinite(Date.parse(data.analysis_date))
    || !obj(data.health) || !Array.isArray(data.health.errors) || !data.health.errors.every(x=>typeof x==='string')
    || !num(data.health.quote_coverage) || !num(data.health.expected_quotes)
    || !obj(data.quotes) || !Array.isArray(data.history) || !obj(data.budget)
    || !num(data.budget.monthly_try) || !obj(data.feedback) || !obj(data.learning)
    || !obj(data.news) || !Array.isArray(data.news.items) || !Array.isArray(data.news.sources)
    || !obj(data.legacy) || !Array.isArray(data.legacy.sources) || !Array.isArray(data.legacy.recent)
    || !data.decisions.every(d=>obj(d) && typeof d.symbol==='string'
       && ['AL','SAT','TUT','BEKLE','VERİ BEKLENİYOR'].includes(d.action)
       && Array.isArray(d.reasons) && d.reasons.every(x=>typeof x==='string') && nullable(d.price))) {
    throw new Error('Portföy verisinin biçimi doğrulanamadı.');
  }
  const invalid = (data.risk != null && (!obj(data.risk) || !Array.isArray(data.risk.stress)
      || !data.risk.stress.every(x=>obj(x) && num(x.fall_pct) && nullable(x.loss_try))
      || !Array.isArray(data.risk.missing) || !data.risk.missing.every(x=>typeof x==='string')))
    || (data.funnel != null && (!obj(data.funnel) || !obj(data.funnel.groups)
      || !Object.values(data.funnel.groups).every(num) || !num(data.funnel.total)))
    || data.decisions.some(d => d.change != null && (!obj(d.change) || !Array.isArray(d.change.items)
      || !d.change.items.every(obj)));
  if (invalid) throw new Error('Portföy açıklamalarının biçimi doğrulanamadı.');
  return data;
}

export async function readRemote(market, {token, fetcher = fetch} = {}) {
  if (market === 'bist' && !token) throw new Error('Özel BIST deposu için sunucuda GitHub okuma bağlantısı eksik.');
  const headers = {Accept: 'application/vnd.github.raw+json', 'X-GitHub-Api-Version': '2022-11-28'};
  if (token) headers.Authorization = `Bearer ${token}`;
  const url = `https://api.github.com/repos/${REPOSITORIES[market]}/contents/data/advisor/latest.json?ref=main`;
  const response = await fetcher(url, {headers, signal: AbortSignal.timeout(15000), redirect: 'error'});
  if (!response.ok) throw new Error(`Portföy arşivi alınamadı (HTTP ${response.status}).`);
  const reader = response.body.getReader();
  const chunks = []; let size = 0;
  try {
    while (true) {
      const {value, done} = await reader.read(); if (done) break;
      size += value.length;
      if (size > 2_000_000) { await reader.cancel(); throw new Error('Portföy dosyası beklenen sınırı aşıyor.'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return validate(JSON.parse(Buffer.concat(chunks).toString('utf8')), market);
}

export async function collect(reader) {
  const markets = Object.keys(REPOSITORIES);
  const results = await Promise.allSettled(markets.map(async market => validate(await reader(market), market)));
  const portfolios = {}, errors = {};
  results.forEach((result, i) => {
    if (result.status === 'fulfilled') portfolios[markets[i]] = validate(result.value, markets[i]);
    else errors[markets[i]] = result.reason?.message?.startsWith('Özel BIST') ? result.reason.message : 'Portföy alınamadı. Bağlantı veya üretilen dosya kontrol edilmeli.';
  });
  return {generated_at: new Date().toISOString(), portfolios, errors};
}
