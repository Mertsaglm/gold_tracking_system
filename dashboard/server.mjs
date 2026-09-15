import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {collect, validate, authorized} from './lib/status.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const sources = {bist: process.env.BIST_SNAPSHOT, gold: process.env.GOLD_SNAPSHOT};
const own = JSON.parse(await readFile(path.join(here, '../advisor/config.json'), 'utf8')).market;
sources[own] ||= path.join(here, '../data/advisor/latest.json');
const files = {'/': ['index.html', 'text/html'], '/app.js': ['app.js', 'text/javascript'], '/style.css': ['style.css', 'text/css'], '/favicon.svg': ['favicon.svg', 'image/svg+xml']};
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Cache-Control', 'no-store');
  try {
    if (req.method !== 'GET') { res.writeHead(405); return res.end(); }
    if (url.pathname === '/api/status') {
      if (process.env.ADVISOR_DASHBOARD_PASSWORD && !authorized(req.headers.authorization, process.env.ADVISOR_DASHBOARD_PASSWORD)) {
        res.writeHead(401, {'Content-Type': 'application/json'}); return res.end(JSON.stringify({error: 'Panel parolası gerekli.'}));
      }
      const data = await collect(async market => {
        if (!sources[market]) throw new Error('Yerel dosya yolu yok.');
        return validate(JSON.parse(await readFile(sources[market], 'utf8')), market);
      });
      res.writeHead(200, {'Content-Type': 'application/json; charset=utf-8'});
      return res.end(JSON.stringify(data));
    }
    if (!files[url.pathname]) { res.writeHead(404); return res.end('Bulunamadı'); }
    const [name, mime] = files[url.pathname];
    res.writeHead(200, {'Content-Type': `${mime}; charset=utf-8`});
    res.end(await readFile(path.join(here, 'public', name)));
  } catch { res.writeHead(500); res.end('Panel verisi okunamadı.'); }
});
server.listen(Number(process.env.PORT || 4173), '127.0.0.1', () => console.log('Birikim paneli: http://127.0.0.1:' + server.address().port));
