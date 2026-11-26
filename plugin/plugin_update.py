"""Release checks use the product's GitHub tags. Installation goes through Codex."""
from contextlib import closing
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
NAME = MANIFEST["name"]
VERSION = MANIFEST["version"]
SOURCE = MANIFEST["repository"] + ".git"
MARKET = "mogoo-codex-plugin"
MARKET_SOURCE = "https://github.com/MogooStudio/mogoo-codex-plugin.git"
HOME = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve()
DATA = Path(os.environ.get("MOGOO_PROMPTS_DATA") or HOME / NAME)
STABLE = re.compile(r"(?:0|[1-9][0-9]{0,8})(?:\.(?:0|[1-9][0-9]{0,8})){2}")


def version_key(value):
    if isinstance(value, str) and STABLE.fullmatch(value):
        return tuple(map(int, value.split(".")))
    return ()


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def run(args, timeout):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="0")
    return subprocess.run(args, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                          encoding="utf-8", timeout=timeout, check=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout


def releases():
    refs = dict(line.split("\t")[::-1] for line in run(
        ["git", "ls-remote", "--", SOURCE, "refs/heads/main", "refs/tags/v*"], 15).splitlines())
    tags = [ref[11:] for ref in refs if ref.startswith("refs/tags/v") and version_key(ref[11:])]
    latest = max(tags, key=version_key, default=None)
    ref = f"refs/tags/v{latest}"
    return latest, bool(latest and refs.get(ref + "^{}", refs.get(ref)) == refs.get("refs/heads/main"))


def codex(*args):
    binary = os.environ.get("CODEX_APP_RUNTIME_CLI_PATH") or shutil.which(
        "codex.exe" if os.name == "nt" else "codex")
    if not binary:
        raise ValueError("找不到 Codex CLI，可在终端运行更新命令。")
    return json.loads(run([binary, "plugin", *args, "--json"], 60))


def cache(market):
    return HOME / "plugins" / "cache" / market / NAME


def installed_version(market):
    base = cache(market)
    versions = []
    for entry in base.glob("*"):
        if version_key(entry.name):
            manifest = load_json(entry / ".codex-plugin" / "plugin.json")
            if manifest.get("name") == NAME and manifest.get("version") == entry.name:
                versions.append(entry.name)
    return max(versions, key=version_key, default=None)


def snapshot(market):
    return HOME / ".tmp" / "marketplaces" / market


def verified_market(market):
    entries = [m for m in codex("marketplace", "list")["marketplaces"] if m["name"] == market]
    if len(entries) != 1:
        return False
    entry = entries[0]
    origin = entry.get("marketplaceSource", {})
    expected = SOURCE if market == NAME else MARKET_SOURCE
    if (origin.get("sourceType") != "git" or origin.get("source") != expected
            or Path(entry["root"]).resolve() != snapshot(market)):
        return False
    return valid_catalog(market)


def valid_catalog(market):
    catalog = load_json(snapshot(market) / ".agents/plugins/marketplace.json")
    sources = [p["source"] for p in catalog.get("plugins", []) if p.get("name") == NAME]
    if catalog.get("name") != market or len(sources) != 1:
        return False
    source = sources[0]
    return (source.get("source") == "git-subdir" and source.get("url") == SOURCE
            and source.get("ref") == "main" and source.get("path") in ("plugin", "./plugin"))


def state(change=None):
    DATA.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DATA / "plugin-update.sqlite3", timeout=3)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        if change:
            db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT data FROM settings WHERE id=1").fetchone()
        info = json.loads(row[0]) if row else {}
        if change:
            change(info)
            db.execute("INSERT OR REPLACE INTO settings VALUES (1,?)", (json.dumps(info),))
    return info


