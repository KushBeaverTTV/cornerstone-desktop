chrome.runtime.onMessage.addListener((msg, sender) => {
  if (!msg || msg.type !== "muse-usage" || !sender.url || !sender.url.startsWith("https://muse.ai/")) return;
  chrome.runtime.sendNativeMessage("com.kushbeaverttv.muse_usage", msg.data, () => void chrome.runtime.lastError);
});
