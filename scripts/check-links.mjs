// Checks every external URL in the dataset records (source, documentation,
// licence, access links, DOIs) and writes research/link-report.json.
// Usage: npm run check:links   (network required; not part of the build,
// because some providers block automated requests while working in browsers).
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dir = join(root, 'src', 'content', 'datasets');
const urls = new Map();
const add = (u, where) => {
  if (!u || !/^https:\/\//.test(u)) return;
  if (!urls.has(u)) urls.set(u, new Set());
  urls.get(u).add(where);
};
for (const f of readdirSync(dir).filter((x) => x.endsWith('.json'))) {
  const r = JSON.parse(readFileSync(join(dir, f), 'utf8'));
  add(r.source_url, `${r.id}.source_url`);
  add(r.documentation_url, `${r.id}.documentation_url`);
  add(r.license?.url, `${r.id}.license`);
  add(r.code_url, `${r.id}.code_url`);
  if (r.doi) add(`https://doi.org/${r.doi}`, `${r.id}.doi`);
  for (const a of r.access ?? []) add(a.url, `${r.id}.access`);
  for (const ref of r.references ?? []) if (ref.doi) add(`https://doi.org/${ref.doi}`, `${r.id}.reference`);
}

const UA = 'Mozilla/5.0 (compatible; AEO-link-check/1.0)';
async function check(u) {
  // DOIs: verify registration with the DOI handle API — many publishers
  // answer automated requests to their landing pages with HTTP 403.
  if (u.startsWith('https://doi.org/')) {
    try {
      const res = await fetch(`https://doi.org/api/handles/${u.slice(16)}`, { headers: { 'user-agent': UA } });
      const j = await res.json();
      return j.responseCode === 1 ? { status: 200, final: u, via: 'doi-handle-api' } : { status: 404, error: `DOI not registered (responseCode ${j.responseCode})` };
    } catch (e) {
      return { status: 0, error: String(e.cause?.code ?? e.message) };
    }
  }
  let last = { status: 0, error: 'not attempted' };
  for (const method of ['HEAD', 'GET']) {
    try {
      const ctl = new AbortController();
      const t = setTimeout(() => ctl.abort(), 30000);
      const res = await fetch(u, { method, redirect: 'follow', signal: ctl.signal, headers: { 'user-agent': UA } });
      clearTimeout(t);
      last = { status: res.status, final: res.url };
      if (res.ok) return last;
    } catch (e) {
      last = { status: 0, error: String(e.cause?.code ?? e.message) };
    }
  }
  return last;
}

const list = [...urls.keys()];
const out = [];
for (let i = 0; i < list.length; i += 8) {
  out.push(...(await Promise.all(list.slice(i, i + 8).map(async (u) => ({ url: u, ...(await check(u)), used_by: [...urls.get(u)] })))));
}
const bad = out.filter((r) => !(r.status >= 200 && r.status < 400));
writeFileSync(
  join(root, 'research', 'link-report.json'),
  JSON.stringify({ checked: new Date().toISOString(), total: out.length, problems: bad, ok: out.filter((r) => !bad.includes(r)) }, null, 2) + '\n',
);
console.log(`links: ${out.length} checked, ${bad.length} need attention`);
for (const b of bad) console.log(`  ${b.status || 'ERR'} ${b.url}  (${b.used_by.join(', ')}) ${b.error ?? ''}`);
