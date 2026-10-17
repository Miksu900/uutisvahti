// Cloudflare-ajastin: käynnistää GitHubin "Kerää ja julkaise" -ajon 10 minuutin välein.
// GITHUB_TOKEN on tallennettu Cloudflaren salaisuudeksi (ei koskaan tähän tiedostoon).
// Julkaistaan Cloudflareen automaattisesti, kun tämä kansio muuttuu (Workers Builds).
async function kaynnista(env) {
  const r = await fetch("https://api.github.com/repos/Miksu900/uutisvahti/actions/workflows/julkaise.yml/dispatches", {
    method: "POST",
    headers: {
      "Authorization": "Bearer " + (env.GITHUB_TOKEN || "").trim(),
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "nytpuhutaan-ajastin"
    },
    body: JSON.stringify({ ref: "main" })
  });
  const teksti = r.status === 204 ? "" : (await r.text()).slice(0, 300);
  console.log("GitHub vastasi", r.status, teksti);
  return { status: r.status, teksti, avain: env.GITHUB_TOKEN ? "on (" + String(env.GITHUB_TOKEN).trim().slice(0, 11) + "…)" : "PUUTTUU" };
}
export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(kaynnista(env));
  },
  async fetch(request, env) {
    if (new URL(request.url).pathname === "/kokeile") {
      const t = await kaynnista(env);
      return new Response(JSON.stringify(t), { headers: { "content-type": "application/json; charset=utf-8" } });
    }
    return new Response("Nytpuhutaan.fi ajastin toimii");
  }
};
