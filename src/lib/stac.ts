import type { Dataset } from '../content.config';
import { SITE } from '../config/site';

const abs = (p: string) => (p.startsWith('/') ? new URL(p, SITE.url).toString() : p);

/**
 * STAC 1.0 Collection representation of a catalog record. This is a metadata
 * description only: assets point at the provider (external) or at AEO-hosted
 * files (available). No STAC API is implied.
 */
export function toStacCollection(d: Dataset) {
  const t = d.temporal_extent;
  const bbox = d.spatial_extent?.bbox ?? null;
  const links: Record<string, unknown>[] = [
    { rel: 'self', href: `${SITE.url}/data/${d.id}.stac.json`, type: 'application/json' },
    { rel: 'root', href: `${SITE.url}/stac/catalog.json`, type: 'application/json' },
    { rel: 'parent', href: `${SITE.url}/stac/catalog.json`, type: 'application/json' },
    { rel: 'alternate', href: `${SITE.url}/data/${d.id}/`, type: 'text/html', title: 'AEO dataset page' },
    { rel: 'describedby', href: `${SITE.url}/data/${d.id}.json`, type: 'application/json', title: 'AEO metadata record' },
  ];
  if (d.source_url) links.push({ rel: 'via', href: d.source_url, type: 'text/html', title: 'Original source' });
  if (d.license?.url) links.push({ rel: 'license', href: d.license.url, title: d.license.name });
  if (d.doi) links.push({ rel: 'cite-as', href: `https://doi.org/${d.doi}` });
  if (d.documentation_url) links.push({ rel: 'about', href: d.documentation_url, title: 'Documentation' });

  const assets: Record<string, unknown> = {};
  d.access
    .filter((a) => a.kind === 'download')
    .forEach((a, i) => {
      assets[`download-${i + 1}`] = {
        href: abs(a.url),
        title: a.label,
        roles: ['data'],
        ...(a.format ? { 'aeo:format': a.format } : {}),
        ...(a.size_bytes ? { 'file:size': a.size_bytes } : {}),
        ...(a.sha256 ? { 'file:checksum': `1220${a.sha256}` } : {}),
      };
    });

  const providers = [] as Record<string, unknown>[];
  if (d.provider) providers.push({ name: d.provider.name, url: d.provider.url ?? undefined, roles: ['producer', 'licensor'] });
  if (d.origin !== 'external') providers.push({ name: SITE.name, url: SITE.url, roles: ['processor', 'host'] });

  return {
    type: 'Collection',
    stac_version: '1.0.0',
    stac_extensions: [
      ...(Object.values(assets).some((a: any) => a['file:checksum'] || a['file:size'])
        ? ['https://stac-extensions.github.io/file/v2.1.0/schema.json'] : []),
      ...(d.doi || d.citation ? ['https://stac-extensions.github.io/scientific/v1.0.0/schema.json'] : []),
      ...(d.version ? ['https://stac-extensions.github.io/version/v1.2.0/schema.json'] : []),
    ],
    id: d.id,
    title: d.title,
    description: d.description,
    keywords: d.keywords,
    license: d.license?.spdx ?? 'other',
    providers,
    extent: {
      spatial: { bbox: [bbox ?? [-180, -90, 180, 90]] },
      temporal: {
        interval: [[t?.start ? `${t.start}T00:00:00Z` : null, t?.ongoing || !t?.end ? null : `${t.end}T23:59:59Z`]],
      },
    },
    summaries: {
      'aeo:status': [d.status],
      'aeo:data_nature': d.data_nature ? [d.data_nature] : [],
      ...(d.resolution?.spatial_m ? { gsd: [d.resolution.spatial_m] } : {}),
    },
    ...(d.doi ? { 'sci:doi': d.doi } : {}),
    ...(d.citation ? { 'sci:citation': d.citation } : {}),
    ...(d.version ? { version: d.version } : {}),
    assets,
    links,
    ...(d.stac ?? {}),
  };
}
