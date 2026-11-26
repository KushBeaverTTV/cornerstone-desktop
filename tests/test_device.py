"""Unit tests for cornerstone-device multi-device profile recommendations."""
import importlib.machinery
import importlib.util
import os
import unittest


HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEVICE_PATH = os.path.join(HERE, "bin", "cornerstone-device")
loader = importlib.machinery.SourceFileLoader("cornerstone_device", DEVICE_PATH)
spec = importlib.util.spec_from_loader("cornerstone_device", loader)
dev = importlib.util.module_from_spec(spec)
loader.exec_module(dev)


class DeviceProfileTests(unittest.TestCase):
    def test_apple_silicon_macbook_recommendation(self):
        profile = {
            "hostname": "omarchy",
            "arch": "aarch64",
            "model": "Mac17,5",
            "chassis": "laptop",
            "isAppleSilicon": True,
            "gpu": {"vendor": "apple", "model": "Apple Silicon (agx-t8140)", "backend": "unified", "hasDiscreteVram": False, "unified": True, "vramTotalMb": 0},
            "monitors": {"count": 1, "primary": "eDP-1", "maxLogicalWidth": 1505, "isCompact": True},
            "capture": {"backend": "wf-recorder", "replayBufferSupported": False},
            "browsers": [{"id": "google-chrome"}],
            "projectRoots": ["/home/u/Projects", "/home/u/Work"],
            "hardware": {"battery": True, "wave3": False, "storageMount": False},
            "services": {"lanMouse": True, "sunshine": False, "onedrive": False, "localStt": False, "jarvis": False, "hq": False, "clips": False, "powerProfiles": True},
        }
        rec = dev.recommend(profile)
        self.assertEqual(rec["barMode"], "compact")
        self.assertEqual(rec["dictationEngine"], "mistral")
        self.assertIn("cornerstone.rig", rec["enabledPlugins"])
        self.assertIn("cornerstone.gpu", rec["disabledPlugins"])
        self.assertIn("cornerstone.hq", rec["disabledPlugins"])
        self.assertNotIn("gpu", rec["statsTabs"].split(","))

    def test_amd_desktop_rig_recommendation(self):
        profile = {
            "hostname": "rig",
            "arch": "x86_64",
            "model": "Custom Desktop",
            "chassis": "desktop",
            "isAppleSilicon": False,
            "gpu": {"vendor": "amd", "model": "AMD GPU", "backend": "amd", "hasDiscreteVram": True, "unified": False, "vramTotalMb": 20480},
            "monitors": {"count": 2, "primary": "DP-1", "maxLogicalWidth": 2560, "isCompact": False},
            "capture": {"backend": "gpu-screen-recorder", "replayBufferSupported": True},
            "browsers": [{"id": "google-chrome"}],
            "projectRoots": ["/home/u/Projects"],
            "hardware": {"battery": False, "wave3": True, "storageMount": True},
            "services": {"lanMouse": True, "sunshine": True, "onedrive": True, "localStt": True, "jarvis": True, "hq": True, "clips": True, "powerProfiles": False},
        }
        rec = dev.recommend(profile)
        self.assertEqual(rec["barMode"], "full")
        self.assertEqual(rec["dictationEngine"], "qwen")
        self.assertIn("cornerstone.gpu", rec["enabledPlugins"])
        self.assertIn("cornerstone.hq", rec["enabledPlugins"])
        self.assertEqual(rec["disabledPlugins"], [])
        self.assertIn("gpu", rec["statsTabs"].split(","))

    def test_nvidia_laptop_recommendation(self):
        profile = {
            "hostname": "thinkpad",
            "arch": "x86_64",
            "model": "ThinkPad P1",
            "chassis": "laptop",
            "isAppleSilicon": False,
            "gpu": {"vendor": "nvidia", "model": "RTX 4070", "backend": "nvidia", "hasDiscreteVram": True, "unified": False, "vramTotalMb": 8192},
            "monitors": {"count": 1, "primary": "eDP-1", "maxLogicalWidth": 1920, "isCompact": False},
            "capture": {"backend": "gpu-screen-recorder", "replayBufferSupported": False},
            "browsers": [{"id": "brave"}],
            "projectRoots": ["/home/u/Code"],
            "hardware": {"battery": True, "wave3": False, "storageMount": False},
            "services": {"lanMouse": False, "sunshine": False, "onedrive": False, "localStt": False, "jarvis": False, "hq": False, "clips": False, "powerProfiles": True},
        }
        rec = dev.recommend(profile)
        self.assertEqual(rec["barMode"], "compact")
        self.assertIn("cornerstone.gpu", rec["enabledPlugins"])
        self.assertIn("cornerstone.hq", rec["disabledPlugins"])
        self.assertIn("gpu", rec["statsTabs"].split(","))


if __name__ == "__main__":
    unittest.main()
