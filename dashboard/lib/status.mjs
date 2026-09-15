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
  if (!data || data.schema_version !== 2 || data.market !== market || data.mode !== 'paper'
    || !Array.isArray(data.decisions) || !data.strategy || !Number.isFinite(Date.parse(data.generated_at))) {
    throw new Error('Portföy verisinin biçimi doğrulanamadı.');
  }
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
