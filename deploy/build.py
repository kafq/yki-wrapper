#!/usr/bin/env python3
"""Build the static site into site/ (for Vercel or any static host).
- Audio is re-encoded to 48 kbps mono MP3 (speech stays clear, size drops by about half).
- All words in transcripts and reading texts are translated once and shipped as data/translations.json.
- Saved words are kept in the browser (deploy/static.js). The password check is deploy/middleware.js.
Run:  python3 deploy/build.py      then:  cd site && vercel deploy --prod
"""
import json, re, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
APP = ROOT / "_app"
SITE = ROOT / "site"
sys.path.insert(0, str(APP))
import server  # reuses the index builders and the translation cache

def key(w): return re.sub(r"^-+|-+$", "", re.sub(r"[^\w-]", "", w, flags=re.U)).lower()

def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime: shutil.copy2(src, dst)

def encode(src, dst):
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime: return
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "44100", "-b:a", "48k",
                    "-map_metadata", "-1", str(dst)], check=True)

def main():
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    items = server.build_index(); reading = server.build_reading_index(); writing = server.build_writing_index()
    files = SITE / "files"
    keep = set()
    for i, it in enumerate(items, 1):
        src = ROOT / it["mp3"]; dst = files / it["mp3"]; encode(src, dst); keep.add(dst)
        for extra in (APP / "data" / (it["id"] + ".json"), APP / "questions" / (it["id"] + ".json"), ROOT / (it["id"] + ".kysymykset.txt")):
            if extra.exists():
                d = files / extra.relative_to(ROOT); copy(extra, d); keep.add(d)
        print(f"\r  audio {i}/{len(items)}", end="", flush=True)
    print()
    for it in reading:
        src = APP / "reading" / (it["id"] + ".json"); d = files / src.relative_to(ROOT); copy(src, d); keep.add(d)
    for it in writing:
        src = APP / "writing" / (it["id"] + ".json"); d = files / src.relative_to(ROOT); copy(src, d); keep.add(d)
        for img in json.loads(src.read_text(encoding="utf-8")).get("images", []):
            s2 = ROOT / img
            if s2.exists(): d = files / img; copy(s2, d); keep.add(d)
    for p in files.rglob("*"):   # drop files that are no longer in the index
        if p.is_file() and p not in keep: p.unlink()

    # translations for every word the player can show
    words = set()
    for p in (APP / "data").rglob("*.json"):
        for seg in json.loads(p.read_text(encoding="utf-8")).get("segments", []):
            for w in seg.get("words", []) or [{"w": x} for x in seg.get("text", "").split()]: words.add(key(w["w"]))
    for p in (APP / "reading").rglob("*.json"):
        for w in json.loads(p.read_text(encoding="utf-8")).get("text", "").split(): words.add(key(w))
    for p in (APP / "writing").rglob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        for t in [d.get("task", "")] + [m.get("text", "") for m in d.get("models", [])]:
            for w in t.split(): words.add(key(w))
    words = {w for w in words if w and not re.fullmatch(r"[\d-]+", w)}
    missing = sorted(w for w in words if w not in server._tr_cache)
    if missing:
        print(f"  translating {len(missing)} new words…", flush=True)
        for i in range(0, len(missing), 100): server.translate(missing[i:i + 100])
    tr = {w: server._tr_cache.get(w, "") for w in sorted(words)}

    write = lambda name, obj: (SITE / "data" / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write("index.json", items); write("reading.json", reading); write("writing.json", writing); write("translations.json", tr)

    html = (APP / "index.html").read_text(encoding="utf-8")
    html = html.replace("<script>\nconst $=", '<script src="/static.js"></script>\n<script>\nconst $=', 1)
    assert "/static.js" in html, "index.html layout changed: static.js hook not found"
    (SITE / "index.html").write_text(html, encoding="utf-8")
    for f in ("static.js", "middleware.js", "vercel.json"): shutil.copy2(HERE / f, SITE / f)
    (SITE / "robots.txt").write_text("User-agent: *\nDisallow: /\n")

    size = sum(p.stat().st_size for p in SITE.rglob("*") if p.is_file() and ".vercel" not in p.parts)
    print(f"  {len(items)} recordings, {len(reading)} reading tasks, {len(writing)} writing tasks, {len(tr)} words, {size/1e6:.0f} MB in {SITE}")

if __name__ == "__main__": main()
