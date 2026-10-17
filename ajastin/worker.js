// Cloudflare-ajastin: käynnistää GitHubin "Kerää ja julkaise" -ajon 10 minuutin välein.
// GITHUB_TOKEN on tallennettu Cloudflaren salaisuudeksi (ei koskaan tähän tiedostoon).
export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(fetch("https://api.github.com/repos/Miksu900/uutisvahti/actions/workflows/julkaise.yml/dispatches", {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + env.GITHUB_TOKEN,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nytpuhutaan-ajastin"
      },
      body: JSON.stringify({ ref: "main" })
    }));
  },
  async fetch() {
    return new Response("Nytpuhutaan.fi ajastin toimii");
  }
};

// Julkaistaan Cloudflareen automaattisesti, kun tämä kansio muuttuu (Workers Builds).
