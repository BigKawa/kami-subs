// Kami Subs — content script
// Mounts a subtitle overlay anchored over the most likely active video element.

const OVERLAY_ID = 'kami-subs-overlay';
const MAX_VISIBLE_CHARS = 180;
// Clear the overlay this long after the last transcript update. While someone's
// talking, updates land ~every second and keep resetting this timer, so the
// line stays put; it only fades once speech actually stops for a few seconds.
// Allow a full 5s speech section plus processing before fading the last line.
const CLEAR_AFTER_MS = 6500;

const isSubframe = window.top !== window;
let captureMounted = false;
let latestText = '';
let latestTextAt = 0;
let lastSettings = {};
let overlayEl = null;
let textEl = null;
let hideTimer = null;
let trackedVideo = null;
let resizeObserver = null;
let scrollHandler = null;
const nativeTracks = new WeakMap();
let activeNativeTrack = null;

function clearNativeSubtitle() {
  if (!activeNativeTrack) return;
  for (const cue of Array.from(activeNativeTrack.cues || [])) activeNativeTrack.removeCue(cue);
  activeNativeTrack.mode = 'disabled';
  activeNativeTrack = null;
}

function updateNativeSubtitle(text) {
  clearNativeSubtitle();
  const fullscreen = document.fullscreenElement || document.webkitFullscreenElement;
  if (!text || !fullscreen || fullscreen.tagName !== 'VIDEO') return;
  // Chromium renders native video fullscreen in a special video surface.
  // Its own subtitle track remains visible where normal DOM overlays do not.
  let track = nativeTracks.get(fullscreen);
  if (!track) {
    track = fullscreen.addTextTrack('subtitles', 'Kami Subs');
    nativeTracks.set(fullscreen, track);
  }
  track.mode = 'showing';
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const cue = new VTTCue(0, 1e10, escaped);
  cue.align = 'center';
  cue.line = (overlayEl?.dataset.position === 'top') ? 1 : -3;
  track.addCue(cue);
  activeNativeTrack = track;
}

function pickPrimaryVideo() {
  const videos = Array.from(document.querySelectorAll('video'));
  if (videos.length === 0) return null;
  // Prefer the largest visible video.
  let best = null;
  let bestArea = 0;
  for (const v of videos) {
    const r = v.getBoundingClientRect();
    const area = Math.max(0, r.width) * Math.max(0, r.height);
    if (area > bestArea) { bestArea = area; best = v; }
  }
  return best;
}

function syncOverlayLayer() {
  if (!overlayEl) return;
  const fullscreen = document.fullscreenElement || document.webkitFullscreenElement;
  const nativeVideo = fullscreen?.tagName === 'VIDEO';
  const embeddedVideo = fullscreen?.tagName === 'IFRAME';
  overlayEl.style.visibility = (nativeVideo || embeddedVideo) ? 'hidden' : '';
  if (fullscreen && !nativeVideo && !embeddedVideo && typeof overlayEl.showPopover === 'function') {
    // Keep a container-fullscreen overlay in its top layer.
    if (overlayEl.parentNode !== fullscreen) {
      fullscreen.appendChild(overlayEl);
    }
    overlayEl.setAttribute('popover', 'manual');
    try {
      if (overlayEl.matches(':popover-open')) overlayEl.hidePopover();
      overlayEl.showPopover();
      return;
    } catch (err) {
      console.warn('[kami-subs] top-layer overlay unavailable', err);
    }
  }
  if (overlayEl.hasAttribute('popover')) {
    try { overlayEl.hidePopover(); } catch (e) {}
    overlayEl.removeAttribute('popover');
  }
  // Compatibility fallback for browsers without the Popover API.
  const host = (nativeVideo || embeddedVideo) ? document.documentElement : (fullscreen || document.documentElement);
  if (overlayEl.parentNode !== host) host.appendChild(overlayEl);
}

function ensureOverlay(settings) {
  // If we hold a reference that's still in the DOM, reuse it.
  if (overlayEl && overlayEl.isConnected) {
    syncOverlayLayer();
    return overlayEl;
  }
  // Service-worker restarts or stale content-script reloads can leave orphan
  // overlay elements in the DOM that we no longer hold a ref to. Sweep them
  // out before creating a new one — otherwise they stack.
  document.querySelectorAll('#' + OVERLAY_ID).forEach(n => n.remove());
  overlayEl = document.createElement('div');
  overlayEl.id = OVERLAY_ID;
  overlayEl.setAttribute('dir', 'auto');
  textEl = document.createElement('span');
  textEl.className = 'kami-subs-text';
  overlayEl.appendChild(textEl);
  document.documentElement.appendChild(overlayEl);
  syncOverlayLayer();
  applySettings(settings || {});
  return overlayEl;
}

function relocateForFullscreen() {
  if (isSubframe) {
    const fullscreen = document.fullscreenElement || document.webkitFullscreenElement;
    if (!fullscreen) {
      clearNativeSubtitle();
      if (overlayEl) overlayEl.classList.remove('kami-visible');
      return;
    }
    if (!captureMounted) return;
    ensureOverlay(lastSettings);
    if (Date.now() - latestTextAt < CLEAR_AFTER_MS) setText(latestText);
  }
  if (!overlayEl) return;
  syncOverlayLayer();
  updateNativeSubtitle(overlayEl.classList.contains('kami-visible') ? textEl.textContent : '');
  positionOverlayOverVideo();
}
document.addEventListener('fullscreenchange', relocateForFullscreen);
document.addEventListener('webkitfullscreenchange', relocateForFullscreen);

