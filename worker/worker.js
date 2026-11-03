// Cloudflare Worker — read-only Steam library relay for the Archipelago checker.
//
// Why this exists: a static GitHub Pages page can't call api.steampowered.com
// directly (Steam sends no CORS headers), and the free public CORS proxies are
// unreliable. This tiny always-on relay fixes that AND holds the Steam Web API
// key as a secret (env.STEAM_KEY), so the key never reaches the public page.
//
// Deploy: Cloudflare dashboard → Workers & Pages → Create → Worker → paste this
// → Deploy. Then Settings → Variables and Secrets → add a *secret* named
// STEAM_KEY (your Steam Web API key). It exposes ONLY three read-only endpoints.
//
//   GET /owned?steamid=<17 digits>
//   GET /resolve?vanity=<name>
//   GET /summaries?steamids=<id64[,id64...] up to 8>

const ALLOW_ORIGIN = "https://xshootakilll.github.io";
const API = "https://api.steampowered.com";

export default {
  async fetch(req, env) {
    const cors = {
      "Access-Control-Allow-Origin": ALLOW_ORIGIN,
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Cache-Control": "no-store",
    };
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    if (req.method !== "GET") return json({ error: "GET only" }, 405, cors);

    const key = env.STEAM_KEY;
    if (!key) return json({ error: "relay misconfigured: STEAM_KEY secret not set" }, 500, cors);

    const url = new URL(req.url);
    const p = url.pathname.replace(/\/+$/, "");
    const q = url.searchParams;
    let target;

    if (p === "/owned") {
      const id = q.get("steamid") || "";
      if (!/^\d{17}$/.test(id)) return json({ error: "bad steamid" }, 400, cors);
      target = `${API}/IPlayerService/GetOwnedGames/v1/?key=${key}&steamid=${id}` +
               `&include_appinfo=1&include_played_free_games=1&format=json`;
    } else if (p === "/resolve") {
      const v = q.get("vanity") || "";
      if (!/^[A-Za-z0-9_.-]{1,64}$/.test(v)) return json({ error: "bad vanity" }, 400, cors);
      target = `${API}/ISteamUser/ResolveVanityURL/v1/?key=${key}&vanityurl=${encodeURIComponent(v)}`;
    } else if (p === "/summaries") {
      const ids = q.get("steamids") || "";
      if (!/^\d{17}(,\d{17}){0,7}$/.test(ids)) return json({ error: "bad steamids" }, 400, cors);
      target = `${API}/ISteamUser/GetPlayerSummaries/v2/?key=${key}&steamids=${ids}`;
    } else {
      return json({ error: "not found" }, 404, cors);
    }

    try {
      const r = await fetch(target, { cf: { cacheTtl: 0 } });
      const body = await r.text();
      return new Response(body, {
        status: r.status,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    } catch (e) {
      return json({ error: "upstream fetch failed", detail: String(e) }, 502, cors);
    }
  },
};

function json(obj, status, cors) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}
