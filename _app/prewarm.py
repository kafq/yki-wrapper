#!/usr/bin/env python3
"""Translate every word in all transcripts once, so hovering is instant and works offline afterwards."""
import json, re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import server
DATA = server.DATA
def key(w): return re.sub(r"^-+|-+$", "", re.sub(r"[^\w-]", "", w, flags=re.U)).lower()
words = set()
for p in DATA.rglob("*.json"):
    for seg in json.loads(p.read_text(encoding="utf-8"))["segments"]:
        for w in seg.get("words", []):
            k = key(w["w"])
            if k and not re.fullmatch(r"[\d-]+", k): words.add(k)
missing = sorted(w for w in words if w not in server._tr_cache)
print(f"{len(words)} unique words, {len(missing)} not cached yet", flush=True)
for i in range(0, len(missing), 100):
    chunk = missing[i:i + 100]
    res = server.translate(chunk)
    print(f"  {i + len(chunk)}/{len(missing)}  ({sum(1 for v in res.values() if v)} ok)", flush=True)
print("cache size:", len(server._tr_cache))
