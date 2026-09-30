#!/usr/bin/env python3
"""Local server for the YKI listening player.
Serves the study folder, translates words (Google Translate, cached), and stores saved words.
Run:  python3 _app/server.py [--port 8765] [--open]
"""
import json, sys, os, io, csv, re, time, uuid, threading, mimetypes, webbrowser, subprocess
import urllib.request, urllib.parse, urllib.error, ssl

def _ssl_context():
    ctx = ssl.create_default_context()
    try:
        import certifi; ctx.load_verify_locations(certifi.where())
    except Exception: pass
    for extra in ("/etc/ssl/cert.pem", "/private/etc/ssl/cert.pem"):
        try: ctx.load_verify_locations(extra)
        except Exception: pass
    return ctx
SSL_CTX = _ssl_context()
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
DATA = APP / "data"
CACHE = APP / "translations.json"
WORDS = APP / "sanat.json"
LOCK = threading.Lock()
LEVEL = {"1-Perustaso": "Perustaso", "2-Keskitaso": "Keskitaso", "3-Ylin-taso": "Ylin taso"}
PART = {"Puheen-ymmartaminen": "Ykitesti (official) · Puheen ymmärtäminen", "Puhuminen": "Ykitesti (official) · Puhuminen",
        "Suomikoulut": "Suomikoulut.fi", "YKI-Test-Prep": "YKI Test Prep", "Linnasmaki-Askelia-2": "Linnasmäki: Askelia aktiivisuuteen 2",
        "Osaan-suomea-Vopkoto": "Osaan suomea / Vopkoto (puhuminen)", "Yle-YKItreenit": "Yle YKItreenit", "Yle-Abitreenit-S2": "Yle Abitreenit S2"}

def load_json(p, default):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return default

def save_json(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=0), encoding="utf-8")
    os.replace(tmp, p)

# ---------- translation ----------
_tr_cache = load_json(CACHE, {})
_tr_cache.update(load_json(APP / "translations-fix.json", {}))   # hand fixes for words Google gets wrong

def _fetch_json(url, timeout=20):
    """Fetch JSON with curl. Google's free endpoint answers curl but rejects Python's HTTP client."""
    r = subprocess.run(["curl", "-sS", "--max-time", str(timeout), "-A", "Mozilla/5.0", "-w", "\\n%{http_code}", url],
                       capture_output=True, text=True)
    body, _, code = r.stdout.rpartition("\n")
    if code != "200": raise urllib.error.HTTPError(url, int(code or 0), r.stderr.strip() or "curl error", {}, None)
    return json.loads(body)

def _gtx(text):
    q = urllib.parse.urlencode({"client": "gtx", "sl": "fi", "tl": "en", "dt": "t", "q": text})
    data = _fetch_json("https://translate.googleapis.com/translate_a/single?" + q)
    return "".join(seg[0] for seg in data[0] if seg and seg[0])

def _mymemory(word):
    q = urllib.parse.urlencode({"q": word, "langpair": "fi|en"})
    data = _fetch_json("https://api.mymemory.translated.net/get?" + q)
    t = (data.get("responseData") or {}).get("translatedText") or ""
    return "" if t.upper() == word.upper() and data.get("responseStatus") != 200 else t

def _google(words):
    """Translate Finnish words to English. Google gtx in batches of 25 (newline separated); on 429 wait and retry;
    then MyMemory one by one for anything still missing."""
    out = {}
    for i in range(0, len(words), 25):
        chunk = words[i:i + 25]
        for attempt in range(3):
            try:
                lines = _gtx("\n".join(chunk)).split("\n")
                if len(lines) == len(chunk):
                    for w, t in zip(chunk, lines): out[w] = t.strip()
                break
            except urllib.error.HTTPError as e:
                print(f"gtx batch {e.code}, attempt {attempt+1}", file=sys.stderr)
                if e.code == 429: time.sleep(3 * (attempt + 1))
                else: break
            except Exception as e:
                print("gtx batch failed:", e, file=sys.stderr); break
        for w in chunk:
            if w in out: continue
            try: out[w] = _gtx(w).strip(); continue
            except Exception as e: print("gtx single failed:", w, e, file=sys.stderr)
            try: out[w] = _mymemory(w).strip()
            except Exception as e: print("mymemory failed:", w, e, file=sys.stderr)
            time.sleep(0.3)
    return out

def translate(words):
    words = [w for w in dict.fromkeys(w.strip().lower() for w in words) if w]
    with LOCK: missing = [w for w in words if w not in _tr_cache]
    if missing:
        with LOCK:  # another process (prewarm.py) may have added words to the file: merge before asking online
            for k, v in load_json(CACHE, {}).items(): _tr_cache.setdefault(k, v)
            missing = [w for w in words if w not in _tr_cache]
    if missing:
        got = _google(missing)
        with LOCK:
            _tr_cache.update(got)
            save_json(CACHE, _tr_cache)
    with LOCK: return {w: _tr_cache.get(w, "") for w in words}

