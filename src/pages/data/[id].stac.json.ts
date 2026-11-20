import type { APIRoute, GetStaticPaths } from 'astro';
import { getDatasets } from '../../lib/catalog';
import { toStacCollection } from '../../lib/stac';
import type { Dataset } from '../../content.config';

// Planned products have no data, so they get no STAC representation.
export const getStaticPaths: GetStaticPaths = async () =>
  (await getDatasets())
    .filter((d) => d.status !== 'in-preparation')
    .map((d) => ({ params: { id: d.id }, props: { d } }));

export const GET: APIRoute = ({ props }) =>
  new Response(JSON.stringify(toStacCollection((props as { d: Dataset }).d), null, 2), {
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
