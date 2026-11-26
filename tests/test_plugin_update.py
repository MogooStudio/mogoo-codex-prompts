import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin"))
import plugin_update as updater
import server


class UpdateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        home = Path(tmp.name).resolve()
        for key, value in {"HOME": home, "DATA": home / "data"}.items():
            self.enter_patch(key, value)
        self.market = updater.MARKET
        self.enter_patch("ROOT", self.package(updater.VERSION))
        snap = updater.snapshot(self.market)
        self.catalog = snap / ".agents/plugins/marketplace.json"
        self.catalog.parent.mkdir(parents=True)
        self.entry = {"name": updater.NAME, "source": {"source": "local", "path": "./plugin"}}
        self.write_catalog()
        self.registration = {"marketplaces": [{"name": self.market, "root": str(snap),
                             "marketplaceSource": {"sourceType": "git", "source": updater.SOURCE}}]}

    def enter_patch(self, key, value):
        obj = patch.object(updater, key, value)
        obj.start()
        self.addCleanup(obj.stop)

    def package(self, version):
        root = updater.cache(self.market) / version
        manifest = root / ".codex-plugin/plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps(dict(name=updater.NAME, version=version)), encoding="utf-8")
        return root

    def write_catalog(self):
        self.catalog.write_text(json.dumps(dict(name=self.market, plugins=[self.entry])), encoding="utf-8")

    def wait(self, key):
        for _ in range(100):
            info = updater.update("status", {})
            if not info[key]:
                return info
            time.sleep(.02)
        self.fail(key)

    def test_stable_tags_and_annotated_head(self):
        refs = ["a\trefs/heads/main", "a\trefs/tags/v0.9.1", "b\trefs/tags/v0.12.3",
                "a\trefs/tags/v0.12.3^{}", "a\trefs/tags/v0.20.0-rc.1", "a\trefs/tags/v02.0.0"]
        with patch.object(updater, "run", return_value="\n".join(refs)):
            self.assertEqual(updater.releases(), ("0.12.3", True))

    def test_github_install_confirmation_and_retry(self):
        target = "1.2.0"
        self.enter_patch("releases", lambda: (target, True))
        updater.update("check", {})
        self.assertTrue(self.wait("checking")["canInstall"])
        with self.assertRaises(ValueError):
            updater.update("install", dict(target=target))
        calls = []
        def cli(*args):
            calls.append(args)
            if args == ("marketplace", "list"):
                return self.registration
            if args == ("marketplace", "upgrade", self.market):
                path = updater.snapshot(self.market) / "plugin/plugin.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(dict(version=target)), encoding="utf-8")
                return {}
            self.assertEqual(args, ("add", f"{updater.NAME}@{self.market}"))
            self.package(target)
            raise OSError("CLI exited after installation")
        self.enter_patch("codex", cli)
        updater.update("install", dict(target=target, confirmed=True))
        result = self.wait("installing")
        self.assertTrue(result["pending"])
        self.assertIsNone(result["installError"])
        self.assertEqual(result["installed"], target)
        self.assertEqual(sum(args[0] == "add" for args in calls), 1)

    def test_reject_changed_market_or_remote(self):
        self.enter_patch("codex", lambda *args: self.registration if args[0] == "marketplace" else self.fail(args))
        target = "1.0.0"
        updater.state(lambda info: info.update(latest=target, atMain=True))
        self.registration["marketplaces"][0]["marketplaceSource"]["source"] += "/other"
        updater.update("install", dict(target=target, confirmed=True))
        self.assertTrue(self.wait("installing")["installError"])
        self.entry["source"]["path"] = "./other"
        self.write_catalog()
        self.assertFalse(updater.update("status", {})["canInstall"])

    def test_auto_check_and_dismiss(self):
        with patch.object(updater, "releases", return_value=("9.1.0", True)) as remote:
            updater.update("configure", {"enabled": False})
            updater.update("auto", {})
            remote.assert_not_called()
            updater.update("check", {})
            self.wait("checking")
            updater.update("configure", {"enabled": True})
            updater.update("auto", {})
            remote.assert_called_once()
            info = updater.update("dismiss", {"target": "9.1.0"})
            self.assertTrue(info["dismissed"])
            self.assertFalse(info["available"])

    def test_manifest_and_panel_agree(self):
        manifest = json.loads((server.ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], server.VERSION)
        self.assertEqual(manifest["interface"], updater.MANIFEST["extensions"]["com.openai"]["interface"])
        self.assertTrue((server.ROOT / manifest["interface"]["composerIcon"]).is_file())
        html = server.dispatch("resources/read", {"uri": server.URI})["contents"][0]["text"]
        self.assertIn(f'data-version="{server.VERSION}"', html)
        self.assertNotIn("<!-- plugin-version -->", html)
        tools = server.dispatch("tools/list", {})["tools"]
        update_tool = next(t for t in tools if t["name"] == "prompts_update")
        self.assertEqual(update_tool["_meta"]["ui"]["visibility"], ["app"])
