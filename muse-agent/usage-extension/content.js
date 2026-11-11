// Reads the quota text Muse shows on its settings page. Nothing leaves this
// machine: the numbers go to the local Omarchy helper only.
(() => {
  const MULT = { k: 1e3, thousand: 1e3, m: 1e6, million: 1e6, b: 1e9, billion: 1e9, t: 1e12, trillion: 1e12 };
  const toNum = (n, s) => {
    const v = parseFloat(String(n).replace(/,/g, ""));
    return isFinite(v) ? v * (MULT[(s || "").toLowerCase()] || 1) : null;
  };
  let last = "";
  function scan() {
    const text = (document.body && document.body.innerText || "").slice(0, 200000);
    const out = {};
    const pct = text.match(/(\d{1,3}(?:\.\d+)?)\s*%\s*(?:of\s+[^\n%]{0,30}?)?used/i);
    if (pct) out.weeklyPct = Math.min(100, parseFloat(pct[1]));
    const reset = text.match(/resets?\s+(?:on|in|at)\s+([^\n]{3,48})/i);
    if (reset) out.resetText = reset[1].trim();
    const plan = text.match(/\b(Free|Power|Maximum)\s+(?:plan|tier)\b/i);
    if (plan) out.plan = plan[1][0].toUpperCase() + plan[1].slice(1).toLowerCase();
    const re = /([\d][\d.,]*)\s*(k|m|b|t|thousand|million|billion|trillion)?\b\s*(?:muse\s+)?tokens?/gi;
    let m;
    while ((m = re.exec(text))) {
      const around = text.slice(Math.max(0, m.index - 90), m.index + m[0].length + 60).toLowerCase();
      if (/additional|bonus|extra|referral|credit|no expiration/.test(around)) {
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