# ---------- index of audio files ----------
SPEAKING = {"Puhuminen", "Osaan-suomea-Vopkoto"}   # recordings you answer out loud: own section in the player
def build_index():
    items = []; titles_cache = {}
    status = load_json(APP / "question_status.json", {})   # what each source offers: questions, answers, a note
    natural = lambda p: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(p))]
    for mp3 in sorted(ROOT.rglob("*.mp3"), key=natural):
        if mp3.relative_to(ROOT).parts[0] in ("_app", "site"): continue
        rel = mp3.relative_to(ROOT); parts = rel.parts
        rid = str(rel.with_suffix(""))
        sj = mp3.parent / "source.json"   # optional {"name": "...", "section": "listening"|"speaking"}
        if sj not in titles_cache: titles_cache[sj] = load_json(sj, {}) if sj.exists() else {}
        src = titles_cache[sj]
        tj = mp3.parent / "titles.json"
        if tj not in titles_cache: titles_cache[tj] = load_json(tj, {}) if tj.exists() else {}
        title = titles_cache[tj].get(mp3.stem)
        data = DATA / (rid + ".json")
        dur = None
        if data.exists():
            try: dur = json.loads(data.read_text(encoding="utf-8")).get("duration")
            except Exception: pass
        items.append({
            "id": rid, "mp3": str(rel), "name": mp3.stem, "title": title,
            "level": parts[0] if len(parts) > 2 else "", "levelName": LEVEL.get(parts[0], parts[0]),
            "part": parts[1] if len(parts) > 2 else "", "partName": src.get("name") or (PART.get(parts[1], parts[1].replace("-", " ")) if len(parts) > 2 else ""),
            "hasData": data.exists(), "hasQuestions": mp3.with_name(mp3.stem + ".kysymykset.txt").exists(),
            "duration": dur, "qstatus": status.get(rid),
            "section": src.get("section") or ("speaking" if len(parts) > 2 and parts[1] in SPEAKING else "listening"),
        })
    return items

# ---------- reading tasks ----------
READING = APP / "reading"
READ_PART = {"Tekstin-ymmartaminen": "Ykitesti (official) · Tekstin ymmärtäminen", "Suomikoulut": "Suomikoulut.fi", "YKI-Test-Prep": "YKI Test Prep", "Sano-suomeksi": "Sano suomeksi"}
def build_reading_index():
    natural = lambda p: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(p))]
    items = []
    for j in sorted(READING.rglob("*.json"), key=natural):
        rel = j.relative_to(READING); parts = rel.parts
        if len(parts) < 3: continue
        d = load_json(j, {})
        items.append({"id": str(rel.with_suffix("")), "level": parts[0], "levelName": LEVEL.get(parts[0], parts[0]),
                      "part": parts[1], "partName": d.get("sourceName") or READ_PART.get(parts[1], parts[1].replace("-", " ")),
                      "title": d.get("title") or j.stem, "nq": len(d.get("questions", [])), "chars": len(d.get("text", ""))})
    return items

# ---------- writing tasks ----------
WRITING = APP / "writing"
def build_writing_index():
    natural = lambda p: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(p))]
    items = []
    official_first = lambda p: (p.relative_to(WRITING).parts[0], p.relative_to(WRITING).parts[1] != "Ykitesti", natural(p))
    for j in sorted(WRITING.rglob("*.json"), key=official_first):
        rel = j.relative_to(WRITING); parts = rel.parts
        if len(parts) < 3: continue
        d = load_json(j, {})
        items.append({"id": str(rel.with_suffix("")), "level": parts[0], "levelName": LEVEL.get(parts[0], parts[0]),
                      "part": parts[1], "partName": d.get("sourceName") or parts[1].replace("-", " "),
                      "title": d.get("title") or j.stem, "kind": d.get("kind", ""), "nm": len(d.get("models", []))})
    return items

# ---------- saved words ----------
def words_all():
    with LOCK: return load_json(WORDS, [])

def words_add(entry):
    e = {"id": uuid.uuid4().hex[:10], "added": time.strftime("%Y-%m-%d %H:%M"),
         "word": str(entry.get("word", "")).strip().lower(), "display": str(entry.get("display", "")).strip(),
         "translation": str(entry.get("translation", "")).strip(), "context": str(entry.get("context", "")).strip(),
         "source": str(entry.get("source", "")), "time": float(entry.get("time", 0) or 0)}
    if not e["word"]: return None
    with LOCK:
        lst = load_json(WORDS, [])
        for x in lst:
            if x["word"] == e["word"]: return x
        lst.append(e); save_json(WORDS, lst)
    return e

