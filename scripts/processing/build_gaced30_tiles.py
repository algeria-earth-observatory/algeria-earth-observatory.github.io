"""Build the map tiles for the GACED30 year slider (one PMTiles file, all 25 years).

Input : data-work/gaced30/out/gaced30_dza_<year>_v1.tif (build_gaced30.py), 2000-2024
Output: public/data/aeo/gaced30/v1/gaced30_dza_2000_2024.pmtiles

Tile encoding (read by src/scripts/gaced-protocol.ts): every tile is 256 x 256 pixels in
Web Mercator, stored as zlib-compressed little-endian uint32 values. Bit i (i = 0..24)
is set when the pixel is cropland in year 2000 + i. Tiles without any cropland in any
year are omitted.

Display resampling: at the deepest zoom (MAX_ZOOM) each pixel takes the most frequent
GACED30 class among the source pixels it covers (GDAL "mode", ignoring no data). Each
coarser zoom marks a year as cropland when at least 2 of the 4 finer pixels are cropland
in that year. This is a visual overview; analysis should use the 30 m GeoTIFFs.

Usage: python scripts/processing/build_gaced30_tiles.py [max_zoom]
"""
import json
import math
import sys
import time
import zlib
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from rasterio.windows import Window, from_bounds as window_from_bounds
from shapely.geometry import box, shape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'data-work' / 'pylib'))
from pmtiles.tile import Compression, TileType, zxy_to_tileid  # noqa: E402
from pmtiles.writer import Writer  # noqa: E402

SRC = ROOT / 'data-work' / 'gaced30' / 'out'
OUT = ROOT / 'public' / 'data' / 'aeo' / 'gaced30' / 'v1'
BOUNDARY = ROOT / 'public' / 'data' / 'aeo' / 'boundaries' / '2026-11-19' / 'dza_adm0.geojson'
YEARS = list(range(2000, 2025))
MAX_ZOOM = int(sys.argv[1]) if len(sys.argv) > 1 else 11
MIN_ZOOM = 4
R = 6378137.0
SIZE = 256


def tile_lonlat(z, x, y):
    n = 2 ** z
    lon0, lon1 = x / n * 360 - 180, (x + 1) / n * 360 - 180
    lat0 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    lat1 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon0, lat0, lon1, lat1


def tile_merc(z, x, y):
    span = 2 * math.pi * R / 2 ** z
    xmin = -math.pi * R + x * span
    ymax = math.pi * R - y * span
    return xmin, ymax - span, xmin + span, ymax


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def algeria():
    gj = json.loads(BOUNDARY.read_text(encoding='utf-8'))
    g = shape(gj['features'][0]['geometry'])
    for f in gj['features'][1:]:
        g = g.union(shape(f['geometry']))
    return g


_srcs = None


def _init():
    global _srcs
    _srcs = [rasterio.open(SRC / f'gaced30_dza_{y}_v1.tif') for y in YEARS]


def render(zxy):
    z, x, y = zxy
    lon0, lat0, lon1, lat1 = tile_lonlat(z, x, y)
    dst_transform = from_bounds(*tile_merc(z, x, y), SIZE, SIZE)
    bits = np.zeros((SIZE, SIZE), np.uint32)
    ref = _srcs[0]
    win = window_from_bounds(lon0, lat0, lon1, lat1, ref.transform)
    win = Window(math.floor(win.col_off) - 2, math.floor(win.row_off) - 2,
                 math.ceil(win.width) + 4, math.ceil(win.height) + 4)
    win = win.intersection(Window(0, 0, ref.width, ref.height))
    wt = ref.window_transform(win)
    for i, src in enumerate(_srcs):
        a = src.read(1, window=win)
        if not (a == 10).any():
            continue
        out = np.full((SIZE, SIZE), 255, np.uint8)
        reproject(a, out, src_transform=wt, src_crs='EPSG:4326', src_nodata=255,
                  dst_transform=dst_transform, dst_crs='EPSG:3857', dst_nodata=255,
                  resampling=Resampling.mode)
        bits |= (out == 10).astype(np.uint32) << np.uint32(i)
    if not bits.any():
        return zxy, None
    return zxy, zlib.compress(bits.astype('<u4').tobytes(), 9)


