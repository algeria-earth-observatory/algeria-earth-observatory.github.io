import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';
import { DOMAIN_IDS } from './lib/domains';

/**
 * AEO dataset metadata schema (v1). One JSON file per record in
 * src/content/datasets/<id>.json. Every record is validated at build time;
 * an invalid record fails the build with the offending field named.
 * Human-readable reference: docs/METADATA_SCHEMA.md
 */
const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, 'must be an ISO date YYYY-MM-DD');
const url = z.string().url();

const accessLink = z.object({
  label: z.string().min(2),
  url: z.string().min(1), // absolute https URL, or a site-relative path for AEO-hosted files
  kind: z.enum(['external', 'download', 'api', 'viewer']),
  format: z.string().nullish(),
  requires_login: z.boolean().default(false),
  size_bytes: z.number().int().positive().nullish(),
  sha256: z.string().regex(/^[a-f0-9]{64}$/).nullish(),
  notes: z.string().nullish(),
});

const reference = z.object({
  citation: z.string().min(10),
  doi: z.string().nullish(),
  url: url.nullish(),
});

export const datasetSchema = z
  .object({
    id: z.string().regex(/^[a-z0-9]+(-[a-z0-9]+)*$/, 'id must be kebab-case'),
    title: z.string().min(3),
    title_fr: z.string().nullish(),
    title_ar: z.string().nullish(),
    description: z.string().min(40),
    purpose: z.string().nullish(),
    domain: z.array(z.enum(DOMAIN_IDS)).min(1),
    categories: z.array(z.string()).default([]),
    keywords: z.array(z.string()).default([]),
    status: z.enum(['available', 'experimental', 'under-validation', 'external', 'in-preparation', 'archived']),
    origin: z.enum(['external', 'aeo-derived', 'aeo-original']),
    data_nature: z.enum(['observed', 'derived', 'modeled']).nullish(),
    data_type: z.enum(['raster', 'vector', 'tabular', 'imagery', 'point']).nullish(),
    provider: z.object({ name: z.string(), url: url.nullish() }).nullish(),
    creator: z.string().nullish(),
    source_url: url.nullish(),
    documentation_url: url.nullish(),
    license: z
      .object({ name: z.string(), spdx: z.string().nullish(), url: url.nullish() })
      .nullish(),
    license_notes: z.string().nullish(),
    citation: z.string().nullish(),
    doi: z
      .string()
      .regex(/^10\.\d{4,9}\/\S+$/, 'doi must be a bare DOI such as 10.5281/zenodo.123')
      .nullish(),
    references: z.array(reference).default([]),
    spatial_extent: z
      .object({
        coverage: z.enum(['global', 'continental', 'regional', 'algeria']),
        description: z.string().nullish(),
        algeria_subset: z.enum(['extract', 'country-file', 'native']).nullish(),
        bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]).nullish(),
      })
      .nullish(),
    temporal_extent: z
      .object({
        start: isoDate.nullish(),
        end: isoDate.nullish(),
        ongoing: z.boolean().default(false),
        frequency: z.string().nullish(),
        description: z.string().nullish(),
      })
      .nullish(),
    resolution: z
      .object({
        spatial: z.string().nullish(),
        spatial_m: z.number().positive().nullish(),
        temporal: z.string().nullish(),
      })
      .nullish(),
    format: z.array(z.string()).default([]),
    crs: z.string().nullish(),
    variables: z
      .array(z.object({ name: z.string(), units: z.string().nullish(), description: z.string().nullish() }))
      .default([]),
    processing: z.string().nullish(),
    validation: z.string().nullish(),
    limitations: z.array(z.string()).default([]),
    /** Prominent warning shown at the top of the record (e.g. a known processing error). */
    alert: z.string().nullish(),
    version: z.string().nullish(),
    published_date: isoDate.nullish(),
    updated_date: isoDate.nullish(),
    download_url: z.string().nullish(),
    preview_url: z.string().nullish(),
    access: z.array(accessLink).default([]),
    code_url: url.nullish(),
    algeria_notes: z.string().nullish(),
    /** AEO map explorer layer ids that preview this dataset. */
    map_layers: z.array(z.string()).default([]),
    /** Planned products: what the product is intended to cover. */
    planned_scope: z.array(z.string()).default([]),
    featured: z.boolean().default(false),
    added_date: isoDate.nullish(),
    verification: z.object({
      checked: isoDate,
      urls_checked: z.boolean(),
      unverified_fields: z.array(z.string()).default([]),
      sources_consulted: z.array(z.string()).default([]),
      notes: z.string().nullish(),
    }),
    stac: z.record(z.any()).nullish(),
    /** Algeria-ready AEO product: machine-readable manifest and supported admin levels. */
    product: z
      .object({
        manifest: z.string().startsWith('/'),
        product_version: z.string().regex(/^\d+\.\d+\.\d+$/, 'semantic version, e.g. 1.0.0'),
        boundary_version: z.string(),
        levels: z.array(z.enum(['admin0', 'admin1', 'admin2'])).min(1),
        spatial_levels: z.array(z.enum(['admin0', 'admin1', 'admin2'])).default([]),
        variables: z.array(z.string()).default([]),
        analyze: z.boolean().default(false),
      })
      .nullish(),
  })
  .superRefine((d, ctx) => {
    const fail = (path: string, message: string) =>
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: [path], message });
    const hasDownload = d.download_url || d.access.some((a) => a.kind === 'download');

    if (d.status === 'in-preparation') {
      if (hasDownload) fail('access', 'an in-preparation product must not expose any download');
      if (d.origin === 'external') fail('origin', 'in-preparation records are AEO products');
    } else {
      // Published records (external, available, archived) need full provenance.
      for (const k of [
        'provider', 'source_url', 'license', 'citation', 'spatial_extent',
        'temporal_extent', 'resolution', 'crs', 'data_nature', 'data_type',
      ] as const) {
        if (k === 'crs' && d.data_type === 'tabular') continue; // national statistics have no CRS
        if (d[k] == null) fail(k, `required for status "${d.status}"`);
      }
      if (d.format.length === 0) fail('format', `at least one format required for status "${d.status}"`);
      if (d.access.length === 0) fail('access', 'at least one verified access route is required');
    }
    if (d.product && d.origin === 'external') fail('product', 'product manifests are only for AEO products');
    if ((d.status === 'experimental' || d.status === 'under-validation') && d.origin === 'external') {
      fail('origin', `status "${d.status}" is for AEO products`);
    }
    if (d.status === 'available') {
      if (d.origin === 'external') fail('origin', '"available" is reserved for files distributed by AEO; use "external"');
      if (!hasDownload) fail('access', '"available" requires at least one direct download');
    }
    if (d.status === 'external' && d.origin !== 'external') {
      fail('origin', 'status "external" requires origin "external"');
    }
    if (d.origin === 'aeo-derived' && !d.code_url && d.status !== 'in-preparation') {
      fail('code_url', 'AEO-derived products must link to reproducible processing code');
    }
    for (const [i, a] of d.access.entries()) {
      if (a.kind === 'download' && a.url.startsWith('/') && !a.sha256) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['access', i, 'sha256'], message: 'AEO-hosted downloads need a sha256 checksum' });
      }
      if (!a.url.startsWith('/') && !/^https?:\/\//.test(a.url)) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['access', i, 'url'], message: 'external links must be absolute http(s) URLs (https preferred)' });
      }
    }
    const t = d.temporal_extent;
    if (t?.start && t?.end && t.start > t.end) fail('temporal_extent', 'start is after end');
    const b = d.spatial_extent?.bbox;
    if (b && (b[0] >= b[2] || b[1] >= b[3] || b[0] < -180 || b[2] > 180 || b[1] < -90 || b[3] > 90)) {
      fail('spatial_extent', 'bbox must be [west, south, east, north] in WGS84');
    }
  });

export type Dataset = z.infer<typeof datasetSchema>;

const datasets = defineCollection({
  loader: glob({ pattern: '*.json', base: './src/content/datasets' }),
  schema: datasetSchema,
});

const docs = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/docs' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    order: z.number().default(100),
    section: z.enum(['Getting started', 'Working with data', 'Scientific practice', 'Tutorials']),
    // YAML parses bare dates as Date objects; normalise to YYYY-MM-DD.
    updated: z.coerce.date().transform((d) => d.toISOString().slice(0, 10)),
  }),
});

export const collections = { datasets, docs };
