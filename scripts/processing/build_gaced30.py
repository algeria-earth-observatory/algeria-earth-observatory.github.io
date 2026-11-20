"""Build the AEO GACED30 Algeria products from the source tiles.

Inputs : data-work/gaced30/raw/Crop_<lon>_<lat>.tif  (fetch_gaced30.py; GACED30 v1,
         doi:10.5281/zenodo.18199675, 25 bands = 2000..2024, 0 non-cropland,
         10 cropland, 255 no data, EPSG:4326, 11132 x 11132 pixels of 0.000269494585 deg
         (30 m at the equator), each tile anchored on a whole-degree multiple of 3)
         Algeria outline: public/data/aeo/boundaries/<version>/dza_adm0.geojson
Outputs: <out>/gaced30_dza_<year>_v1.tif  one Cloud Optimized GeoTIFF per year, on the
         common grid anchored at 12 W / 39 N with the GACED30 pixel size, values unchanged,
         pixels outside Algeria = 255. Because a tile spans 3.0000137 deg, not exactly 3 deg,
         tiles are placed at the nearest whole pixel (shift < 0.5 pixel, < 15 m); where
         neighbouring tiles overlap by one pixel, the later tile (east / north) is kept.

Usage: python scripts/processing/build_gaced30.py [years...]   (default: all 2000-2024)
"""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import rasterio
import rasterio.shutil
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from rasterio.windows import Window
from shapely.geometry import box, shape

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'data-work' / 'gaced30' / 'raw'
TMP = ROOT / 'data-work' / 'gaced30' / 'tmp'
OUT = ROOT / 'data-work' / 'gaced30' / 'out'
BOUNDARY = ROOT / 'public' / 'data' / 'aeo' / 'boundaries' / '2026-11-19' / 'dza_adm0.geojson'
YEARS = list(range(2000, 2025))
TILE_PX = 11132
RES = 0.0002694945852358564  # GACED30 pixel size (degrees)
LON0, LAT0 = -12.0, 39.0  # grid origin on GACED30 tile corners (multiples of 3 degrees)
NODATA = 255


def algeria():
    gj = json.loads(BOUNDARY.read_text(encoding='utf-8'))
    geoms = [shape(f['geometry']) for f in gj['features']]
    g = geoms[0]
    for o in geoms[1:]:
        g = g.union(o)
    return g


def grid(geom):
    minx, miny, maxx, maxy = geom.bounds
    c0 = int(np.floor((minx - LON0) / RES)); c1 = int(np.ceil((maxx - LON0) / RES))
    r0 = int(np.floor((LAT0 - maxy) / RES)); r1 = int(np.ceil((LAT0 - miny) / RES))
    transform = Affine(RES, 0, LON0 + c0 * RES, 0, -RES, LAT0 - r0 * RES)
    return transform, c1 - c0, r1 - r0


def build_year(year):
    t0 = time.time()
    geom = algeria()
    transform, width, height = grid(geom)
    band = year - 2000 + 1
    TMP.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    tmp = TMP / f'gaced30_dza_{year}.tif'
    profile = dict(driver='GTiff', dtype='uint8', count=1, width=width, height=height, crs='EPSG:4326',
                   transform=transform, nodata=NODATA, tiled=True, blockxsize=512, blockysize=512,
                   compress='deflate', sparse_ok=True, bigtiff='if_safer')
    tiles = 0
    with rasterio.open(tmp, 'w', **profile) as dst:
        for p in sorted(RAW.glob('Crop_*.tif')):
            lon, lat = (float(v) for v in p.stem[5:].split('_'))
            if not box(lon, lat, lon + 3, lat + 3).intersects(geom):
                continue
            tiles += 1
            with rasterio.open(p) as src:
                assert src.count == 25 and abs(src.res[0] - RES) < 1e-15, (p, src.res)
                assert src.descriptions[band - 1] in (None, f'Crop_{year}'), src.descriptions[band - 1]
                # destination window of this source tile
                col = round((lon - transform.c) / RES); row = round((transform.f - (lat + 3)) / RES)
                # clip the tile to the output grid
                sc0, sr0 = max(0, -col), max(0, -row)
                sc1, sr1 = min(TILE_PX, width - col), min(TILE_PX, height - row)
                if sc1 <= sc0 or sr1 <= sr0:
                    continue
                for r in range(sr0, sr1, 2048):
                    r_end = min(r + 2048, sr1)
                    win = Window(sc0, r, sc1 - sc0, r_end - r)
                    a = src.read(band, window=win)
                    wt = src.window_transform(win)
                    outside = geometry_mask([geom], out_shape=a.shape, transform=wt, invert=False)
                    if outside.all():
                        continue
                    a[outside] = NODATA
                    dst.write(a, 1, window=Window(col + sc0, row + r, sc1 - sc0, r_end - r))
        dst.set_band_description(1, f'Cropland {year} (GACED30 v1): 0 non-cropland, 10 cropland, 255 no data / outside Algeria')
        dst.update_tags(source='GACED30 v1, doi:10.5281/zenodo.18199675', year=str(year),
                        license='CC BY 4.0', processing='Clipped to Algeria by the Algeria Earth Observatory; values unchanged')
    out = OUT / f'gaced30_dza_{year}_v1.tif'
    with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True):
        rasterio.shutil.copy(tmp, out, driver='COG', compress='DEFLATE', level=9, overview_resampling='mode',
                             blocksize=512, bigtiff='IF_SAFER')
    tmp.unlink()
    return year, tiles, out.stat().st_size, round(time.time() - t0)


if __name__ == '__main__':
    years = [int(y) for y in sys.argv[1:]] or YEARS
    with Pool(min(6, len(years))) as pool:
        for year, tiles, size, secs in pool.imap_unordered(build_year, years):
            print(f'{year}: {tiles} source tiles, {size / 1e6:.1f} MB, {secs}s', flush=True)
