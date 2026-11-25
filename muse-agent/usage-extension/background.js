const ALLOWED_ORIGINS = [
  "https://muse.ai/",
  "https://www.muse.ai/",
  "https://agent.meta.ai/"
];

chrome.runtime.onMessage.addListener((msg, sender) => {
  const url = (sender && sender.url) || "";
  if (!msg || msg.type !== "muse-usage") return;
  if (!ALLOWED_ORIGINS.some((prefix) => url.startsWith(prefix))) return;
  chrome.runtime.sendNativeMessage("com.kushbeaverttv.muse_usage", msg.data, () => void chrome.runtime.lastError);
});
