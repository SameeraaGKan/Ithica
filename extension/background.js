// The Siren — service worker. Keeps the latest player state per tab and relays it to the side panel.
import { FAZE_CHANNELS, FAZE_MEMBER_NAMES } from "./config.js";

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(console.error);
});

function isFaze(s) {
  if (!s) return false;
  const name = (s.channelName || "").toLowerCase();
  const handle = (s.channelHandle || "").toLowerCase();
  const bare = name.replace(/^faze\s*/, "").replace(/[^a-z0-9 ]/g, "").trim();
  return name.includes("faze") || handle.includes("faze") ||
    FAZE_CHANNELS.includes(handle) || FAZE_CHANNELS.includes(name) ||
    FAZE_MEMBER_NAMES.includes(bare) || FAZE_MEMBER_NAMES.includes(handle.replace(/^@/, ""));
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.kind === "siren:state" && sender.tab) {
    const state = msg.state ? { ...msg.state, isFaze: isFaze(msg.state), tabId: sender.tab.id } : null;
    chrome.storage.session.set({ [`tab:${sender.tab.id}`]: state });
    // Badge: a gold dot when the Siren has something to sing on this tab.
    chrome.action.setBadgeText({ tabId: sender.tab.id, text: state?.isFaze ? "♪" : "" });
    chrome.action.setBadgeBackgroundColor({ tabId: sender.tab.id, color: "#C9A227" });
    chrome.runtime.sendMessage({ kind: "siren:update", state }).catch(() => {}); // panel may be closed
    return;
  }
  if (msg?.kind === "siren:get-active") {
    chrome.tabs.query({ active: true, currentWindow: true }).then(async ([tab]) => {
      if (!tab) return sendResponse(null);
      const key = `tab:${tab.id}`;
      const got = await chrome.storage.session.get(key);
      // Ask the page to re-report in case the worker restarted and lost state.
      chrome.tabs.sendMessage(tab.id, { kind: "siren:ping" }).catch(() => {});
      sendResponse(got[key] || null);
    });
    return true; // async sendResponse
  }
  if (msg?.kind === "siren:seek") {
    chrome.tabs.sendMessage(msg.tabId, { kind: "siren:seek", t: msg.t }).catch(() => {});
  }
});

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  const got = await chrome.storage.session.get(`tab:${tabId}`);
  chrome.runtime.sendMessage({ kind: "siren:update", state: got[`tab:${tabId}`] || null }).catch(() => {});
});

chrome.tabs.onRemoved.addListener((tabId) => chrome.storage.session.remove(`tab:${tabId}`));
