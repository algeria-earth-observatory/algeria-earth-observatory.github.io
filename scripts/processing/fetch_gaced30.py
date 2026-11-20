"""Fetch the GACED30 tiles that cover Algeria from the Zenodo ZIP packages.

GACED30 v1 (doi:10.5281/zenodo.18199675) is published as 60 ZIP packages, one per
6 degrees of longitude, each holding 3 x 3 degree 25-band GeoTIFF tiles named
Crop_<lon>_<lat>.tif. Only the tiles near Algeria are read: the ZIP directory is read
with HTTP range requests, then each member's compressed bytes are fetched in a single
request and inflated locally. The 5.7 GB of packages is not downloaded.

Usage: python scripts/processing/fetch_gaced30.py [out_dir]
"""
import hashlib
import json
import struct
import sys
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from httpzip import HTTPFile  # noqa: E402

RECORD = 'https://zenodo.org/api/records/18199675'
PACKAGES = ['lon_-012_to_-006.zip', 'lon_-006_to_+000.zip', 'lon_+000_to_+006.zip', 'lon_+006_to_+012.zip']
# Algeria lies within 8.7W-12.0E, 18.9N-37.2N; the margin covers either tile-corner convention.
LON_MIN, LON_MAX, LAT_MIN, LAT_MAX = -12, 12, 15, 39


def get_range(url, start, end):
    req = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def fetch_member(url, info, dest):
    if dest.exists() and dest.stat().st_size == info.file_size:
        return 'cached'
    head = get_range(url, info.header_offset, info.header_offset + 29)
    if struct.unpack('<I', head[:4])[0] != 0x04034B50:
        raise ValueError('bad local file header')
    name_len, extra_len = struct.unpack('<HH', head[26:30])
    start = info.header_offset + 30 + name_len + extra_len
    data = get_range(url, start, start + info.compress_size - 1)
    if info.compress_type == zipfile.ZIP_DEFLATED:
        data = zlib.decompressobj(-15).decompress(data)
    elif info.compress_type != zipfile.ZIP_STORED:
        raise ValueError(f'unsupported compression {info.compress_type}')
    if len(data) != info.file_size or zlib.crc32(data) != info.CRC:
        raise ValueError(f'size/CRC mismatch for {info.filename}')
    tmp = dest.with_suffix('.part')
    tmp.write_bytes(data)
    tmp.replace(dest)
    return 'downloaded'


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else 'data-work/gaced30/raw')
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for pkg in PACKAGES:
        url = f'{RECORD}/files/{pkg}/content'
        for info in zipfile.ZipFile(HTTPFile(url)).infolist():
            stem = info.filename.rsplit('/', 1)[-1]
            if not (stem.startswith('Crop_') and stem.endswith('.tif')):
                continue
            lon, lat = (float(v) for v in stem[5:-4].split('_'))
            if LON_MIN <= lon < LON_MAX and LAT_MIN <= lat < LAT_MAX:
                jobs.append((pkg, url, info, out / stem))
    print(f'{len(jobs)} tiles selected', flush=True)

    def run(job):
        pkg, url, info, dest = job
        status = fetch_member(url, info, dest)
        print(f'{status:10s} {pkg} {dest.name} {info.file_size / 1e6:.1f} MB', flush=True)
        return {'package': pkg, 'member': info.filename, 'bytes': info.file_size,
                'crc32': f'{info.CRC:08x}', 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()}

    with ThreadPoolExecutor(6) as ex:
        log = sorted(ex.map(run, jobs), key=lambda r: r['member'])
    (out / 'fetch_log.json').write_text(json.dumps(
        {'record': RECORD, 'doi': '10.5281/zenodo.18199675', 'files': log}, indent=2))
    print(f'{len(log)} tiles in {out}, {sum(r["bytes"] for r in log) / 1e6:.0f} MB')


if __name__ == '__main__':
    main()
