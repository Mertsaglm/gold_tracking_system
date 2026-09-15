import {authorized, collect, readRemote} from '../lib/status.mjs';

let cached, expires = 0;
export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  if (req.method !== 'GET') { res.setHeader('Allow', 'GET'); return res.status(405).json({error: 'Yalnız okuma desteklenir.'}); }
  const password = process.env.ADVISOR_DASHBOARD_PASSWORD;
  if (!password) return res.status(503).json({error: 'Panel erişim parolası sunucuda henüz ayarlanmamış.'});
  if (!authorized(req.headers.authorization, password)) {
    return res.status(401).json({error: 'Panel parolası gerekli.'});
  }
  try {
    if (!cached || Date.now() >= expires) {
      cached = await collect(market => readRemote(market, {token: process.env.ADVISOR_GITHUB_TOKEN}));
      expires = Date.now() + 45000;
    }
    return res.status(200).json(cached);
  } catch {
    return res.status(502).json({error: 'Portföy arşivi şu anda okunamıyor.'});
  }
}
