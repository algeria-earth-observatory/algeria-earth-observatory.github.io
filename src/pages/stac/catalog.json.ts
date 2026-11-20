import type { APIRoute } from 'astro';
import { getDatasets } from '../../lib/catalog';
import { SITE } from '../../config/site';

/** Static STAC root catalog linking to one Collection per published record. */
export const GET: APIRoute = async () => {
  const all = (await getDatasets()).filter((d) => d.status !== 'in-preparation');
  const body = {
    type: 'Catalog',
    stac_version: '1.0.0',
    id: 'algeria-earth-observatory',
    title: SITE.name,
    description: `${SITE.description} Static STAC catalog of metadata records; it is not a STAC API and most assets are held by their original providers.`,
    links: [
      { rel: 'self', href: `${SITE.url}/stac/catalog.json`, type: 'application/json' },
      { rel: 'root', href: `${SITE.url}/stac/catalog.json`, type: 'application/json' },
      ...all.map((d) => ({ rel: 'child', href: `${SITE.url}/data/${d.id}.stac.json`, type: 'application/json', title: d.title })),
    ],
  };
  return new Response(JSON.stringify(body, null, 2), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
};
