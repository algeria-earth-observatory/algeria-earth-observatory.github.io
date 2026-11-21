/**
 * Administrative units for the region selectors (RegionDataDownloader), built from the
 * published boundary files. Stable ONS codes are the identifiers; names are for display.
 */
import type { APIRoute } from 'astro';
import { loadRegions, BOUNDARY_VERSION } from '../../lib/regions-data';

export const GET: APIRoute = () => {
  const { wilayas, communes } = loadRegions();
  const body = {
    boundary_version: BOUNDARY_VERSION,
    source: 'AEO administrative boundaries (OpenStreetMap snapshot), ODbL 1.0',
    national: { code: 'DZ', name: 'Algeria', name_ar: 'الجزائر' },
    wilayas: wilayas.map((w) => [w.code, w.name, w.name_ar ?? '']),
    communes: communes.map((c) => [c.code, c.name, c.name_ar ?? '', c.wilaya_code]),
  };
  return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
};
