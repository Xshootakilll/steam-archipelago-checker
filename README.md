# Archipelago Steam Checker

A tiny static web tool: **see which of your games have an [Archipelago](https://archipelago.gg) randomizer world** — your **Steam** library is auto-detected, and **emulated/console** games (Pokémon, Zelda, SMW…) you tick yourself.

👉 **Live:** https://xshootakilll.github.io/steam-archipelago-checker/

- Checks your **public** Steam library against the community [Archipelago Games sheet](https://docs.google.com/spreadsheets/d/1iuzDTOAvdoNe8Ne8i461qGNucg5OuEoF-Ikqs8aUQZw/htmlview) (all ~870 games, stable/unstable/broken included).
- **Solo** (one profile) or **Group** (compare 2–8 Steam libraries — who-has-what grid).
- **Emulated/console AP games aren't on Steam**, so they can't be auto-detected — you tick the ones you have, saved in your browser.
- **100% GitHub** — static Pages site + a weekly Action. Steam reads go through a tiny Cloudflare Worker relay; nothing else is stored server-side.
- Your Steam **Game details** must be **Public** (Profile → Edit Profile → Privacy → *Game details*).

## How it works

| File | Purpose |
|---|---|
| `index.html` | The page. Auto-matches your Steam library (AppID + edition/remake-tolerant name match) and lets you tick emulated games (localStorage). |
| `worker/worker.js` | Cloudflare Worker relaying read-only Steam Web API calls; holds the API key as a secret (never in the page). |
| `ap_games.json` | The live list the page loads: every AP game with `{norms, stability, appid, steam}`. **Auto-generated** — don't edit by hand. |
| `curated_db.json` | The **verified truth DB** — each game's correct AppID and Steam/emulated flag. Refreshed by `curate_db.py`. |
| `aliases.json` | Hand overrides `{ "AP Game Name": appid | null }` (null forces non-Steam). Highest precedence. |
| `scripts/curate_db.py` | Heavy, occasional pass: resolves each game's AppID via jsnli + **validated Steam storesearch**, classifies Steam vs emulated → writes `curated_db.json`. Run locally. |
| `scripts/build_ap_list.py` | Light weekly build: merges `curated_db.json` + `aliases.json` + the live sheet → `ap_games.json`. New games get a best-guess, flagged for the next curation. |
| `.github/workflows/update.yml` | Runs `build_ap_list.py` **weekly** and commits `ap_games.json`. |

**The data model** (curate-once, guess-new, re-curate later): `curate_db.py` builds a human-verifiable accurate base; the weekly Action trusts it and only best-guesses games newly added to the sheet. Re-run `curate_db.py` periodically to re-verify and fold in the guesses. Name matching strips editions/remakes/publisher prefixes and apostrophes (so *Resident Evil 2 Remake* == *Resident Evil 2*, *Sid Meier's Civilization V* == *Civilization V*).

*Fan project — not affiliated with Steam, Valve, or Archipelago.*
