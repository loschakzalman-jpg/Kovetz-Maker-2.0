# קובץ לימוד ערב שבת: website

A small local website. You enter a date, it fetches everything, you check the Dvar Torah, and it gives you two PDFs:

- **Reading PDF**: half-letter pages (5.5 x 8.5 in), in reading order.
- **Booklet PDF**: the same pages arranged on US Letter sheets for printing. Print double-sided, **flip on the short edge**, fold the stack in half.

## Run it

You need Python 3.10 or newer.

    ./run.sh          (Mac / Linux)
    run.bat           (Windows)

The first run installs the packages and a copy of Chromium (a few minutes). Then open http://127.0.0.1:5000.

For the AI-written Dvar Torah, set your key before starting:

    export ANTHROPIC_API_KEY=sk-ant-...        (Windows: set ANTHROPIC_API_KEY=...)

Without a key the Dvar Torah boxes get a placeholder that you can paste over. `KOVETZ_MODEL` changes the model (default `claude-sonnet-5-5`).

## Where each part comes from

| Part | Source |
|---|---|
| Chumash with Rashi, Tanya, Hayom Yom, Rambam (1 perek) | chayenu.org, the page for that date. The page title is checked against the date you chose. |
| Candle-lighting time | chabad.org candle-lighting page for the location in Settings, for the Friday of that week. |
| Parsha name, aliyot, Shnayim Mikra and Onkelos | Sefaria (Miqra according to the Masorah, Onkelos / Torat Emet). |
| Hebrew date | Calculated on your computer (pyluach). |
| Dvar Torah | Written by the Anthropic API for that parsha. Read it before printing. |

If chabad.org can't be read, the back page falls back to a sunset calculation and the site tells you to check it.

## If a section fails

Every page it downloads is saved in `cache/<date>/`. If Chayenu or Chabad.org changes its layout, the error names the section, and the saved HTML is what you send for the parser to be fixed (`kovetz/sources.py`).

## Layout

Fonts, spacing and page layout live in `static/print.css` and `kovetz/render.py`. Replace `static/logo.png` to change the back-page logo.

## Tests

    python -m tests.test_parsers      # parsers against mock pages
    python -m tests.test_app          # full flow with saved data (uses tests/data/sample_issue.json)

## Put it online

The folder is ready to deploy as a container (`Dockerfile`, `render.yaml`).

1. Put the folder in a GitHub repository (private is fine).
2. On render.com, choose New > Blueprint, pick the repository. It reads `render.yaml`.
3. When asked, enter `SITE_PASSWORD` (anyone opening the site must type it; any username works) and your `ANTHROPIC_API_KEY`.
4. Render builds it and gives you an https address.

Without `SITE_PASSWORD`, anyone with the link can use your API key, so keep it set. The Starter plan is about $7 a month. Any host that runs a Dockerfile works the same way (Fly.io, a small VPS).
