import hashlib
from fastapi import Response

def set_cache_headers(resp: Response, etag_source: str, public_seconds: int = 300, shared_seconds: int = 600):
    etag = hashlib.sha256(etag_source.encode("utf-8")).hexdigest()
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = f"public, max-age={public_seconds}, s-maxage={shared_seconds}"
