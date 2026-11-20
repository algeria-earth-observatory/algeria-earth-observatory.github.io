import { getCollection, type CollectionEntry } from 'astro:content';
import type { Dataset } from '../content.config';

export type DatasetEntry = CollectionEntry<'datasets'>;

/** All records, sorted by title. Published records first, planned products last. */
export async function getDatasets(): Promise<Dataset[]> {
  const all = await getCollection('datasets');
  for (const e of all) {
    if (e.data.id !== e.id) {
      throw new Error(`Dataset file "${e.id}.json" declares id "${e.data.id}" — the id must equal the file name.`);
    }
  }
  return all
    .map((e) => e.data)
    .sort((a, b) => {
      const pa = a.status === 'in-preparation' ? 1 : 0;
      const pb = b.status === 'in-preparation' ? 1 : 0;
      return pa - pb || a.title.localeCompare(b.title);
    });
}

/** Public JSON form of a record (what /data/<id>.json serves). */
export function publicRecord(d: Dataset) {
  const { stac, featured, ...rest } = d;
  return { schema: 'https://algeria-earth-observatory.github.io/docs/metadata-schema/', schema_version: '1.0', ...rest };
}
