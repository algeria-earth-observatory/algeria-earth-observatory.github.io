// Pre-build checks that complement the Zod schema in src/content.config.ts:
//  - every file parses as JSON and its "id" equals the file name
//  - ids are unique
//  - AEO-hosted downloads exist and match their recorded SHA-256 and size
//  - map_layers referenced by records exist in the map registry
//  - in-preparation records carry no download link of any kind
//  - product manifests are complete and every asset matches its size and SHA-256
// Exits non-zero with a readable message listing every problem found.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dir = join(root, 'src', 'content', 'datasets');
const layerSrc = readFileSync(join(root, 'src', 'data', 'map-layers.ts'), 'utf8');
const layerIds = new Set([...layerSrc.matchAll(/^\s{4}id: '([a-z0-9-]+)'/gm)].map((m) => m[1]));
// generated layers: SPI choropleths (one per listed scale) and SoilGrids properties (from the soil map metadata)
const spiScales = layerSrc.match(/\(\[([^\]]+)\] as const\)\.map\(\(k\): MapLayer => \(\{\s*id: `spi-\$\{k\}`/);
if (spiScales) for (const k of spiScales[1].match(/\d+/g)) layerIds.add(`spi-${k}`);
const soilMap = join(root, 'public', 'data', 'aeo', 'products', 'soil', 'v1.0.0', 'map', 'map.json');
if (existsSync(soilMap)) for (const id of Object.keys(JSON.parse(readFileSync(soilMap, 'utf8')).layers)) layerIds.add(`soil-${id.split('_')[0]}`);
// water, cropland and climate layers (src/data/map-layers.ts waterClimateLayers): fixed ids, plus CMIP6 indicators from their map metadata
for (const m of layerSrc.matchAll(/^\s{6}id: '([a-z0-9-]+)'/gm)) layerIds.add(m[1]);
const cmipMap = join(root, 'public', 'data', 'aeo', 'products', 'climate-projections', 'v1.0.0', 'map', 'map.json');
if (existsSync(cmipMap)) for (const id of Object.keys(JSON.parse(readFileSync(cmipMap, 'utf8')).layers)) layerIds.add(`cmip6-${id}`);
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
  if (rec.product) checkManifest(f, rec);
}

// Product manifests (docs/ADDING_PRODUCTS.md): required fields, no placeholders,
// every asset exists with the recorded size and SHA-256, levels agree with the record.
function checkManifest(f, rec) {
  const mpath = join(root, 'public', rec.product.manifest);
  if (!existsSync(mpath)) { errors.push(`${f}: product manifest ${rec.product.manifest} not found`); return; }
  const text = readFileSync(mpath, 'utf8');
  if (/VERIFY/.test(text)) errors.push(`${f}: manifest still contains VERIFY placeholders`);
  const m = JSON.parse(text);
  for (const k of ['product_id', 'title', 'status', 'version', 'geographic_scope', 'source_product', 'source_version',
    'temporal_coverage', 'spatial_resolution', 'boundary_version', 'available_levels', 'formats', 'license',
    'methodology_url', 'download_assets']) {
    if (m[k] === undefined || m[k] === null || m[k] === '') errors.push(`${f}: manifest field "${k}" is missing`);
  }
  if (m.product_id !== rec.id) errors.push(`${f}: manifest product_id "${m.product_id}" differs from record id`);
  if (m.status !== rec.status) errors.push(`${f}: manifest status "${m.status}" differs from record status "${rec.status}"`);
  if (m.version !== rec.product.product_version) errors.push(`${f}: manifest version ${m.version} differs from record ${rec.product.product_version}`);
  if (m.boundary_version !== rec.product.boundary_version) errors.push(`${f}: boundary_version differs between manifest and record`);
  if (!/^\d+\.\d+\.\d+$/.test(m.version ?? '')) errors.push(`${f}: manifest version is not semantic (x.y.z)`);
  const lv = [...(m.available_levels ?? [])].sort().join(','), rl = [...rec.product.levels].sort().join(',');
  if (lv !== rl) errors.push(`${f}: manifest levels [${lv}] differ from record levels [${rl}]`);
  if (!Array.isArray(m.download_assets) || m.download_assets.length === 0) errors.push(`${f}: manifest has no download assets`);
  const hrefs = new Set();
  for (const a of m.download_assets ?? []) {
    hrefs.add(a.href);
    const file = join(root, 'public', a.href);
    if (!a.href?.startsWith('/data/')) { errors.push(`${f}: asset href must be a site path under /data/: ${a.href}`); continue; }
    if (!existsSync(file)) { errors.push(`${f}: manifest asset missing: ${a.href}`); continue; }
    if (statSync(file).size !== a.bytes) errors.push(`${f}: size mismatch for ${a.href}`);
    if (createHash('sha256').update(readFileSync(file)).digest('hex') !== a.sha256) errors.push(`${f}: sha256 mismatch for ${a.href}`);
  }
  for (const a of rec.access ?? []) {
    if (a.kind === 'download' && a.url.startsWith(rec.product.manifest.replace(/manifest\.json$/, '')) && !hrefs.has(a.url)) {
      errors.push(`${f}: record download ${a.url} is not listed in the manifest`);
    }
  }
}

// Regional partitions (scripts/pipelines/partition_regional.py): every partition matches
// its recorded size and SHA-256, and the index's source SHA-256 equals the published file's.
const sha = (p) => createHash('sha256').update(readFileSync(p)).digest('hex');
const pub = (href) => join(root, 'public', href);
function walkIndexes(d) {
  const out = [];
  if (!existsSync(d)) return out;
  for (const e of readdirSync(d, { withFileTypes: true })) {
    const p = join(d, e.name);
    if (e.isDirectory()) out.push(...walkIndexes(p));
    else if (e.name === 'index.json' && p.includes('by_wilaya')) out.push(p);
  }
  return out;
}
let nParts = 0;
for (const ip of walkIndexes(join(root, 'public', 'data', 'aeo'))) {
  const idx = JSON.parse(readFileSync(ip, 'utf8'));
  const sources = idx.source ? [idx.source] : Object.values(idx.sources ?? {});
  for (const s of sources) {
    if (!existsSync(pub(s.href))) { errors.push(`${ip}: source ${s.href} missing`); continue; }
    if (sha(pub(s.href)) !== s.sha256) errors.push(`${ip}: source ${s.href} changed since partitioning (re-run scripts/pipelines/partition_regional.py)`);
  }
  for (const p of idx.partitions ?? []) {
    nParts++;
    if (!existsSync(pub(p.href))) { errors.push(`${ip}: partition ${p.href} missing`); continue; }
    if (statSync(pub(p.href)).size !== p.bytes || sha(pub(p.href)) !== p.sha256) errors.push(`${ip}: partition ${p.href} does not match its index`);
  }
}

if (errors.length) {
  console.error(`\nCatalog validation failed (${errors.length} problem(s)):\n  - ` + errors.join('\n  - ') + '\n');
  process.exit(1);
}
console.log(`catalog: ${ids.size} records passed pre-build checks; ${nParts} regional partitions verified`);
