"""List a remote ZIP using HTTP range requests (no full download)."""
import io, sys, zipfile, urllib.request

class HTTPFile(io.RawIOBase):
    def __init__(self, url):
        self.url = url; self.pos = 0
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req) as r: self.size = int(r.headers['Content-Length'])
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def read(self, n=-1):
        if n < 0: n = self.size - self.pos
        if n == 0 or self.pos >= self.size: return b''
        end = min(self.size, self.pos + n) - 1
        req = urllib.request.Request(self.url, headers={'Range': f'bytes={self.pos}-{end}'})
        with urllib.request.urlopen(req) as r: b = r.read()
        self.pos += len(b); return b
    def readinto(self, b):
        d = self.read(len(b)); b[:len(d)] = d; return len(d)

if __name__ == '__main__':
    z = zipfile.ZipFile(HTTPFile(sys.argv[1]))
    infos = z.infolist()
    print(len(infos), 'entries')
    for i in infos[:8]: print(i.filename, i.compress_type, i.file_size, i.compress_size, i.header_offset)
    import collections
    print(collections.Counter(i.compress_type for i in infos))
