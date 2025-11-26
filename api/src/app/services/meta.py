import json, os
from . import paths

def read_meta():
    meta_path = os.path.join(paths.CURRENT, "meta.json")
    if not os.path.exists(meta_path):
        return {"version": None, "created_at": None, "modules": []}
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)
