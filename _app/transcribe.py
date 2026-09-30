#!/usr/bin/env python3
"""Transcribe all MP3s in the YKI folder with Whisper (mlx-whisper), with word timestamps.
Pass 1: normal Whisper run. Pass 2: Whisper sometimes skips a whole 30-second window, so every gap of 4 s or more
that has sound at speech level is re-transcribed as its own clip and merged in. Hallucinations on noise are filtered.
Writes _app/data/<file>.json for the player and <file>.txt next to each MP3.
Usage: python3 _app/transcribe.py [--force] [path-filter]"""
import json, re, subprocess, pathlib, sys, time, tempfile
import mlx_whisper
ROOT = pathlib.Path(__file__).resolve().parent.parent; DATA = ROOT / "_app" / "data"
MODEL = "mlx-community/whisper-large-v3-turbo"
MIN_GAP, MARGIN, REL_DB = 4.0, 0.15, 8.0
HALLU = re.compile(r"tekstit|katso|kiitos kun|www\.|\.com|tilaa kanava|amara\.org", re.I)
FILLER = {"kiitos", "nyt", "niin", "joo", "ja", "no", "hmm", "mm", "ok", "okei", "hei", "kyllä", "ei"}
TMP = pathlib.Path(tempfile.gettempdir()) / "yki_clip.wav"
def ts(s): m, sec = divmod(int(s), 60); return f"{m:02d}:{sec:02d}"
def norm(t): return re.sub(r"[^\wäöå]+", " ", t.lower()).strip()
def mean_volume(mp3, a, b):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(mp3), "-ss", f"{a:.2f}", "-to", f"{b:.2f}", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: ([-\d.]+) dB", out); return float(m.group(1)) if m else -99.0
def duration(mp3):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)], capture_output=True, text=True).stdout.strip() or 0)
def to_segments(result, offset=0.0, strict=False):
    segs = []
    for s in result["segments"]:
        t = s["text"].strip()
        if not t: continue
        if strict:
            if s.get("no_speech_prob", 0) > 0.5 or s.get("avg_logprob", 0) < -1.0 or HALLU.search(t): continue
            if norm(t) in FILLER or len(norm(t)) < 3: continue
        words = [{"w": w["word"].strip(), "s": round(offset + w["start"], 2), "e": round(offset + w["end"], 2)} for w in s.get("words", []) if w["word"].strip()]
        segs.append({"start": round(offset + s["start"], 2), "end": round(offset + s["end"], 2), "text": t, "words": words})
    return segs
def transcribe(path):
    return mlx_whisper.transcribe(str(path), path_or_hf_repo=MODEL, language="fi", verbose=False, condition_on_previous_text=False, word_timestamps=True)
def gaps(segs, dur):
    pts = [(0.0, segs[0]["start"])] if segs else [(0.0, dur)]
    pts += [(segs[i]["end"], segs[i + 1]["start"]) for i in range(len(segs) - 1)]
    if segs: pts.append((segs[-1]["end"], dur))
    return [(a, b) for a, b in pts if b - a >= MIN_GAP]
def clip_segments(mp3, a, b, dur):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(mp3), "-ss", f"{max(0, a - MARGIN):.2f}", "-to", f"{min(dur, b + MARGIN):.2f}", "-ac", "1", "-ar", "16000", str(TMP)], check=True)
    return to_segments(transcribe(TMP), offset=max(0, a - MARGIN), strict=True)
def transcribe_gap(mp3, a, b, dur, speech_db, depth=0):
    """Transcribe the range a-b as its own clip. If Whisper gives nothing, split the clip and retry;
    if it covers only part of the range, retry on the uncovered parts (2 levels deep)."""
    if b - a < 3: return []
    new = clip_segments(mp3, a, b, dur)
    if not new:
        if depth < 2 and b - a >= 8:
            mid = (a + b) / 2
            return transcribe_gap(mp3, a, mid, dur, speech_db, depth + 1) + transcribe_gap(mp3, mid, b, dur, speech_db, depth + 1)
        return []
    covered = sum(n["end"] - n["start"] for n in new)
    if depth < 2 and b - a >= 10 and covered < 0.3 * (b - a):      # a lone word for a long clip: split and retry
        mid = (a + b) / 2
        alt = transcribe_gap(mp3, a, mid, dur, speech_db, depth + 1) + transcribe_gap(mp3, mid, b, dur, speech_db, depth + 1)
        if sum(n["end"] - n["start"] for n in alt) > covered: return alt
    if depth < 2:
        pts = [a]
        for n in sorted(new, key=lambda n: n["start"]): pts += [n["start"], n["end"]]
        pts.append(b)
        for x, y in zip(pts[0::2], pts[1::2]):
            if y - x >= MIN_GAP and mean_volume(mp3, x, y) >= speech_db - REL_DB:
                new += transcribe_gap(mp3, x, y, dur, speech_db, depth + 1)
    return new
