// The Siren follows the Hub: on the Ithaca site, copy the fan you're browsing as and the Hub's API into
// the extension, so relics collected on YouTube land on that fan, on the same backend the Hub reads.
function sync() {
  let fan = "";
  try { fan = localStorage.getItem("ithaca_fan") || ""; } catch {}
  const apiBase = document.querySelector('meta[name="ithaca-api"]')?.content || "";
  chrome.storage.local.get(["fan", "apiBase", "webBase"], (cur) => {
    const next = {};
    if (fan && fan !== cur.fan) next.fan = fan;
    if (apiBase && apiBase !== cur.apiBase) next.apiBase = apiBase;
    if (location.origin !== cur.webBase) next.webBase = location.origin;
    if (Object.keys(next).length) chrome.storage.local.set(next);
  });
}
sync();
const timer = setInterval(() => { try { sync(); } catch { clearInterval(timer); } }, 2000); // the Hub is a single-page app: the fan can change without a page load
