import type { APIRoute, GetStaticPaths } from 'astro';
import { getDatasets, publicRecord } from '../../lib/catalog';
import type { Dataset } from '../../content.config';

export const getStaticPaths: GetStaticPaths = async () =>
  (await getDatasets()).map((d) => ({ params: { id: d.id }, props: { d } }));

export const GET: APIRoute = ({ props }) =>
  new Response(JSON.stringify(publicRecord((props as { d: Dataset }).d), null, 2), {
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
