// Post-build checks on dist/: required pages exist, no localhost/dev URLs,
// every internal href/src resolves to a built file.
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dist = join(root, 'dist');
const walk = (d) => readdirSync(d).flatMap((f) => (statSync(join(d, f)).isDirectory() ? walk(join(d, f)) : [join(d, f)]));
const files = walk(dist);
const errors = [];
const required = ['index.html', '404.html', 'data/index.html', 'map/index.html', 'catalog.json', 'stac/catalog.json', 'sitemap-index.xml', 'robots.txt'];
for (const p of required) if (!existsSync(join(dist, p))) errors.push(`missing ${p}`);

const resolves = (href) => {
  const clean = decodeURI(href.split('#')[0].split('?')[0]);
  if (!clean || clean === '/') return true;
  const p = join(dist, clean);
  if (existsSync(p) && statSync(p).isFile()) return true;
  return existsSync(join(p, 'index.html'));
};
for (const f of files.filter((x) => extname(x) === '.html')) {
  const html = readFileSync(f, 'utf8');
  const rel = f.slice(dist.length).replace(/\\/g, '/');
  if (/localhost|127\.0\.0\.1/.test(html)) errors.push(`${rel} contains a localhost URL`);
  for (const m of html.matchAll(/(?:href|src)="(\/[^"]*)"/g)) {
    if (m[1].startsWith('//')) continue;
    if (!resolves(m[1])) errors.push(`${rel}: broken internal link ${m[1]}`);
  }
}
if (errors.length) {
  console.error(`\nPost-build check failed:\n  - ${[...new Set(errors)].join('\n  - ')}\n`);
  process.exit(1);
}
console.log(`postbuild: ${files.length} files OK, internal links resolve`);
