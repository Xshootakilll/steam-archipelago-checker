#!/usr/bin/env python3
"""
Build ap_games.json: the Archipelago games list enriched with Steam AppIDs.

- Fetches the AP "Games" tab (public Google Sheet) as CSV.
- Fetches Steam's keyless full app list.
- Matches each AP game name -> Steam AppID (exact normalized-name match,
  lowest appid wins on collisions = usually the base game).
- aliases.json ({ "Game Name": appid }) forces/corrects tricky matches.

No API keys. Runs locally and in the GitHub Action on a schedule.
"""
import csv, io, json, re, sys, os, urllib.request, datetime

SHEET_ID = "1iuzDTOAvdoNe8Ne8i461qGNucg5OuEoF-Ikqs8aUQZw"
GAMES_GID = "58422002"
APPLIST_URL = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root

def fetch(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "steam-archipelago-checker"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def norm(s):
    s = (s or "").lower().replace("&", " and ")
    s = re.sub(r"[™®©]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("the "):
        s = s[4:]
    return s

# ---- 1. AP games tab ----
csv_text = fetch(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GAMES_GID}").decode("utf-8", "replace")
rows = list(csv.reader(io.StringIO(csv_text)))
KNOWN_STABILITY = {"stable", "unstable", "beta", "wip", "broken", "unknown", "--", "", "n/a"}
ap, seen = [], set()
for row in rows[1:]:
    if not row or not row[0].strip():
        continue
    name = row[0].strip()
    n = norm(name)
    if not n or n in seen:
        continue
    stability = (row[1].strip() if len(row) > 1 else "")
    # skip note/section rows: a real game row has a recognizable stability value
    if stability.lower() not in KNOWN_STABILITY:
        continue
    support = (row[6].strip() if len(row) > 6 else "")
    seen.add(n)
    ap.append({"name": name, "norm": n, "stability": stability, "support": support})

# ---- 2. Steam app list -> normalized name -> lowest appid ----
# Best-effort: api.steampowered.com isn't reachable from every network (it is
# from GitHub's Action runners). If it fails, we ship name-only matching and
# the next Action run fills in the AppIDs.
smap = {}
try:
    apps = json.loads(fetch(APPLIST_URL))["applist"]["apps"]
    for a in apps:
        nm = norm(a.get("name", ""))
        if not nm:
            continue
        aid = a["appid"]
        if nm not in smap or aid < smap[nm]:
            smap[nm] = aid
    print(f"Steam app list: {len(smap)} unique names")
except Exception as e:
    print(f"warn: Steam app list unavailable ({e}); shipping name-only, Action will add AppIDs", file=sys.stderr)

# ---- 3. aliases overrides ----
alias_norm = {}
apath = os.path.join(HERE, "aliases.json")
if os.path.exists(apath):
    try:
        for k, v in json.load(open(apath)).items():
            alias_norm[norm(k)] = int(v)
    except Exception as e:
        print(f"warn: aliases.json ignored: {e}", file=sys.stderr)

# ---- 4. match ----
matched = 0
for g in ap:
    aid = alias_norm.get(g["norm"]) or smap.get(g["norm"])
    g["appid"] = aid
    if aid:
        matched += 1

out = {
    "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
    "source": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}",
    "count": len(ap),
    "matched_to_steam": matched,
    "games": ap,
}
with open(os.path.join(HERE, "ap_games.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

print(f"AP games parsed: {len(ap)}  |  matched to a Steam AppID: {matched} ({matched*100//max(len(ap),1)}%)")
