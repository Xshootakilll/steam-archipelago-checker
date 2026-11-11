#!/usr/bin/env python3
"""
Weekly build (the GitHub Action runs this): merge the curated truth DB
(curated_db.json, refreshed by curate_db.py) with the live AP sheet -> ap_games.json,
which the browser loads. Curated games are trusted as-is; games NEW to the sheet get
a light jsnli best-guess and are flagged "guessed" for the next curation pass.
Kept light (no storesearch) so it runs fast on the Action. All games included,
unstable/broken or not.
"""
import csv, io, json, re, os, sys, urllib.request, datetime

SHEET = "1iuzDTOAvdoNe8Ne8i461qGNucg5OuEoF-Ikqs8aUQZw"
GID = "58422002"
JSNLI = "https://raw.githubusercontent.com/jsnli/steamappidlist/master/data/games_appid.json"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def fetch(u, t=120):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "steam-archipelago-checker"}), timeout=t).read()

def norm1(s):
    s = (s or "").lower().replace("&", " and ")
    s = s.replace("'", "").replace("’", "")   # drop apostrophes: meier's -> meiers
    s = re.sub(r"[™®©]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[4:] if s.startswith("the ") else s

_PREFIX = ["sid meiers", "tom clancys", "disneys", "disney", "warner bros"]
_STRIP = ["definitive edition", "definite edition", "game of the year edition", "goty edition", "goty",
          "complete edition", "enhanced edition", "deluxe edition", "ultimate edition",
          "gold edition", "special edition", "anniversary edition",
          "20th anniversary world tour", "anniversary world tour",
          "hd remaster", "remastered", "remaster", "remake", "redux"]
def variants(name):
    forms, s = {name or ""}, (name or "")
    while re.search(r"[\(\[][^\)\]]*[\)\]]\s*$", s):
        s = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]\s*$", "", s); forms.add(s)
    out = set()
    for f in forms:
        n = norm1(f); out.add(n)
        n2 = n
        for p in _PREFIX: n2 = re.sub(r"^" + re.escape(p) + r" ", "", n2)
        for w in _STRIP:  n2 = re.sub(r"\b" + re.escape(w) + r"\b", " ", n2)
        n2 = re.sub(r"\s+", " ", n2).strip()
        if n2: out.add(n2)
    return sorted(v for v in out if v)

# ---- curated truth DB, keyed by every norm-variant ----
curated = {}
cp = os.path.join(HERE, "curated_db.json")
if os.path.exists(cp):
    for g in json.load(open(cp)).get("games", []):
        for v in g.get("norms", []):
            curated.setdefault(v, g)

# ---- aliases.json: hand overrides {"Name": appid|null}  (null = force non-Steam) ----
alias_norm = {}
apath = os.path.join(HERE, "aliases.json")
if os.path.exists(apath):
    try:
        for k, v in json.load(open(apath)).items():
            if not k.startswith("_"):
                alias_norm[norm1(k)] = v
    except Exception as e:
        print("warn: aliases.json ignored:", e, file=sys.stderr)

# ---- jsnli name->appid (for best-guessing NEW games only) ----
smap = {}
try:
    for a in json.loads(fetch(JSNLI)):
        k = norm1(a.get("name", "")); aid = a.get("appid")
        if k and aid and (k not in smap or aid < smap[k]):
            smap[k] = aid
except Exception as e:
    print("warn: jsnli unavailable:", e, file=sys.stderr)

rows = list(csv.reader(io.StringIO(fetch(f"https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:csv&gid={GID}").decode("utf-8", "replace"))))
games, seen, new = [], set(), 0
for r in rows[1:]:
    if not r or not r[0].strip():
        continue
    name = r[0].strip()
    vs = variants(name)
    key = min(vs, key=len) if vs else ""
    if not key or key in seen:
        continue
    seen.add(key)
    stability = (r[1].strip() if len(r) > 1 else "")
    g = {"name": name, "norms": vs, "stability": stability}
    av = next((alias_norm[v] for v in vs if v in alias_norm), "MISS")
    if av != "MISS":                                   # hand-curated override
        g.update(appid=(av or None), steam=bool(av), src="alias")
    elif (c := next((curated[v] for v in vs if v in curated), None)):  # curated truth
        g.update(appid=c.get("appid"), steam=c.get("steam", bool(c.get("appid"))), src=c.get("src", "curated"))
    else:                                              # new game -> best guess
        aid = next((smap[v] for v in vs if v in smap), None)
        g.update(appid=aid, steam=bool(aid), src="guess", guessed=True)
        new += 1
    games.append(g)

out = {
    "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
    "source": f"https://docs.google.com/spreadsheets/d/{SHEET}",
    "count": len(games),
    "steam": sum(1 for g in games if g["steam"]),
    "nonsteam": sum(1 for g in games if not g["steam"]),
    "games": games,
}
with open(os.path.join(HERE, "ap_games.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"games {len(games)} | steam {out['steam']} | non-steam {out['nonsteam']} | NEW guessed {new}")
