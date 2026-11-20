// Computes size and SHA-256 for every AEO-hosted download (access[].url starting
// with "/") and writes them back into the dataset records.
// Run after publishing or replacing any file under public/data/aeo/.
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, writeFileSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dir = join(root, 'src', 'content', 'datasets');
let changed = 0;
for (const f of readdirSync(dir).filter((x) => x.endsWith('.json'))) {
  const p = join(dir, f);
  const rec = JSON.parse(readFileSync(p, 'utf8'));
  let dirty = false;
  for (const a of rec.access ?? []) {
    if (a.kind !== 'download' || !a.url.startsWith('/')) continue;
    const file = join(root, 'public', a.url);
    const sha = createHash('sha256').update(readFileSync(file)).digest('hex');
    const size = statSync(file).size;
    if (a.sha256 !== sha || a.size_bytes !== size) {
      a.sha256 = sha;
      a.size_bytes = size;
      dirty = true;
    }
  }
  if (dirty) {
    writeFileSync(p, JSON.stringify(rec, null, 2) + '\n');
    changed++;
    console.log(`updated ${f}`);
  }
}
console.log(`checksums: ${changed} record(s) updated`);