def status(info, market):
    now = time.time()
    installed = installed_version(market)
    pending = version_key(installed) > version_key(VERSION)
    latest = info.get("latest")
    newer = version_key(latest) > max(version_key(VERSION), version_key(installed))
    available = newer and info.get("dismissed") != latest and not pending
    installing = info.get("installUntil", 0) > now
    commands = [f"codex plugin add {NAME}@{market} --json"]
    if not valid_catalog(market):
        commands.insert(0, f"codex plugin marketplace upgrade {market} --json")
    return dict(running=VERSION, installed=installed, snapshot=None, latest=latest,
                pending=pending, available=available, dismissed=newer and not available and not pending,
                checking=info.get("checkUntil", 0) > now, installing=installing,
                checked=bool(info.get("checkedAt")), error=info.get("checkError"),
                installError=info.get("installError") if not pending and not installing else None,
                auto=info.get("auto", True), commands=commands, currentRelease=info.get("atMain", False),
                canInstall=available and info.get("atMain", False) and not info.get("checkError")
                and ROOT == cache(market) / VERSION and valid_catalog(market) and not installing)


def start_job(kind, prepare, work):
    token = uuid4().hex
    def claim(info):
        if info.get(kind + "Until", 0) <= time.time() and prepare(info):
            info[kind + "Token"] = token
            info[kind + "Until"] = time.time() + (360 if kind == "install" else 45)
    if state(claim).get(kind + "Token") != token:
        return

    def worker():
        try:
            result = work()
        except Exception as exc:
            message = str(exc) if isinstance(exc, UpdateError) else (
                "安装未完成，请核对市场来源与已安装版本后重试。" if kind == "install" else "暂时无法读取 GitHub 版本标签。")
            result = {"installError": message} if kind == "install" else {
                "checkedAt": time.time(), "checkedWith": VERSION, "checkError": message, "atMain": False}
        def finish(info):
            if info.get(kind + "Token") == token:
                info.update(result)
                info.pop(kind + "Until", None)
                info.pop(kind + "Token", None)
        state(finish)
    threading.Thread(target=worker, daemon=True).start()


class UpdateError(ValueError):
    pass


def check(action):
    def due(info):
        if action == "check":
            return True
        delay = 3600 if info.get("checkError") else 21600
        return info.get("auto", True) and (info.get("checkedWith") != VERSION
                                           or time.time() - info.get("checkedAt", 0) >= delay)
    def fetch():
        latest, at_main = releases()
        return dict(latest=latest, atMain=at_main, checkedAt=time.time(), checkedWith=VERSION, checkError=None)
    start_job("check", due, fetch)


def install(market, target):
    def ready(info):
        if not status(info, market)["canInstall"] or target != info.get("latest"):
            raise UpdateError("可安装版本已变化，请重新检查。")
        info["installError"] = "上次安装已中断，请重新检查后重试。"
        return True

    def apply():
        if not verified_market(market) or releases() != (target, True):
            raise UpdateError("市场来源或 GitHub 发行版本已变化，请核对后重试。")
        if version_key(installed_version(market)) < version_key(target):
            try:
                codex("add", f"{NAME}@{market}")
            except (ValueError, OSError, subprocess.SubprocessError):
                if version_key(installed_version(market)) < version_key(target):
                    raise
        if version_key(installed_version(market)) < version_key(target):
            raise UpdateError("Codex 尚未安装目标版本。")
        return dict(installError=None)
    start_job("install", ready, apply)


def update(action, data):
    market = NAME if ROOT == cache(NAME) / VERSION else MARKET
    if action in ("auto", "check"):
        check(action)
    elif action == "configure" and isinstance(data.get("enabled"), bool):
        state(lambda info: info.update(auto=data["enabled"]))
    elif action == "dismiss" and version_key(data.get("target")):
        def dismiss(info):
            if not status(info, market)["available"] or data["target"] != info.get("latest"):
                raise UpdateError("新版已变化，请重新检查。")
            info["dismissed"] = data["target"]
        state(dismiss)
    elif action == "install" and data.get("confirmed") is True and version_key(data.get("target")):
        install(market, data["target"])
    elif action != "status":
        raise UpdateError("无效的插件更新操作。")
    return status(state(), market)
