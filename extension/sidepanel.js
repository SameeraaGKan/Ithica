// The Siren — side panel. Shows lore for what's playing, lets the fan collect relics.
// Talks to the Ithaca API (backend/app/routes.py: /siren/context, /siren/collect);
// falls back to bundled lore (lore_seed.json, a copy of backend/data/lore_seed.json) if the API is slow or down.
import { DEFAULTS, getSettings } from "./config.js";

const $ = (id) => document.getElementById(id);

const COLLECT_REWARD = 26;  // offline estimate; matches the backend (25 for a new relic + 1 for the watch)

let settings = { ...DEFAULTS };
let lore = { eras: [], entries: [] };   // { eras, entries } from lore_seed.json
let state = null;         // latest player state from background
let current = null;       // { entry, era, relic, collected }
let fetchSeq = 0;
let lastKey = "";

// ---------------------------------------------------------------- boot
init();

async function init() {
  settings = await getSettings();
  const seed = await fetch(chrome.runtime.getURL("lore_seed.json")).then((r) => r.json()).catch(() => null);
  if (seed) lore = { eras: seed.eras || [], entries: (seed.lore_entries || []).filter((e) => !e._product) };
  const { drachmae = 0 } = await chrome.storage.local.get("drachmae");
  setDrachmae(drachmae, false);

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.kind === "siren:update") onState(msg.state);
  });
  onState(await chrome.runtime.sendMessage({ kind: "siren:get-active" }));
  wireUi();
  checkApi();
}

// ---------------------------------------------------------------- state → view
function onState(s) {
  state = s;
  if (!s) return show("idle");
  if (!s.isFaze) {
    $("notfazeChannel").textContent = s.channelName ? `(Channel: ${s.channelName})` : "";
    return show("notfaze");
  }
  // Only refetch when the lore could change: new video, or a new 30s window.
  const key = `${s.videoId}|${Math.floor(s.t / 30)}`;
  if (key === lastKey) return;
  lastKey = key;
  loadContext(s);
}

async function loadContext(s) {
  const seq = ++fetchSeq;
  let ctx = null;
  try {
    const q = new URLSearchParams({ videoId: s.videoId, t: String(s.t), channel: s.channelName || s.channelHandle });
    const res = await api(`/siren/context?${q}`);
    // Backend shape: { video_id, t, is_faze, lore: {..., era_label}, relic_available: {id, era, name, rarity} }
    if (!res.lore) throw new Error("no lore from API");
    const era = eraOf(res.lore.era);
    // The API omits video_id/relic on lore; merge the bundled copy so "Jump to moment" and relic names still work.
    const entry = { ...(lore.entries.find((e) => e.id === res.lore.id) || {}), ...res.lore };
    ctx = { entry, era: { ...era, label: era?.label || res.lore.era_label }, relic: res.relic_available || entry.relic,
            kind: entry.video_id === s.videoId ? "Lore at this moment" : "While you watch: a story from the archive" };
    setStatus("live", "Live · Ithaca API");
  } catch {
    ctx = localContext(s);
    setStatus("offline", "Offline lore · will sync later");
  }
  const { owned = [] } = await chrome.storage.local.get("owned");
  ctx.collected = owned.includes(ctx.relic?.id);
  if (seq !== fetchSeq || !ctx?.entry) return; // a newer request won
  current = ctx;
  render(ctx);
}

