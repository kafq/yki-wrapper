# Agent instructions

You are working in the YKI wrapper: a local study player for the Finnish YKI
test. The code is in `_app/` and `deploy/`. Content lives in level folders
and is collected by you, for the user's personal study.

Read this whole file before you add content. The formats below are the
contract between your files and the player. If a file does not match, the
player skips it or breaks.

## Rules

1. **Never invent answers.** Fill `correct`, `model` and example answers only
   with what the source itself gives. When the source has no answer key, leave
   them empty and say so in `_app/question_status.json`. The player then shows
   "No answers available". A wrong answer key is worse than none.
2. **Always keep the source.** Every folder gets a `LAHDE.txt` with the URL,
   the publisher and the date you downloaded it. Every JSON has `source`.
3. **Public material only.** Do not log in, do not get past paywalls, do not use
   the user's accounts. Skip sites that block downloads, and note why in
   `docs/SOURCES.md`.
4. **Personal use.** Collected content stays on this machine. It is
   git-ignored. Do not commit it, and do not remove those lines from
   `.gitignore`.
5. **Finnish text exactly as in the source.** Fix only extraction damage, such
   as words broken across lines in PDFs.
6. **Check your work.** After you add content, run the checks at the end of this
   file and open the player.
7. **Report doubts.** Tell the user what you could not get, what you guessed
   (for example, which recording an exercise belongs to), and what they should
   check by hand.

## Layout

    <level>/<source>/<name>.mp3              audio (level: 1-Perustaso | 2-Keskitaso | 3-Ylin-taso)
    <level>/<source>/<name>.kysymykset.txt   plain-text questions; its presence tells the player questions exist
    <level>/<source>/<name>.txt              transcript (made by transcribe.py)
    <level>/<source>/titles.json             {"<name>": "Readable title"}   optional
    <level>/<source>/source.json             {"name": "Source name shown in the list", "section": "listening"|"speaking"}
    <level>/<source>/LAHDE.txt               where it came from

    _app/data/<level>/<source>/<name>.json       transcript with word timings (made by transcribe.py)
    _app/questions/<level>/<source>/<name>.json  questions for a recording
    _app/reading/<level>/<source>/<name>.json    reading task
    _app/writing/<level>/<source>/<name>.json    writing task
    _app/question_status.json                    what each source offers, per recording id

A recording's **id** is its path without `.mp3`, for example
`1-Perustaso/Linnasmaki-Askelia-2/3_Asuntonaytossa`. Use ASCII file names
without spaces (`Puhelu_Kelaan`, not `Puhelu Kelaan`), and put the real title
in `titles.json`.

`source.json` `section` puts the recording in the **Listening** or the
**Speaking** tab. Speaking = the learner answers out loud (YKI Puhuminen
tasks, dialogue prompts).

## Formats

Working examples of every format are in the `Esimerkit` and
`Esimerkit-Puhuminen` folders. Copy their structure.

### Questions: `_app/questions/<id>.json`

    {"title": "3. Asuntonäytössä",
     "intro": "Task instruction from the source",
     "questions": [
       {"type": "tf", "label": "M1", "text": "M1. Asunto on yksiö.",
        "options": ["Oikein", "Väärin"], "correct": ["B"]},
       {"type": "mc", "label": "M2", "text": "M2. Vuokra on",
        "options": ["505 euroa", "515 euroa", "550 euroa"], "correct": ["A"]},
       {"type": "open", "label": "A1", "text": "A1. Milloin asunto on vapaa?",
        "options": [], "correct": [], "model": "1.3. alkaen", "keywords": ["1.3."]}
     ]}

- `type`: `tf` (true/false: options are always `["Oikein","Väärin"]`, so A =
  Oikein, B = Väärin), `mc` (multiple choice), `open` (free answer).
- `options`: plain text, no "A)" prefixes. The player adds the letters.
- `correct`: letters, for example `["C"]`. Use `[]` when the source gives no
  answer.
- `model`, `keywords`: for open questions, only from the source.
- `label`: a short id. When a recording has two exercise sets, use
  `"Tehtävä 1.3"` style labels: the player then shows a "Tehtävä 1" heading.
