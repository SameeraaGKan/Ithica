// The Siren — content script. Reads what's playing on YouTube / Twitch and reports it
// to the background worker. It never changes the page except to seek when asked.
(() => {
  const PLATFORM = location.hostname.includes("twitch.tv") ? "twitch" : "youtube";
  let last = null;

  function youtubeState() {
    const url = new URL(location.href);
    let videoId = url.searchParams.get("v");
    if (!videoId && url.pathname.startsWith("/shorts/")) videoId = url.pathname.split("/")[2];
    if (!videoId) return null;
    const video = document.querySelector("video.html5-main-video") || document.querySelector("video");
    const ownerLink =
      document.querySelector("ytd-watch-metadata ytd-channel-name a") ||
      document.querySelector("#owner #channel-name a") ||
      document.querySelector("ytd-reel-player-overlay-renderer ytd-channel-name a");
    const channelName = ownerLink?.textContent?.trim() || "";
    const href = ownerLink?.getAttribute("href") || "";
    const channelHandle = (href.match(/\/(@[^/?]+)/) || [])[1] || "";
    const title =
      document.querySelector("ytd-watch-metadata h1 yt-formatted-string")?.textContent?.trim() ||
      document.title.replace(/ - YouTube$/, "");
    return {
      platform: "youtube", videoId, title, channelName, channelHandle,
      t: video ? Math.floor(video.currentTime) : 0,
      paused: video ? video.paused : true
    };
  }

  function twitchState() {
    const parts = location.pathname.split("/").filter(Boolean);
    if (!parts.length) return null;
    const isVod = parts[0] === "videos";
    const video = document.querySelector("video");
    const login = isVod
      ? (document.querySelector('a[data-a-target="stream-info-card-component--channel-link"], h1.tw-title')?.textContent || "").trim().toLowerCase()
      : parts[0].toLowerCase();
    const reserved = ["directory", "settings", "search", "downloads", "turbo", "p", "jobs"];
    if (!isVod && reserved.includes(login)) return null;
    return {
      platform: "twitch",
      videoId: isVod ? `twitch:vod:${parts[1]}` : `twitch:live:${login}`,
      title: document.title.replace(/ - Twitch$/, ""),
      channelName: login, channelHandle: login,
      t: video ? Math.floor(video.currentTime) : 0,
      paused: video ? video.paused : true,
      live: !isVod
    };
  }

  function tick() {
    const s = PLATFORM === "youtube" ? youtubeState() : twitchState();
    if (!s) {
      if (last) { last = null; chrome.runtime.sendMessage({ kind: "siren:state", state: null }).catch(() => {}); }
      return;
    }
    // Report on a new video, a seek (jump > 4s), or every 10s of play — not every tick.
    const changed = !last || last.videoId !== s.videoId || last.channelName !== s.channelName ||
      Math.abs(s.t - last.t) > 4 || s.paused !== last.paused || (!s.paused && s.t - (last.sentT ?? 0) >= 10);
    if (changed) {
      s.sentT = s.t;
      chrome.runtime.sendMessage({ kind: "siren:state", state: s }).catch(() => {});
      last = s;
    } else {
      last = { ...last, t: s.t };
    }
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.kind === "siren:seek") {
      const v = document.querySelector("video");
      if (v && Number.isFinite(msg.t)) { v.currentTime = msg.t; v.play?.(); }
    }
    if (msg?.kind === "siren:ping") { last = null; tick(); }
  });

  setInterval(tick, 1000);
  tick();
})();