function render({ entry, era, relic, collected, kind }) {
  show("lore");
  $("eraLabel").textContent = era?.label || entry.era;
  $("eraOdyssey").textContent = era?.odyssey || "";
  $("loreKind").textContent = kind || "Lore at this moment";
  $("loreTitle").textContent = entry.title;
  $("lorePeople").replaceChildren(...(entry.people || []).map((p) => Object.assign(document.createElement("span"), { textContent: p })));
  $("loreSummary").textContent = entry.summary;
  $("loreWhy").textContent = entry.why_it_matters;

  const canJump = entry.video_id && entry.video_id === state?.videoId && Number.isFinite(entry.start_s);
  $("jumpBtn").classList.toggle("hidden", !canJump);

  const r = relic || entry.relic;
  $("relic").classList.toggle("hidden", !r);
  if (r) {
    $("relicName").textContent = r.name;
    $("relicRarity").textContent = r.rarity;
    $("relicRarity").className = `rarity ${r.rarity}`;
    setCollected(collected ?? false);
  }

  const others = lore.entries.filter((e) => e.era === entry.era && e.id !== entry.id).slice(0, 4);
  $("more").classList.toggle("hidden", others.length === 0);
  $("moreList").replaceChildren(...others.map((e) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="y"></span><span class="t"></span>`;
    li.querySelector(".y").textContent = e.year;
    li.querySelector(".t").textContent = e.title;
    li.onclick = async () => {
      const { owned = [] } = await chrome.storage.local.get("owned");
      current = { entry: e, era: eraOf(e.era), relic: e.relic, collected: owned.includes(e.relic?.id), kind: "From the archive" };
      render(current);
    };
    return li;
  }));
}

function show(id) {
  for (const s of ["idle", "notfaze", "lore"]) $(s).classList.toggle("hidden", s !== id);
  if (id !== "lore") $("more").classList.add("hidden");
}

// ---------------------------------------------------------------- offline lore
function eraOf(id) { return lore.eras.find((e) => e.id === id); }

function localContext(s) {
  const forVideo = lore.entries.filter((e) => e.video_id && e.video_id === s.videoId);
  let entry = forVideo.find((e) => s.t >= (e.start_s ?? 0) && s.t <= (e.end_s ?? Infinity)) || forVideo[0];
  let kind = "Lore at this moment";
  if (!entry) {
    // Not mapped yet: rotate through lore every 30s, stable per video.
    const pool = lore.entries.filter((e) => !e.sensitive);
    entry = pool[(hash(s.videoId) + Math.floor(s.t / 30)) % pool.length];
    kind = "While you watch: a story from the archive";
  }
  return { entry, era: eraOf(entry.era), relic: entry.relic, collected: false, kind };
}

function hash(str) { let h = 0; for (const c of str) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h; }

// ---------------------------------------------------------------- actions
function wireUi() {
  $("collectBtn").onclick = collect;
  $("jumpBtn").onclick = () => chrome.runtime.sendMessage({ kind: "siren:seek", tabId: state?.tabId, t: current?.entry?.start_s });
  $("askBtn").onclick = () => {
    const u = new URL("/bard", settings.webBase);
    u.searchParams.set("fan_id", settings.fan);
    if (current?.entry) u.searchParams.set("lore", current.entry.id);
    if (state?.videoId) { u.searchParams.set("videoId", state.videoId); u.searchParams.set("t", state.t); }
    chrome.tabs.create({ url: u.toString() });
  };
  $("settingsBtn").onclick = () => {
    $("apiBase").value = settings.apiBase; $("webBase").value = settings.webBase; $("fan").value = settings.fan;
    $("settings").showModal();
  };
  $("settings").addEventListener("close", async () => {
    if ($("settings").returnValue !== "save") return;
    settings = { ...settings, apiBase: $("apiBase").value.replace(/\/$/, ""), webBase: $("webBase").value.replace(/\/$/, ""), fan: $("fan").value.trim() };
    await chrome.storage.local.set({ apiBase: settings.apiBase, webBase: settings.webBase, fan: settings.fan });
    lastKey = ""; checkApi(); if (state) onState(state);
  });
}

async function collect() {
  if (!current?.entry) return;
  const relic = current.relic || current.entry.relic;
  $("collectBtn").disabled = true;
  const body = { fan_id: settings.fan, video_id: state?.videoId || "unknown", t: state?.t ?? 0, lore_id: current.entry.id };
  try {
    // Backend shape: { relic, drachmae_awarded, drachmae_total, already_had }
    const res = await api("/siren/collect", { method: "POST", body: JSON.stringify(body) });
    setDrachmae(res.drachmae_total, !res.already_had);
    const { owned = [] } = await chrome.storage.local.get("owned");
    if (relic && !owned.includes(relic.id)) await chrome.storage.local.set({ owned: [...owned, relic.id] });
    toast(res.already_had ? `You already hold the ${relic.name}.` : `Relic collected: ${relic.name}  +${res.drachmae_awarded} Drachmae`);
  } catch {
    // Offline: remember it locally and sync when the API is back.
    const { pending = [], drachmae = 0, owned = [] } = await chrome.storage.local.get(["pending", "drachmae", "owned"]);
    const already = owned.includes(relic.id);
    if (!already) {
      await chrome.storage.local.set({ pending: [...pending, body], owned: [...owned, relic.id], drachmae: drachmae + COLLECT_REWARD });
      setDrachmae(drachmae + COLLECT_REWARD, true);
    }
    toast(already ? `You already hold the ${relic.name}.` : `Relic collected: ${relic.name}  +${COLLECT_REWARD} Drachmae`);
  }
  setCollected(true);
}

// Push offline collects once the API answers again.
async function flushPending() {
  const { pending = [] } = await chrome.storage.local.get("pending");
  if (!pending.length) return;
  const left = [];
  for (const p of pending) { try { await api("/siren/collect", { method: "POST", body: JSON.stringify(p) }); } catch { left.push(p); } }
  await chrome.storage.local.set({ pending: left });
}

async function checkApi() {
  try { await api("/health"); setStatus("live", "Live · Ithaca API"); flushPending(); }
  catch { setStatus("offline", "Offline lore · will sync later"); }
}

// ---------------------------------------------------------------- helpers
async function api(path, opts = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), settings.apiTimeoutMs ?? DEFAULTS.apiTimeoutMs);
  try {
    const r = await fetch(settings.apiBase + path, { ...opts, signal: ctrl.signal, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } finally { clearTimeout(timer); }
}

function setCollected(done) {
  $("relic").classList.toggle("collected", done);
  $("collectBtn").textContent = done ? "Collected ✓" : "Collect Relic";
  $("collectBtn").disabled = done;
}

function setDrachmae(n, bump) {
  if (!Number.isFinite(n)) return;
  $("drachmae").textContent = n.toLocaleString();
  chrome.storage.local.set({ drachmae: n });
  if (bump) { const el = $("drachmae").parentElement; el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump"); }
}

function setStatus(kind, text) { $("status").className = `status ${kind}`; $("statusText").textContent = text; }

let toastTimer;
function toast(text) {
  const t = $("toast"); t.textContent = text; t.classList.remove("hidden");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.add("hidden"), 2600);
}
