# Roadmap

Where this project is going, in order. Each step should keep the app working
for a person who only runs `python3 _app/server.py`.

## Now (v0)

- Player for listening, speaking, reading and writing, with word translation,
  saved words, questions with answer check, drafts, and "mark as complete".
- Transcription with Whisper (Apple Silicon only).
- Static build and password-protected hosting on Vercel.
- `AGENTS.md` so that a coding agent can collect content.
- Examples: 5 real recordings (Linnasmäki) and original reading, writing and
  speaking tasks.

## 1. Works on every computer

- Add `faster-whisper` as a second transcription engine for Windows and
  Linux. Pick the engine by platform, with a `--engine` option.
- Translation provider setting: Google free endpoint (default, can block),
  DeepL or Google Cloud with the user's own API key, or none.
- One setup script (`setup.sh` / `setup.ps1`) that checks Python, ffmpeg and
  curl and creates the venv.
- Windows start script.

## 2. Data on the server, not only in the browser

- Drafts, completed lessons and saved words are in the browser's
  localStorage now. Move them to files next to `sanat.json` when the local
  server runs, and keep localStorage for the hosted static site.
- Needed for the MCP server (step 4) and for sync between devices.
- Import and export of all personal data as one JSON file.

## 3. Skills for agents

Package the work in `AGENTS.md` as skills (`SKILL.md` folders) that Claude
Code, the Claude apps and Codex can load:

- `collect-content`: find sources, download, transcribe, make questions and
  status files, run the checks.
- `add-source`: add one site or PDF.
- `writing-feedback`: check a draft against the YKI level descriptions, list
  errors, and suggest a corrected version.
- `speaking-feedback`: record or take a recording of the learner, transcribe
  it, and give feedback on grammar, vocabulary and fluency.

## 4. MCP server: a tutor next to the app

A small MCP server over the local data, so that a chat assistant (Claude
Desktop, Claude Code, Codex, ChatGPT) sees what the learner sees:

- `current_lesson`: the open lesson, with transcript and questions.
- `get_draft`, `save_feedback`: read a writing draft, store feedback.
- `saved_words`, `add_word`: quiz the learner, add words from the chat.
- `progress`, `mark_complete`: what is done and what comes next.
- `add_lesson`: import content the assistant found.

Local clients run it directly. The ChatGPT app needs a remote HTTPS MCP
server (a tunnel such as Cloudflare Tunnel): check OpenAI's current docs.

## 5. More than one language

- Move Finnish-specific things into a config: level names, UI hints,
  translation direction, Whisper language, source list.
- The same app then works for Swedish (Språktest), German (telc), and others.

## 6. Better content and quality

- Word translation with context (whole sentence), and base forms of words
  (Finnish has many word forms), for example with a morphology library such as
  Voikko.
- More open-licensed or self-made example content, and real human voices for
  the speaking examples (now text-to-speech).
- A "check the transcript" mode: listen and fix Whisper errors in the
  browser.
- Timed practice test mode that follows the real YKI timing.
- Spaced repetition for saved words.

## 7. Project health

- Small test suite: index building, the format checks from `AGENTS.md`, and
  a browser smoke test.
- CI that runs the checks on pull requests.
- Contribution guide: code changes are welcome, content is not (see README).
