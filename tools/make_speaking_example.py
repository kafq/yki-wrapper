#!/usr/bin/env python3
"""Make the example speaking tasks with macOS text-to-speech (voices Satu and Reed, fi_FI).
Each part is (voice, text, seconds of answer time). After a prompt with answer time the script adds a beep
and silence. The transcript comes from the script text, so no Whisper step is needed.
Usage (macOS only): python3 tools/make_speaking_example.py"""
import json, subprocess, pathlib, tempfile
REPO = pathlib.Path(__file__).resolve().parent.parent
T = pathlib.Path(tempfile.mkdtemp(prefix="yki_tts_"))
NAR, OTHER = "Satu", "Reed (Finnish (Finland))"
def run(*a): subprocess.run(a, check=True, capture_output=True)
def dur(p): return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)],capture_output=True,text=True).stdout)
run("ffmpeg","-y","-f","lavfi","-i","sine=frequency=880:duration=0.3","-ar","22050","-ac","1",str(T / "beep.wav"))
def build(name, parts):
    files, segs, t = [], [], 0.0
    for k, (voice, text, pause) in enumerate(parts):
        a = T / f"{name}_{k}.aiff"; wv = T / f"{name}_{k}.wav"
        run("say", "-v", voice, "-r", "165", "-o", str(a), text)
        run("ffmpeg","-y","-i",str(a),"-ar","22050","-ac","1",str(wv))
        d = dur(wv); words = text.split(); step = d / len(words)
        segs.append({"start": round(t + .05, 2), "end": round(t + d, 2), "text": text,
                     "words": [{"w": w_, "s": round(t + i * step, 2), "e": round(t + (i + 1) * step, 2)} for i, w_ in enumerate(words)]})
        files.append(wv); t += d
        gap = T / f"{name}_{k}_gap.wav"
        if pause:
            run("ffmpeg","-y","-f","lavfi","-i","anullsrc=r=22050:cl=mono","-t","0.6",str(gap)); files += [gap, T/"beep.wav"]
            sil = T / f"{name}_{k}_sil.wav"; run("ffmpeg","-y","-f","lavfi","-i","anullsrc=r=22050:cl=mono","-t",str(pause),str(sil)); files.append(sil)
            t += 0.6 + 0.3 + pause
        else:
            run("ffmpeg","-y","-f","lavfi","-i","anullsrc=r=22050:cl=mono","-t","0.8",str(gap)); files.append(gap); t += 0.8
    lst = T / f"{name}.txt"; lst.write_text("".join(f"file '{f.resolve()}'\n" for f in files))
    return lst, segs, t
def publish(level, source, name, parts, title):
    lst, segs, total = build(name, parts)
    out = REPO / level / source / f"{name}.mp3"; out.parent.mkdir(parents=True, exist_ok=True)
    run("ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-ac","1","-b:a","64k",str(out))
    total = round(dur(out), 2)
    rel = f"{level}/{source}/{name}"
    d = REPO / "_app/data" / f"{rel}.json"; d.parent.mkdir(parents=True, exist_ok=True)
    d.write_text(json.dumps({"file": f"{name}.mp3", "duration": total, "segments": segs}, ensure_ascii=False))
    ts = lambda s: f"{int(s)//60:02d}:{int(s)%60:02d}"
    (REPO / f"{rel}.txt").write_text(f"Transkripti: {name}.mp3 (kesto {ts(total)})\nKäsikirjoitus (tekstistä puheeksi, macOS-äänet {NAR} ja Reed). Ei Whisper-litteraatiota.\n\n--- Teksti ---\n"
        + " ".join(s["text"] for s in segs) + "\n\n--- Aikaleimat ---\n" + "".join(f"[{ts(s['start'])}] {s['text']}\n" for s in segs))
    print(rel, total, "s")

S1 = [(NAR, "Tilanteet. Kuulet neljä tilannetta. Reagoi jokaiseen tilanteeseen. Kun kuulet äänimerkin, aloita puhuminen. Sinulla on aikaa 15 sekuntia.", 0),
      (NAR, "Tilanne yksi. Olet kaupassa. Et löydä maitoa. Kysy myyjältä apua.", 15),
      (NAR, "Tilanne kaksi. Ystäväsi kutsuu sinut elokuviin tänä iltana, mutta sinulla on kiire. Kieltäydy kohteliaasti.", 15),
      (NAR, "Tilanne kolme. Soitat terveysasemalle. Haluat varata ajan lääkärille. Kerro, mikä sinua vaivaa.", 15),
      (NAR, "Tilanne neljä. Naapurisi auttoi sinua muutossa. Kiitä häntä.", 15),
      (NAR, "Tehtävä on päättynyt.", 0)]
S2 = [(NAR, "Keskustelu. Haluat liittyä kuntosalin jäseneksi. Soitat kuntosalin asiakaspalveluun. Kuulet asiakaspalvelijan puheenvuorot. Vastaa jokaisen puheenvuoron jälkeen, kun kuulet äänimerkin.", 0),
      (OTHER, "Hyvää päivää, Kuntokeskus Voima, Mikko puhelimessa. Miten voin auttaa?", 20),
      (OTHER, "Selvä juttu. Meillä on kaksi vaihtoehtoa: kuukausijäsenyys ja vuosijäsenyys. Kumpi kiinnostaa sinua enemmän?", 20),
      (OTHER, "Hyvä valinta. Oletko käynyt kuntosalilla aiemmin, vai tarvitsetko ohjausta laitteiden käytössä?", 20),
      (OTHER, "Meillä on myös ryhmäliikuntatunteja, esimerkiksi joogaa ja zumbaa. Haluatko kuulla niistä lisää?", 20),
      (OTHER, "Tunteja on joka päivä, ja ne kuuluvat jäsenyyden hintaan. Milloin haluaisit tulla tekemään sopimuksen?", 15),
      (OTHER, "Sopii hyvin. Tervetuloa! Muistathan ottaa henkilöllisyystodistuksen mukaan.", 10),
      (NAR, "Keskustelu on päättynyt.", 0)]
if __name__ == "__main__":
  publish("1-Perustaso", "Esimerkit-Puhuminen", "Tilanteet", S1, "Tilanteet")
  publish("2-Keskitaso", "Esimerkit-Puhuminen", "Keskustelu-kuntosali", S2, "Keskustelu: kuntosali")
