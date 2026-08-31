# Getting Started with InsightWeaver

> **Superseded 2026-08-31 (backlog task 012).** The briefing product this
> document describes -- `brief`, beats, questions, predictions, frames,
> synthesis and rendering -- has been **deleted**. Roughly 8,900 lines of source
> and most of the test suite went with it, in a single commit, because the
> operator's call was that git history is the rollback path and dead code in the
> tree reads as current. `insightweaver` now exposes one command, `sources`.
>
> What survives is ingestion: `src/sources/`, `src/rss/`, `src/processors/`, the
> feed config, and five modules ported for tiers not yet built
> (`src/matching/entity_matcher.py`, `src/matching/coverage_probe.py`,
> `src/llm/claude_client.py`, `src/utils/cadence.py`,
> `src/processors/deduplicator.py`).
>
> **Everything below this banner describes the deleted product and has not been
> rewritten.** Rewriting it needs the new pipeline to exist first, which task 012
> explicitly puts out of scope. Read it as history until it is replaced.

---

This guide walks you through downloading, installing, and running InsightWeaver on your computer.

---

## What You Need

1. **A computer** (Windows, Mac, or Linux)
2. **Python 3.11 or newer** -- [Download Python](https://www.python.org/downloads/)
3. **An Anthropic API key** -- [Get one here](https://console.anthropic.com/) (requires account; ~$0.20-0.40 per brief)

---

## Step 1: Download InsightWeaver

**Option A: Download ZIP** (easiest)
1. Click the green "Code" button on this page
2. Click "Download ZIP"
3. Extract the ZIP file to a folder (e.g., your Documents folder)

**Option B: Using Git** (if you have it installed)
```
git clone https://github.com/YOUR_USERNAME/InsightWeaver.git
```

---

## Step 2: Open a Terminal

**Windows:**
1. Press `Windows + R`, type `cmd`, press Enter
2. `cd Documents\InsightWeaver`

**Mac:**
1. Open Spotlight (`Cmd + Space`), type `Terminal`, press Enter
2. `cd ~/Documents/InsightWeaver`

**Linux:**
1. Open your terminal application
2. `cd ~/Documents/InsightWeaver`

---

## Step 3: Install InsightWeaver

```
python -m venv venv
```

Activate the virtual environment:

- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

Install:

```
pip install -e .
```

---

## Step 4: Add Your API Key

```
cp .env.example .env       # Mac/Linux
copy .env.example .env     # Windows
```

Open `.env` in any text editor. Replace `your_key_here` with your actual API key. Save.

---

## Step 5: Set Up Your Profile

Copy the example profile to its expected location:

```
cp config/user_profile.example.json config/user_profile.json
```

Open `config/user_profile.json` and edit it for your situation -- location, profession, civic interests, etc. The profile is what makes the brief location-aware and personally relevant.

---

## Step 6: Generate Your First Briefing

```
insightweaver brief
```

This takes 2-5 minutes. The brief renders directly to your terminal. To archive a copy as markdown:

```
insightweaver brief --save brief.md
```

---

## Daily Use

The minimum rhythm is one command:

```
insightweaver brief
```

Each morning. That's it. The brief renders to your terminal with everything you need: situation analyses, narrative-layer mapping, branching paths, information gaps, returning question identity (`Q47 (run 4, asked 2026-03-12)`), and a transparency line reporting which of yesterday's flagged observables resolved.

You don't need to touch anything else.

---

## Optional: tracking threads across time

InsightWeaver maintains a persistent commitment graph behind the brief -- Questions, Predictions, Decisions, Frames. These accumulate automatically whether or not you ever query them, but the CLI exposes them when you want to look.

**See [docs/CONCEPTS.md](docs/CONCEPTS.md)** for a one-page reference on what each entity is and when it gets created.

Commands available when you want depth:

```
insightweaver questions list           # threads the coverage is still tracking
insightweaver questions show 47        # full history of question Q47
insightweaver predictions track-record # the tool's own calibration record
insightweaver decisions list           # standing decisions
insightweaver decisions show 1         # factors and routed evidence for D1
insightweaver diet feeds               # which frames each feed carries
insightweaver diet gaps                # frames consistently absent (curation signal)
insightweaver sources list             # per-source structural calibration
insightweaver frames list              # the narrative frame glossary
insightweaver forecast                 # open observables + resolved record
```

If you want to register decisions so they accumulate evidence over time:

```
insightweaver decisions add --name "housing market timing" --type housing
insightweaver decisions factor add 1 --name "interest rates" \
  --update-when "Fed signals a cut or hold at the next meeting"
```

Then each subsequent brief will route relevant situation evidence into that decision automatically.

Run `insightweaver --help` or type `help` in interactive mode for the full command list.

---

## Filtering the brief

The brief accepts topic and scope filters:

```
insightweaver brief --hours 48          # look back 48 hours
insightweaver brief -cs -n              # national cybersecurity only
insightweaver brief --hours 48 -l       # 48-hour local news
```

Topic flags: `--cybersecurity` (`-cs`), `--ai` (`-ai`). Scope flags: `--local` (`-l`), `--state` (`-s`), `--national` (`-n`), `--global` (`-g`). Combine with AND logic.

---

## Troubleshooting

**"command not found" or "not recognized"** -- the virtual environment isn't active. Run `source venv/bin/activate` (Mac/Linux) or `venv\Scripts\activate` (Windows). You should see `(venv)` at the start of your prompt.

**"No module named..."** -- reinstall: `pip install -e .`

**API key errors** -- check that `.env` exists and contains your key with no extra spaces around the `=`. Verify the key at [console.anthropic.com](https://console.anthropic.com/).

**Brief is empty or errors out** -- check internet connection and API credit balance. Add `--debug` for verbose logs: `insightweaver brief --debug`.

---

## Configuration

**Your profile** is `config/user_profile.json`. Edit directly to change your location, professional domain, or topic interests. Most users edit this once a year, when major life circumstances change.

**Your RSS feeds** are configured in `config/feeds/`. Each JSON file lists feed URLs by category. Add or remove sources to shape your information diet -- the `diet gaps` command will tell you what perspectives are missing.

---

## Privacy

- All data is stored locally in `data/insightweaver.db`
- News articles come from public RSS feeds you configure
- Synthesis runs through the Anthropic API (no third-party sharing)
- Delete `data/` to wipe all accumulated state

---

## Requirements

- **Python:** 3.11 or newer
- **Disk:** ~100MB for database
- **Internet:** for RSS fetch and API calls
- **API budget:** ~$0.20-0.40 per brief
