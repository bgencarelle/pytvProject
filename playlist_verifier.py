#!/usr/bin/env python3
import json, sys, pathlib
from channel_manager import _cache_path

root = pathlib.Path(sys.argv[1] if len(sys.argv)>1 else "movies")
cache = json.load(open(_cache_path(str(root))))
for ch,rec in cache["channels"].items():
    sum_us = sum(rec["duration_us"])
    ok = "✓" if sum_us==rec["total_us"] else "✗"
    print(f"CH {ch:>2}:  files={len(rec['files'])}  "
          f"total {rec['total_us']/1e6:8.3f}s  ({ok})")