- Also write `<id>.kysymykset.txt` next to the MP3, a plain-text copy, with
  the answers at the end under `Vastaukset` if the source has them.

### Status: `_app/question_status.json`

One entry per recording that has no questions or no answers. Recordings with
full questions and answers need no entry.

    {"<id>": {"questions": false, "answers": false, "kind": "listening",
              "note": "One plain-English sentence for the learner.",
              "source": "https://…"}}

### Reading: `_app/reading/<level>/<source>/<name>.json`

    {"title": "…", "source": "https://…", "sourceName": "Suomikoulut.fi",
     "intro": "Task instruction", "text": "Paragraphs separated by a blank line",
     "questions": [ …same question format as above… ]}

### Writing: `_app/writing/<level>/<source>/<name>.json`

    {"title": "Viesti naapurille", "kind": "epävirallinen viesti",
     "task": "Situation text\n- first thing to write\n- second thing",
     "length": "n. 50 sanaa", "minWords": 40, "maxWords": 60,
     "images": [],
     "models": [{"level": "", "text": "Example answer", "comment": ""}],
     "source": "https://…", "sourceName": "Ykitesti (official)"}

- `kind`: short Finnish label, for example `virallinen viesti`, `mielipide`.
- `minWords` / `maxWords`: numbers only if the source states them, else `null`.
- `images`: paths relative to the repo root, when the task needs a picture.
- `models`: example answers from the source only. `level` is the YKI grade
  (`taitotaso 3`) only if the source rates it.

## Pipeline for a new listening or speaking source

1. Find the source and check rule 3. Look at `docs/SOURCES.md` first.
2. Make `<level>/<Source-Name>/`, download the MP3s, write `LAHDE.txt`,
   `source.json` and `titles.json`.
3. Transcribe (Apple Silicon): `.venv/bin/python _app/transcribe.py <Source-Name>`.
   Long jobs: run in the background and log to a file. Tell the user
   roughly how long it takes: about 5–15 s per minute of audio.
4. Extract questions from the source into `_app/questions/…` and
   `.kysymykset.txt`. Interactive pages often keep the data in the HTML:
   H5P (`H5PIntegration` JSON), Hot Potatoes (`I[n]` arrays), Next.js
   (`self.__next_f.push` chunks). PDFs: extract text with `pypdf`.
5. Add status entries for recordings without questions or answers.
6. `python3 _app/prewarm.py` to translate the new words.
7. Run the checks below.

## Checks

    python3 - <<'PY'
    import json, pathlib
    root = pathlib.Path(".")
    ids = {str(p.with_suffix("")) for p in root.glob("[123]-*/**/*.mp3")}
    for p in pathlib.Path("_app/questions").rglob("*.json"):
        d = json.loads(p.read_text()); i = str(p.relative_to("_app/questions").with_suffix(""))
        assert i in ids, f"questions without mp3: {i}"
        assert pathlib.Path(i + ".kysymykset.txt").exists(), f"missing .kysymykset.txt: {i}"
        for q in d["questions"]:
            assert q["type"] in ("tf", "mc", "open"), p
            for c in q.get("correct", []): assert ord(c) - 65 < len(q["options"]), f"bad answer letter in {p}"
    st = json.loads(pathlib.Path("_app/question_status.json").read_text() or "{}") if pathlib.Path("_app/question_status.json").exists() else {}
    assert all(k in ids for k in st), "status id without mp3"
    print("ok:", len(ids), "recordings")
    PY

Then start the player (`python3 _app/server.py`), open the new lessons, play
a few seconds, and check the questions and the answer check.

## Code notes

- `_app/server.py`: Python standard library only. Serves the repo, builds the
  lists, translates words (curl to Google, cached), stores saved words in
  `_app/sanat.json`. Restart it after you change it.
- `_app/index.html`: the whole player, plain HTML/CSS/JS, no build step.
- `deploy/`: static build for hosting (`build.py`), the browser stand-in for
  the server API (`static.js`), and the Vercel password check
  (`middleware.js`). Anything the server API does must also work in
  `static.js`.
- Keep the design rules: short ease-out transitions, no hover-only features
  on touch screens, 16 px minimum for inputs on phones.
- `ROADMAP.md` lists planned work. Update it when you finish an item.
