#!/usr/bin/env python3
"""
One-time / periodic CURATION pass — builds the accurate base DB.
For every AP game: find a verified Steam AppID (jsnli exact-name, then Steam
storesearch validated by normalized-name match), else mark it non-Steam
(console/emulated/browser). Applies aliases.json overrides (human truth).
Heavier than build_ap_list.py (does ~hundreds of storesearch calls) — run it
locally to refresh curated_db.json, which the weekly build then trusts.
"""
import urllib.request, urllib.parse, csv, io, re, json, time, os, sys

SHEET = "1iuzDTOAvdoNe8Ne8i461qGNucg5OuEoF-Ikqs8aUQZw"
GID = "58422002"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSNLI = "https://raw.githubusercontent.com/jsnli/steamappidlist/master/data/games_appid.json"

def fetch(u, t=120):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t).read()

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
    """normalized-name variants for matching: trailing (…)/[…] stripped, plus
    edition/remake/publisher-stripped forms (so 'Resident Evil 2 Remake' == 'Resident Evil 2',
    'Sid Meier's Civilization V' == 'Civilization V')."""
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
    return {v for v in out if v}

# ---- aliases.json: human truth {"AP Game Name": appid|null}  (null = force non-Steam) ----
alias = {}
ap = os.path.join(HERE, "aliases.json")
if os.path.exists(ap):
    try: alias = {k: v for k, v in json.load(open(ap)).items() if not k.startswith("_")}
    except Exception as e: print("warn: aliases.json:", e, file=sys.stderr)
alias_norm = {norm1(k): v for k, v in alias.items()}

# ---- sheet: all games ----
rows = list(csv.reader(io.StringIO(fetch(f"https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:csv&gid={GID}").decode("utf-8", "replace"))))
games, seen = [], set()
for r in rows[1:]:
    if not r or not r[0].strip(): continue
    name = r[0].strip()
    vs = variants(name)
    key = min(vs, key=len) if vs else ""
    if not key or key in seen: continue
    seen.add(key)
    games.append({"name": name, "norms": sorted(vs),
                  "stability": (r[1].strip() if len(r) > 1 else "")})
print(f"games: {len(games)}")

# ---- jsnli name -> appid ----
smap = {}
for a in json.loads(fetch(JSNLI)):
    k = norm1(a.get("name", "")); aid = a.get("appid")
    if k and aid and (k not in smap or aid < smap[k]): smap[k] = aid
print(f"jsnli names: {len(smap)}")

def storesearch(term):
    u = "https://store.steampowered.com/api/storesearch/?" + urllib.parse.urlencode({"term": term, "l": "english", "cc": "US"})
    try:
        d = json.loads(fetch(u, 15))
        return [(i.get("id"), i.get("name")) for i in d.get("items", []) if i.get("id")]
    except Exception:
        return []

n_alias = n_jsnli = n_store = n_none = 0
review = []
for g in games:
    vs = set(g["norms"])
    # 1) alias override (truth)
    hit = next((alias_norm[v] for v in vs if v in alias_norm), "MISS")
    if hit != "MISS":
        g["appid"] = hit if hit else None
        g["steam"] = bool(hit); g["src"] = "alias"; n_alias += 1; continue
    # 2) jsnli exact-name
    aid = next((smap[v] for v in vs if v in smap), None)
    if aid:
        g["appid"] = aid; g["steam"] = True; g["src"] = "jsnli"; n_jsnli += 1; continue
    # 3) storesearch, validated by variant overlap (query variants ∩ result variants)
    cands = storesearch(g["name"])
    time.sleep(0.35)
    good = next((i for i, nm in cands if vs & variants(nm)), None)
    if good:
        g["appid"] = good; g["steam"] = True; g["src"] = "storesearch"; n_store += 1; continue
    g["appid"] = None; g["steam"] = False; g["src"] = "none"; n_none += 1
    if cands:  # storesearch found something but name didn't match -> maybe a mismatch to alias
        review.append((g["name"], cands[:2]))

out = {"generated": time.strftime("%Y-%m-%d"), "count": len(games),
       "steam": sum(1 for g in games if g["steam"]),
       "nonsteam": sum(1 for g in games if not g["steam"]), "games": games}
json.dump(out, open(os.path.join(HERE, "curated_db.json"), "w"), ensure_ascii=False, separators=(",", ":"))
print(f"\nSTEAM: {out['steam']}  (alias {n_alias}, jsnli {n_jsnli}, storesearch {n_store})")
print(f"NON-STEAM (console/emulated/other): {out['nonsteam']}")
print(f"\n== REVIEW: storesearch found a possible match but name differed ({len(review)}) ==")
for nm, c in review[:40]:
    print(f"   {nm!r:44} -> {c}")