def words_delete(wid):
    with LOCK:
        lst = load_json(WORDS, []); new = [x for x in lst if x["id"] != wid]
        save_json(WORDS, new); return len(new) != len(lst)

def words_csv():
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["word", "translation", "context", "source", "added"])
    for x in words_all(): w.writerow([x["display"] or x["word"], x["translation"], x["context"], x["source"], x["added"]])
    return "﻿" + buf.getvalue()

# ---------- HTTP ----------
class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        if "/api/" in self.path or self.path == "/": super().log_message(fmt, *a)

    def send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

    def send_text(self, text, ctype, code=200, download=None):
        b = text.encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ctype + "; charset=utf-8")
        if download: self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def send_file(self, path: Path):
        if not path.is_file(): return self.send_error(404)
        size = path.stat().st_size
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if path.suffix in (".txt", ".json", ".html", ".css", ".js"): ctype += "; charset=utf-8"
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        m = re.match(r"bytes=(\d*)-(\d*)", rng or "")
        if m and (m.group(1) or m.group(2)):
            if m.group(1): start = int(m.group(1)); end = int(m.group(2)) if m.group(2) else size - 1
            else: start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            if start > end: self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.end_headers(); return
            self.send_response(206); self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        length = end - start + 1
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes"); self.send_header("Cache-Control", "no-cache"); self.end_headers()
        with open(path, "rb") as f:
            f.seek(start); left = length
            while left > 0:
                chunk = f.read(min(1 << 16, left))
                if not chunk: break
                try: self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError): return
                left -= len(chunk)

    def safe_path(self, url_path):
        rel = urllib.parse.unquote(url_path).lstrip("/")
        p = (ROOT / rel).resolve()
        if ROOT not in p.parents and p != ROOT: return None
        return p

    def _path(self):
        try: return self.path.encode("latin-1").decode("utf-8")   # raw UTF-8 bytes in the request line
        except Exception: return self.path

    def do_GET(self):
        u = urllib.parse.urlparse(self._path()); qs = urllib.parse.parse_qs(u.query); path = u.path
        if path == "/": return self.send_file(APP / "index.html")
        if path == "/api/index": return self.send_json(build_index())
        if path == "/api/reading": return self.send_json(build_reading_index())
        if path == "/api/writing": return self.send_json(build_writing_index())
        if path == "/api/words": return self.send_json(words_all())
        if path == "/api/words.csv": return self.send_text(words_csv(), "text/csv", download="yki-sanat.csv")
        if path == "/api/translate":
            words = [w for w in qs.get("w", [""])[0].split(",") if w]
            return self.send_json(translate(words))
        if path.startswith("/files/"):
            p = self.safe_path(path[len("/files"):])
            return self.send_file(p) if p else self.send_error(403)
        self.send_error(404)

    def do_POST(self):
        u = urllib.parse.urlparse(self._path())
        n = int(self.headers.get("Content-Length") or 0)
        try: body = json.loads(self.rfile.read(n) or b"null")
        except Exception: body = None
        if u.path == "/api/translate" and isinstance(body, list): return self.send_json(translate([str(w) for w in body]))
        if u.path == "/api/words" and isinstance(body, dict):
            e = words_add(body); return self.send_json(e) if e else self.send_json({"error": "empty word"}, 400)
        self.send_error(404)

    def do_DELETE(self):
        u = urllib.parse.urlparse(self._path()); qs = urllib.parse.parse_qs(u.query)
        if u.path == "/api/words":
            ok = words_delete(qs.get("id", [""])[0]); return self.send_json({"ok": ok})
        self.send_error(404)

def main():
    port = 8765
    if "--port" in sys.argv: port = int(sys.argv[sys.argv.index("--port") + 1])
    host = "0.0.0.0" if "--lan" in sys.argv else "127.0.0.1"   # --lan: reachable from a phone on the same Wi-Fi
    srv = ThreadingHTTPServer((host, port), H)
    url = f"http://127.0.0.1:{port}/"
    print(f"YKI player: {url}  (folder: {ROOT})", flush=True)
    if host == "0.0.0.0":
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try: s.connect(("192.0.2.1", 9)); print(f"On your phone: http://{s.getsockname()[0]}:{port}/", flush=True)
            except OSError: pass
    if "--open" in sys.argv: webbrowser.open(url)
    try: srv.serve_forever()
    except KeyboardInterrupt: pass

if __name__ == "__main__": main()
