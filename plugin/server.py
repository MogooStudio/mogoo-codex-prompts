"""Local stdio MCP App for personal prompt collections. Python standard library."""
import json
import os
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4

import plugin_update

PANEL_TITLE = "Mogoo 常用提示词"
URI = "ui://mogoo-codex-prompts/panel.html"
MIME = "text/html;profile=mcp-app"
VERSION = plugin_update.VERSION
ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("MOGOO_PROMPTS_DATA") or
            Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "mogoo-codex-prompts")
SEEDS = [
    ("review", "只审查改动", "按严重程度列出问题，附上文件位置和触发条件。等我确认后再改。", "审查"),
    ("verify", "附上验证结果", "列出跑过的检查、结果，以及还没验证的部分。", "开发"),
    ("discuss", "先讨论需求", "先梳理使用场景和需要我决定的问题，确认后再讨论界面。", "开发"),
]


def initial():
    return dict(categories=["审查", "开发", "发布"], recent=[], revision=0, appearance="auto",
                prompts=[dict(id=i, title=t, body=b, category=c, saved=True) for i, t, b, c in SEEDS])


def text(args, key):
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("请填写有效的" + key)
    return value


def mutate(state, action, args):
    categories, prompts = state["categories"], state["prompts"]
    if action == "appearance":
        mode = args.get("mode")
        if mode not in ("auto", "light", "dark"):
            raise ValueError("外观选项无效。")
        state["appearance"] = mode
        return
    if action != "use" and args.get("revision") != state["revision"]:
        raise ValueError("其他面板已更新，请核对最新内容后再保存。")
    if action in ("add_category", "rename_category"):
        label = text(args, "name").strip()
        old = args.get("category")
        if len(label) > 40 or label.casefold() in {name.casefold() for name in ["全部", *categories]}:
            raise ValueError("分类名称已使用或超过 40 字。")
        if action == "add_category":
            categories.append(label)
        else:
            categories[categories.index(old)] = label
            for prompt in prompts:
                if prompt["category"] == old:
                    prompt["category"] = label
    elif action == "move_category":
        idx = categories.index(args.get("category"))
        step = args.get("step")
        if step not in (-1, 1) or not 0 <= idx + step < len(categories):
            raise ValueError("分类已在列表边缘。")
        categories[idx], categories[idx+step] = categories[idx+step], categories[idx]
    elif action in ("create", "edit"):
        category = args.get("category")
        if category not in categories:
            raise ValueError("请重新选择分类。")
        body = text(args, "body")
        values = dict(body=body, title=text(args, "title").strip(), category=category)
        if action == "create":
            prompts.insert(0, dict(id=uuid4().hex, saved=True, **values))
        else:
            find_prompt(prompts, args).update(values)
    elif action in ("use", "favorite"):
        prompt = find_prompt(prompts, args)
        if action == "use":
            state["recent"] = [prompt["id"]] + [i for i in state["recent"] if i != prompt["id"]]
        else:
            prompt["saved"] = not prompt["saved"]
    else:
        raise ValueError("未知操作。")


def find_prompt(prompts, args):
    for prompt in prompts:
        if prompt["id"] == args.get("id"):
            return prompt
    raise ValueError("提示词不存在。")


def collection(action, args):
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / "prompts.sqlite3", timeout=8)
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS collection (id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
            row = db.execute("SELECT data FROM collection WHERE id=1").fetchone()
            state = json.loads(row[0]) if row else initial()
            if action != "list":
                mutate(state, action, args)
                if action not in ("use", "appearance"):
                    state["revision"] += 1
            if not row or action != "list":
                db.execute("INSERT OR REPLACE INTO collection VALUES (1,?)", (json.dumps(state, ensure_ascii=False),))
        return state
    finally:
        db.close()


def descriptor(name, description, schema, meta):
    return dict(name=name, description=description, inputSchema=schema, _meta=meta)


def result(data):
    return dict(content=[dict(type="text", text="常用提示词")], structuredContent=data)


def dispatch(method, params):
    if method == "initialize":
        protocol = params.get("protocolVersion")
        supported = ("2025-11-25", "2025-06-18", "2025-03-26")
        return dict(protocolVersion=protocol if protocol in supported else supported[0],
                    capabilities=dict(tools={}, resources={}), serverInfo=dict(name="mogoo-codex-prompts", version=VERSION))
    if method == "ping":
        return {}
    if method == "resources/templates/list":
        return {"resourceTemplates": []}
    if method == "resources/list":
        return {"resources": [dict(uri=URI, name=PANEL_TITLE, mimeType=MIME)]}
    if method == "resources/read":
        if params.get("uri") != URI:
            raise ValueError("未知资源。")
        panel = (ROOT / "panel.html").read_text(encoding="utf-8").replace(
            "<!-- panel-runtime -->", "<script>" + (ROOT / "panel.js").read_text(encoding="utf-8") + "</script>")
        panel = panel.replace("<!-- plugin-version -->", VERSION)
        return {"contents": [dict(uri=URI, mimeType=MIME, text=panel,
                                  _meta={"ui": {"csp": {"connectDomains": [], "resourceDomains": []},
                                                "permissions": {"clipboardWrite": {}}}})]}
    if method == "tools/list":
        entry = {"ui": {"resourceUri": URI, "visibility": ["model", "app"]},
                 "openai/ui": {"entrypoints": [{"type": "thread"}]}}
        empty = dict(type="object", properties={}, additionalProperties=False)
        schema = dict(type="object", properties={"action": {"type":"string"}, "data": {"type":"object"}},
                      required=["action"], additionalProperties=False)
        return {"tools": [descriptor("prompts_panel", "打开当前聊天的常用提示词面板。", empty, entry) | {"title": PANEL_TITLE},
                          descriptor("prompts_update", "查看版本和管理插件更新。", schema, {"ui":{"visibility":["app"]}}),
                          descriptor("prompts_collection", "读取和更新本机收藏。", schema, {"ui":{"visibility":["app"]}})]}
    if method == "tools/call":
        if params.get("name") == "prompts_panel":
            payload = result({"threadId": (params.get("_meta") or {}).get("threadId")})
            payload["_meta"] = {"ui": {"resourceUri":URI}}
            return payload
        if params.get("name") in ("prompts_collection", "prompts_update"):
            args = params.get("arguments") or {}
            try:
                handler = plugin_update.update if params["name"] == "prompts_update" else collection
                return result(handler(args["action"], args.get("data") or {}))
            except (ValueError, sqlite3.Error, OSError, KeyError, TypeError) as exc:
                return {"isError":True, "content":[{"type":"text","text":str(exc)}]}
    raise LookupError(method)


def main():
    for line in sys.stdin.buffer:
        ident = None
        try:
            request = json.loads(line)
            if "id" not in request:
                continue
            ident = request["id"]
            reply = {"result":dispatch(request["method"], request.get("params", {}))}
        except LookupError:
            reply = {"error":{"code":-32601,"message":"未知请求。"}}
        except (TypeError, ValueError, OSError) as exc:
            reply = {"error":{"code":-32602,"message":str(exc)}}
        print(json.dumps(dict(jsonrpc="2.0", id=ident, **reply), ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