def fill_gaps(mp3, segs, dur, log):
    ref = sorted(segs, key=lambda s: s["end"] - s["start"], reverse=True)[:5]
    speech_db = sum(mean_volume(mp3, s["start"], s["end"]) for s in ref) / len(ref) if ref else -25.0
    added = []
    for a, b in gaps(segs, dur):
        vol = mean_volume(mp3, a, b)
        if vol < speech_db - REL_DB: continue           # silence or room noise
        new = transcribe_gap(mp3, a, b, dur, speech_db)
        near = [s for s in segs if abs(s["start"] - a) < 4 or abs(s["end"] - b) < 4]
        new = [n for n in new if not any(norm(n["text"]) == norm(s["text"]) for s in near)]   # boundary duplicates
        if new: log.append(f"    filled {ts(a)}-{ts(b)}: " + " | ".join(n["text"][:50] for n in sorted(new, key=lambda n: n["start"])[:3]))
        added += new
    return sorted(segs + added, key=lambda s: s["start"])
def polish(segs):
    """Drop runs of 3+ identical short lines (Whisper stuck on noise)."""
    out = []; i = 0
    while i < len(segs):
        j = i
        while j < len(segs) and norm(segs[j]["text"]) == norm(segs[i]["text"]): j += 1
        dense = j - i >= 3 and (segs[j - 1]["start"] - segs[i]["start"]) < 3 * (j - i)   # e.g. 11 copies within 5 s
        if not dense or len(norm(segs[i]["text"]).split()) > 3: out += segs[i:j]            # real cues 30 s apart are kept
        i = j
    return out
def write(mp3, rel, dur, segs):
    out = DATA / rel.with_suffix(".json"); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"file": str(rel) + ".mp3", "duration": round(dur, 2), "segments": segs}, ensure_ascii=False), encoding="utf-8")
    with open(mp3.with_suffix(".txt"), "w", encoding="utf-8") as f:
        f.write(f"Transkripti: {mp3.name} (kesto {ts(dur)})\nTehty automaattisesti Whisper-mallilla ({MODEL}). Voi sisältää virheitä.\n\n--- Teksti ---\n")
        f.write(" ".join(s["text"] for s in segs) + "\n\n--- Aikaleimat ---\n")
        for s in segs: f.write(f"[{ts(s['start'])}] {s['text']}\n")
def main():
    force = "--force" in sys.argv; flt = [a for a in sys.argv[1:] if not a.startswith("--")]
    files = [p for p in sorted(ROOT.rglob("*.mp3")) if p.relative_to(ROOT).parts[0] not in ("_app", "site") and (not flt or any(f in str(p) for f in flt))]
    for i, mp3 in enumerate(files, 1):
        rel = mp3.relative_to(ROOT).with_suffix("")
        if not force and (DATA / rel.with_suffix(".json")).exists(): print(f"[{i}/{len(files)}] skip {rel}", flush=True); continue
        t0 = time.time(); dur = duration(mp3); log = []
        segs = to_segments(transcribe(mp3))
        n0 = len(segs); segs = polish(fill_gaps(mp3, segs, dur, log))
        write(mp3, rel, dur, segs)
        print(f"[{i}/{len(files)}] {rel}  {ts(dur)} audio, {time.time() - t0:.0f}s, {n0} segments + {len(segs) - n0} filled", flush=True)
        for l in log: print(l, flush=True)
    print("DONE")
if __name__ == "__main__": main()
