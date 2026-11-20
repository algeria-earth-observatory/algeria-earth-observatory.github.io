/**
 * MapLibre protocol for the GACED30 year slider.
 *
 * The PMTiles archive built by scripts/processing/build_gaced30_tiles.py stores, per
 * 256 x 256 Web Mercator tile, zlib-compressed little-endian uint32 values where bit i
 * means "cropland in year 2000 + i". This protocol turns one archive tile into a PNG
 * for the requested year, so changing the year only re-colours tiles already in memory.
 *
 * URL form: aeo-gaced://<archive path>/{z}/{x}/{y}?t=<YYYY-MM-DD>
 */
import { PMTiles } from 'pmtiles';
import type maplibregl from 'maplibre-gl';

const SIZE = 256;
const FIRST_YEAR = 2000;
const LAST_YEAR = 2024;
/** Cropland in the selected year. */
const ON: [number, number, number, number] = [200, 82, 0, 235];
/** Cropland in at least one other year 2000–2024, not in the selected year. */
const OTHER: [number, number, number, number] = [214, 190, 150, 170];

const archives = new Map<string, PMTiles>();
const decoded = new Map<string, Uint32Array | null>();
const MAX_DECODED = 160;
let blank: ArrayBuffer | null = null;

async function inflate(buf: ArrayBuffer): Promise<ArrayBuffer> {
  const stream = new Blob([buf]).stream().pipeThrough(new DecompressionStream('deflate'));
  return new Response(stream).arrayBuffer();
}

async function getBits(path: string, z: number, x: number, y: number, signal: AbortSignal) {
  const key = `${path}/${z}/${x}/${y}`;
  if (decoded.has(key)) {
    const v = decoded.get(key)!;
    decoded.delete(key);
    decoded.set(key, v); // LRU refresh
    return v;
  }
  let pm = archives.get(path);
  if (!pm) {
    pm = new PMTiles(path);
    archives.set(path, pm);
  }
  const res = await pm.getZxy(z, x, y, signal);
  const bits = res ? new Uint32Array(await inflate(res.data)) : null;
  decoded.set(key, bits);
  if (decoded.size > MAX_DECODED) decoded.delete(decoded.keys().next().value!);
  return bits;
}

async function toPng(rgba: Uint8ClampedArray<ArrayBuffer>): Promise<ArrayBuffer> {
  const canvas = new OffscreenCanvas(SIZE, SIZE);
  canvas.getContext('2d')!.putImageData(new ImageData(rgba, SIZE, SIZE), 0, 0);
  return (await canvas.convertToBlob({ type: 'image/png' })).arrayBuffer();
}

export const gacedProtocol: maplibregl.AddProtocolAction = async (params, abort) => {
  const m = params.url.match(/^aeo-gaced:\/\/(.+)\/(\d+)\/(\d+)\/(\d+)\?t=(\d{4})/);
  if (!m) throw new Error(`Bad GACED30 tile URL: ${params.url}`);
  const [, path, zs, xs, ys, ys4] = m;
  const year = Math.min(LAST_YEAR, Math.max(FIRST_YEAR, Number(ys4)));
  const bits = await getBits(path, Number(zs), Number(xs), Number(ys), abort.signal);
  if (!bits) {
    blank ??= await toPng(new Uint8ClampedArray(SIZE * SIZE * 4));
    return { data: blank.slice(0) };
  }
  const bit = 1 << (year - FIRST_YEAR);
  const rgba = new Uint8ClampedArray(SIZE * SIZE * 4);
  for (let i = 0; i < bits.length; i++) {
    const v = bits[i];
    if (!v) continue;
    const c = v & bit ? ON : OTHER;
    const o = i * 4;
    rgba[o] = c[0]; rgba[o + 1] = c[1]; rgba[o + 2] = c[2]; rgba[o + 3] = c[3];
  }
  return { data: await toPng(rgba) };
};

export const GACED_COLORS = {
  on: `rgba(${ON.slice(0, 3).join(',')},${(ON[3] / 255).toFixed(2)})`,
  other: `rgba(${OTHER.slice(0, 3).join(',')},${(OTHER[3] / 255).toFixed(2)})`,
};
