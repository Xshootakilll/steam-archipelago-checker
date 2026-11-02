# Archipelago Steam Checker

A tiny static web tool: **paste your Steam profile link and see which of your games have an [Archipelago](https://archipelago.gg) randomizer world.**

👉 **Live:** https://xshootakilll.github.io/steam-archipelago-checker/

- Matches your **public** Steam library against the community [Archipelago Games sheet](https://docs.google.com/spreadsheets/d/1iuzDTOAvdoNe8Ne8i461qGNucg5OuEoF-Ikqs8aUQZw/htmlview).
- **100% GitHub** — static GitHub Pages site + a weekly GitHub Action. No server, no API keys, nothing stored. Everything runs in your browser.
- Your Steam **Game details** must be set to **Public** (Profile → Edit → Privacy) for it to read your library.

## How it works

| File | Purpose |
|---|---|
| `index.html` | The page. Reads your public Steam games XML (via a public CORS proxy) and matches it against `ap_games.json` client-side. |
| `ap_games.json` | The AP games list + Steam AppIDs. **Auto-generated** — don't edit by hand. |
| `scripts/build_ap_list.py` | Fetches the AP sheet + Steam's app list and rebuilds `ap_games.json`. |
| `.github/workflows/update.yml` | Runs the script **weekly** (and on demand) and commits an updated list, so the tool stays current as new AP games are added. |
| `aliases.json` | Optional manual overrides for tricky name→AppID matches, e.g. `{ "Some Game": 123456 }`. |

Matching is primarily by normalized game name (works without AppIDs); AppIDs add exact matching + store links and are filled in by the Action (Steam's API isn't reachable from every network, but it is from GitHub's runners).

*Fan project — not affiliated with Steam, Valve, or Archipelago.*
