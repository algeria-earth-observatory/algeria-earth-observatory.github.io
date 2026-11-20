import type { APIRoute } from 'astro';
import { getDatasets, publicRecord } from '../lib/catalog';
import { SITE } from '../config/site';

export const GET: APIRoute = async () => {
  const all = await getDatasets();
  const body = {
    name: `${SITE.name} data catalog`,
    url: `${SITE.url}/data/`,
    generated: new Date().toISOString(),
    schema: `${SITE.url}/docs/metadata-schema/`,
    count: all.length,
    note: 'Records with status "external" are held by their original providers; "in-preparation" records are planned AEO products with no released data.',
    datasets: all.map(publicRecord),
  };
  return new Response(JSON.stringify(body, null, 2), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
};
