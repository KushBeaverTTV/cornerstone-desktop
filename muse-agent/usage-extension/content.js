// Reads the quota text Muse shows on its settings/subscriptions page.
// Nothing leaves this machine: the numbers go to the local Omarchy helper only.
(() => {
  const MULT = { k: 1e3, thousand: 1e3, m: 1e6, million: 1e6, b: 1e9, billion: 1e9, t: 1e12, trillion: 1e12 };
  const toNum = (n, s) => {
    const v = parseFloat(String(n).replace(/,/g, ""));
    return isFinite(v) ? v * (MULT[(s || "").toLowerCase()] || 1) : null;
  };
  let last = "";

  function findPercent(text) {
    const usedAfter = text.match(/(\d{1,3}(?:\.\d+)?)\s*%\s*(?:of\s+[^\n%]{0,36}?)?used/i);
    if (usedAfter) return Math.min(100, Math.max(0, parseFloat(usedAfter[1])));
    const usedBefore = text.match(/\bused\s*:?\s*(\d{1,3}(?:\.\d+)?)\s*%/i);
    if (usedBefore) return Math.min(100, Math.max(0, parseFloat(usedBefore[1])));
    const remaining = text.match(/(\d{1,3}(?:\.\d+)?)\s*%\s*(?:of\s+[^\n%]{0,36}?)?(?:remaining|left)/i);
    if (remaining) return Math.min(100, Math.max(0, 100 - parseFloat(remaining[1])));
    const weeklyBlock = text.match(/weekly[^\n]{0,40}\n?\s*(\d{1,3}(?:\.\d+)?)\s*%/i);
    if (weeklyBlock) return Math.min(100, Math.max(0, parseFloat(weeklyBlock[1])));
    const bar = document.querySelector('[role="progressbar"][aria-valuenow]');
    if (bar) {
      const now = parseFloat(bar.getAttribute("aria-valuenow"));
      const max = parseFloat(bar.getAttribute("aria-valuemax") || "100") || 100;
      if (isFinite(now) && max > 0) return Math.min(100, Math.max(0, (now / max) * 100));
    }
    return undefined;
  }

  function scan() {
    const text = (document.body && document.body.innerText || "").slice(0, 200000);
    const out = {};
    const pct = findPercent(text);
    if (pct !== undefined) out.weeklyPct = Math.round(pct * 10) / 10;

    const reset = text.match(/(?:resets?|renews?)\s+(?:on|in|at)\s+([^\n]{3,48})/i);
    if (reset) out.resetText = reset[1].trim();

    const plan = text.match(/\b(Free|Power|Pro|Max|Maximum)\s+(?:plan|tier)\b/i)
      || text.match(/\bcurrent\s+plan\s*:?\s*(Free|Power|Pro|Max|Maximum)\b/i);
    if (plan) out.plan = plan[1][0].toUpperCase() + plan[1].slice(1).toLowerCase();

    const re = /([\d][\d.,]*)\s*(k|m|b|t|thousand|million|billion|trillion)?\b\s*(?:muse\s+)?tokens?/gi;
    let m;
    while ((m = re.exec(text))) {
      const around = text.slice(Math.max(0, m.index - 90), m.index + m[0].length + 60).toLowerCase();
      if (/additional|bonus|extra|referral|credit|top-?up|no expiration/.test(around)) {
        const v = toNum(m[1], m[2]);
        if (v !== null) { out.extraTokens = v; out.extraText = m[0].trim(); break; }
      }
    }
    if (out.weeklyPct === undefined && out.extraTokens === undefined) return;
    const key = JSON.stringify(out);
    if (key === last) return;
    last = key;
    chrome.runtime.sendMessage({ type: "muse-usage", data: out });
  }

  let t = null;
  const later = () => { clearTimeout(t); t = setTimeout(scan, 800); };
  new MutationObserver(later).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  later();
})();