function applySettings(settings) {
  if (!overlayEl) return;
  const fontSize = settings.fontSize || 28;
  overlayEl.style.setProperty('--kami-font-size', fontSize + 'px');
  const position = settings.position || 'bottom';
  overlayEl.dataset.position = position;
}

function positionOverlayOverVideo() {
  if (!overlayEl) return;
  // Viewport-anchored positioning works reliably in every layout:
  // tall pages, fullscreen players, iframes, weird custom skins, etc.
  // Trying to follow the video element's bounding box ends up offscreen
  // whenever the player is taller than the viewport or scrolls oddly.
  overlayEl.style.left = '50%';
  overlayEl.style.transform = 'translateX(-50%)';
  overlayEl.style.width = 'min(86vw, 1200px)';
  if ((overlayEl.dataset.position || 'bottom') === 'top') {
    overlayEl.style.top = '6vh';
    overlayEl.style.bottom = '';
  } else {
    overlayEl.style.bottom = '8vh';
    overlayEl.style.top = '';
  }
}

function trackVideo() {
  trackedVideo = pickPrimaryVideo();
  if (resizeObserver) try { resizeObserver.disconnect(); } catch (e) {}
  if (window.ResizeObserver && trackedVideo) {
    resizeObserver = new ResizeObserver(() => positionOverlayOverVideo());
    resizeObserver.observe(trackedVideo);
  }
  scrollHandler = () => positionOverlayOverVideo();
  window.addEventListener('scroll', scrollHandler, { passive: true });
  window.addEventListener('resize', scrollHandler);
  positionOverlayOverVideo();
}

function untrackVideo() {
  if (resizeObserver) { try { resizeObserver.disconnect(); } catch (e) {} resizeObserver = null; }
  if (scrollHandler) {
    window.removeEventListener('scroll', scrollHandler);
    window.removeEventListener('resize', scrollHandler);
    scrollHandler = null;
  }
  trackedVideo = null;
}

function mount(settings) {
  captureMounted = true;
  lastSettings = settings || {};
  // Only the main frame draws ordinary subtitles; embedded frames draw them
  // when their own player enters fullscreen, avoiding duplicate overlays.
  if (isSubframe && !document.fullscreenElement && !document.webkitFullscreenElement) return;
  ensureOverlay(lastSettings);
  trackVideo();
  // Don't reveal the overlay until we actually have text — otherwise the user
  // sees an empty black padded box during the seconds before the first chunk.
}

function unmount() {
  captureMounted = false;
  latestText = '';
  clearNativeSubtitle();
  if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
  untrackVideo();
  // Belt-and-suspenders: remove every #kami-subs-overlay in the DOM, not just
  // the one we hold a ref to (defensive against orphans from previous loads).
  document.querySelectorAll('#' + OVERLAY_ID).forEach(n => n.remove());
  overlayEl = null;
  textEl = null;
}

function setText(text) {
  latestText = text || '';
  latestTextAt = Date.now();
  if (isSubframe && (!captureMounted || (!document.fullscreenElement && !document.webkitFullscreenElement))) return;
  if (!overlayEl) ensureOverlay(lastSettings);
  let t = (text || '').trim();
  if (!t) {
    // Empty transcript — hide instead of showing a blank black box.
    overlayEl.classList.remove('kami-visible');
    textEl.textContent = '';
    clearNativeSubtitle();
    return;
  }
  if (t.length > MAX_VISIBLE_CHARS) t = '…' + t.slice(-MAX_VISIBLE_CHARS);
  textEl.textContent = t;
  updateNativeSubtitle(t);
  overlayEl.classList.add('kami-visible');
  positionOverlayOverVideo();
  // Reset the idle clear-timer on every update. The line persists through the
  // gaps between chunks but disappears once speech stops for CLEAR_AFTER_MS.
  if (hideTimer) clearTimeout(hideTimer);
  hideTimer = setTimeout(() => {
    if (overlayEl) {
      overlayEl.classList.remove('kami-visible');
      if (textEl) textEl.textContent = '';
      clearNativeSubtitle();
    }
    hideTimer = null;
  }, CLEAR_AFTER_MS);
}

function showError(msg) {
  if (isSubframe && (!captureMounted || (!document.fullscreenElement && !document.webkitFullscreenElement))) return;
  if (!overlayEl) ensureOverlay(lastSettings);
  textEl.textContent = '⚠ ' + msg;
  updateNativeSubtitle(textEl.textContent);
  overlayEl.classList.add('kami-visible', 'kami-error');
  if (hideTimer) clearTimeout(hideTimer);
  hideTimer = setTimeout(() => {
    if (overlayEl) overlayEl.classList.remove('kami-error');
  }, 4000);
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || !msg.type) return;
  switch (msg.type) {
    case 'ping':            sendResponse({ ok: true }); return true;
    case 'overlay:mount':   mount(msg.settings); break;
    case 'overlay:unmount': unmount(); break;
    case 'overlay:text':    setText(msg.text); break;
    case 'overlay:error':   showError(msg.message); break;
  }
});

// If the page loads while capture is already active, restore the overlay.
chrome.storage.local.get(['isCapturing', 'activeTabId', 'settings'], (s) => {
  if (s && s.isCapturing) mount(s.settings || {});
});