def downsample(children):
    """children: dict (dx, dy) -> uint32 array; returns parent uint32 array (2 of 4 rule)."""
    big = np.zeros((SIZE * 2, SIZE * 2), np.uint32)
    for (dx, dy), arr in children.items():
        big[dy * SIZE:(dy + 1) * SIZE, dx * SIZE:(dx + 1) * SIZE] = arr
    out = np.zeros((SIZE, SIZE), np.uint32)
    for i in range(len(YEARS)):
        plane = ((big >> np.uint32(i)) & 1).astype(np.uint8)
        count = plane[0::2, 0::2] + plane[1::2, 0::2] + plane[0::2, 1::2] + plane[1::2, 1::2]
        out |= (count >= 2).astype(np.uint32) << np.uint32(i)
    return out


def decode(b):
    return np.frombuffer(zlib.decompress(b), dtype='<u4').reshape(SIZE, SIZE)


def main():
    t0 = time.time()
    geom = algeria()
    minx, miny, maxx, maxy = geom.bounds
    x0, y0 = lonlat_to_tile(minx, maxy, MAX_ZOOM)
    x1, y1 = lonlat_to_tile(maxx, miny, MAX_ZOOM)
    jobs = [(MAX_ZOOM, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)
            if box(*[tile_lonlat(MAX_ZOOM, x, y)[k] for k in (0, 1, 2, 3)]).intersects(geom)]
    print(f'z{MAX_ZOOM}: {len(jobs)} tiles intersect Algeria', flush=True)
    tiles = {}
    with Pool(8, initializer=_init) as pool:
        for n, (zxy, data) in enumerate(pool.imap_unordered(render, jobs, chunksize=16), 1):
            if data is not None:
                tiles[zxy] = data
            if n % 1000 == 0:
                print(f'  {n}/{len(jobs)}  {time.time() - t0:.0f}s', flush=True)
    print(f'z{MAX_ZOOM}: {len(tiles)} non-empty tiles', flush=True)

    for z in range(MAX_ZOOM - 1, MIN_ZOOM - 1, -1):
        parents = {}
        for (cz, cx, cy) in [k for k in tiles if k[0] == z + 1]:
            parents.setdefault((z, cx // 2, cy // 2), {})[(cx % 2, cy % 2)] = (cz, cx, cy)
        n = 0
        for pk, kids in parents.items():
            arr = downsample({d: decode(tiles[k]) for d, k in kids.items()})
            if arr.any():
                tiles[pk] = zlib.compress(arr.astype('<u4').tobytes(), 9)
                n += 1
        print(f'z{z}: {n} non-empty tiles', flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'gaced30_dza_2000_2024.pmtiles'
    with open(path, 'wb') as f:
        w = Writer(f)
        for (z, x, y) in sorted(tiles, key=lambda k: zxy_to_tileid(*k)):
            w.write_tile(zxy_to_tileid(z, x, y), tiles[(z, x, y)])
        header = {
            'tile_type': TileType.UNKNOWN, 'tile_compression': Compression.NONE,
            'min_lon_e7': int(minx * 1e7), 'min_lat_e7': int(miny * 1e7),
            'max_lon_e7': int(maxx * 1e7), 'max_lat_e7': int(maxy * 1e7),
            'center_zoom': 5, 'center_lon_e7': int((minx + maxx) / 2 * 1e7), 'center_lat_e7': int((miny + maxy) / 2 * 1e7),
        }
        w.finalize(header, {
            'name': 'GACED30 cropland extent, Algeria, 2000-2024 (AEO display tiles)',
            'attribution': 'GACED30 v1 (doi:10.5281/zenodo.18199675), CC BY 4.0; processing: Algeria Earth Observatory',
            'encoding': 'zlib-compressed little-endian uint32[256*256]; bit i = cropland in year 2000+i',
            'years': [YEARS[0], YEARS[-1]],
            'resampling': f'mode at z{MAX_ZOOM}; coarser zooms: cropland where >= 2 of 4 finer pixels are cropland',
        })
    print(f'wrote {path} {path.stat().st_size / 1e6:.1f} MB, {len(tiles)} tiles, {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
