// Pre-build checks that complement the Zod schema in src/content.config.ts:
//  - every file parses as JSON and its "id" equals the file name
//  - ids are unique
//  - AEO-hosted downloads exist and match their recorded SHA-256 and size
//  - map_layers referenced by records exist in the map registry
//  - in-preparation records carry no download link of any kind
// Exits non-zero with a readable message listing every problem found.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dir = join(root, 'src', 'content', 'datasets');
const layerSrc = readFileSync(join(root, 'src', 'data', 'map-layers.ts'), 'utf8');
const layerIds = new Set([...layerSrc.matchAll(/^\s{4}id: '([a-z0-9-]+)'/gm)].map((m) => m[1]));
const errors = [];
const ids = new Set();

for (const f of readdirSync(dir).filter((x) => x.endsWith('.json')).sort()) {
  const p = join(dir, f);
  let rec;
  try {
    rec = JSON.parse(readFileSync(p, 'utf8'));
  } catch (e) {
    errors.push(`${f}: invalid JSON (${e.message})`);
    continue;
  }
  const id = f.replace(/\.json$/, '');
  if (rec.id !== id) errors.push(`${f}: "id" is "${rec.id}" but must equal the file name "${id}"`);
  if (ids.has(rec.id)) errors.push(`${f}: duplicate id "${rec.id}"`);
  ids.add(rec.id);
  for (const a of rec.access ?? []) {
    if (a.kind === 'download' && a.url.startsWith('/')) {
      const file = join(root, 'public', a.url);
      if (!existsSync(file)) {
        errors.push(`${f}: download "${a.url}" does not exist under public/`);
        continue;
      }
      const sha = createHash('sha256').update(readFileSync(file)).digest('hex');
      if (a.sha256 !== sha) errors.push(`${f}: sha256 mismatch for ${a.url} (verify the file, then run "npm run checksums")`);
      if (a.size_bytes !== statSync(file).size) errors.push(`${f}: size mismatch for ${a.url}`);
    }
  }
  if (rec.status === 'in-preparation' && (rec.download_url || (rec.access ?? []).some((a) => a.kind === 'download'))) {
    errors.push(`${f}: in-preparation record must not have downloads`);
  }
  for (const l of rec.map_layers ?? []) {
    if (!layerIds.has(l)) errors.push(`${f}: map layer "${l}" is not defined in src/data/map-layers.ts`);
  }
}

if (errors.length) {
  console.error(`\nCatalog validation failed (${errors.length} problem(s)):\n  - ` + errors.join('\n  - ') + '\n');
  process.exit(1);
}
console.log(`catalog: ${ids.size} records passed pre-build checks`);
