# YKI wrapper

A study player for the Finnish YKI test (Yleiset kielitutkinnot). You bring the
practice materials. The app turns them into interactive lessons:

- **Listening and speaking:** the audio plays with a transcript as subtitles.
  Hover or tap a word to pause and see its English translation. Save words to
  study later.
- **Questions:** true/false and multiple choice with answer checking, and open
  questions with model answers when the source has them.
- **Reading:** texts with click-to-translate words and questions.
- **Writing:** task, a text box that keeps your draft, a word count, and example
  answers.
- Mark lessons as complete, practise saved words, and export them as CSV.
- Works on a phone. Optional hosting on Vercel behind one password.

**This repo has almost no content, on purpose.** Practice materials belong to
their publishers. The idea is that you clone the repo and ask your own coding
agent (Claude Code, Codex, Cursor…) to collect materials for your personal
study. The agent instructions are in [AGENTS.md](AGENTS.md).

The repo has a few example tasks for every tab, so the app works right after
cloning (see [Example content](#example-content)).

## Quick start

Needs Python 3.10+, `ffmpeg` and `curl`.

    python3 _app/server.py --open        # http://127.0.0.1:8765/

On a Mac you can also double-click `start.command`.

To add content, open the repo in your coding agent and say, for example:

> Read AGENTS.md. Collect YKI keskitaso listening tasks from the sources in
> docs/SOURCES.md, transcribe them and add their questions.

## Transcription

`_app/transcribe.py` uses Whisper through `mlx-whisper`, so it runs on Apple
Silicon Macs only for now (see [ROADMAP.md](ROADMAP.md)).

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/python _app/transcribe.py            # all new MP3 files
    .venv/bin/python _app/transcribe.py --force 3_Asunto   # redo one file

Whisper makes mistakes, and sometimes it skips a whole 30-second window. The
script fills such gaps in a second pass and removes typical hallucinations, but
check the transcript before you trust it.

## Translations

Word translations come from Google Translate's free web endpoint, one word at a
time, without context. They are cached in `_app/translations.json`. This
endpoint is unofficial and can block you. Wrong translations can be fixed by
hand in `_app/translations-fix.json`. Run `python3 _app/prewarm.py` to
translate all words at once.

## Hosting (optional)

`deploy/build.py` builds a static copy into `site/`: smaller audio (48 kbps
mono), all translations pre-built, and saved words and drafts kept in each
visitor's browser. `deploy/middleware.js` protects the whole site with one
password on Vercel.

    python3 deploy/build.py
    cd site && vercel link && vercel env add YKI_PASSWORD production && vercel deploy --prod

Host only content you are allowed to share. Keep the password.

## Example content

The repo has two kinds of example content.

**Original examples, written for this repo** (folders `Esimerkit` and
`Esimerkit-Puhuminen`, MIT like the code). They follow the YKI task formats:

- Reading: 2 perustaso tasks (a notice, a message from a colleague) and 1
  keskitaso text, with true/false, multiple choice and open questions.
- Writing: 2 perustaso and 2 keskitaso tasks (informal and formal messages,
  an opinion text, a complaint), each with an example answer. The example
  answers are not official YKI ratings.
- Speaking: a perustaso "Tilanteet" task and a keskitaso phone dialogue. The
  audio is macOS text-to-speech (`tools/make_speaking_example.py`), with a
  beep and silence for your answer, and example answers to compare with.

**Real recordings from an open source:**

`1-Perustaso/Linnasmaki-Askelia-2/` has 5 recordings from *Askelia
aktiivisuuteen 2* (Mari Ruohonen, Turun kristillinen opisto 2015, funded by the
Finnish National Agency for Education, published free at
https://linnas.fi/opiston-tuottamaa-oppimateriaalia/askelia-aktiivisuuteen-2/).
The book's preface says the project's audio files may be used freely
("Hankkeessa tuotettuja äänitiedostoja voi vapaasti käyttää"). The questions are
from the same book, with credit. The transcripts are machine-made with Whisper.
If you are the rights holder and want them removed, open an issue.

## License

The code is MIT licensed (see [LICENSE](LICENSE)). The example content keeps
its own terms, as above. Content that you collect is for your own study; follow
each site's terms.

Built with Claude (Anthropic) in Claude Code.
