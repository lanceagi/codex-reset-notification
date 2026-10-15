#!/usr/bin/env python3
"""义父情报卡（Codex 额度重置）定时推送：cron 触发，每班一次。

最新事件 status=announced → 红题头「义父预告」卡（预计窗口+历史高发时段提示）；
否则 → 蓝题头「上次动作」卡；API 不可达 → 蓝题头「接口暂不可达」卡。

发送通道（skill 本职=跑通"获取重置情报并生成卡片"，投递方式自选）：
1. lark-cli 管道（推荐，飞书官方开源 CLI：https://github.com/larksuite/cli）：
   python3 push_reset.py --print-card | lark-cli --as bot im +messages-send \
     --chat-id oc_xxx --msg-type interactive --content - \
     --idempotency-key "reset-push-$(date +%Y%m%d-%H)"
   （bot 需在目标群内；install.sh 的 RESET_CHAT_ID 模式会自动组装这条管道）
2. 飞书自定义机器人 webhook（内置发送，免 CLI，支持免服务器部署）：
   FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" \
   [FEISHU_WEBHOOK_SECRET="xxx"] python3 push_reset.py
   URL 经域名白名单 + DNS 解析结果校验（阻断私网/环回/链路本地地址，防贴错或 DNS rebinding）。

幂等：同一触发时段（YYYYMMDD-HH）重跑不重发。
lark-cli 管道由 --idempotency-key 服务端去重；webhook 通道用本地 .push_state.json 记录。
用法：python3 push_reset.py [--dry-run | --print-card]
"""
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

BJT = timezone(timedelta(hours=8))
HINT = "历史高发时段（45 条实测）：北京上午 8-12 点、午后 15 点前，凌晨有夜袭"
STATE_FILE = Path(__file__).resolve().parent / ".push_state.json"
WEBHOOK_HOSTS = ("open.feishu.cn", "open.larksuite.com")
DATA_API = "https://aihot.news/api/v1/codex-resets"


def fetch_latest():
    """取 codex-resets 最新事件（events[0]，新→旧排序）。目标 URL 为本文件常量。

    全量端点每客户端 10 分钟一次（超出返回 429+retryAfter），班距务必留足间隔。
    """
    try:
        req = urllib.request.Request(
            DATA_API, headers={"User-Agent": "codex-reset-notification/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return (json.loads(resp.read().decode("utf-8")).get("events") or [None])[0]
    except Exception:  # noqa: BLE001
        return None


def validate_webhook_url(url):
    """域名白名单 + 解析结果校验：仅允许官方 webhook 域名的 https 地址，
    且域名解析出的 IP 不得为私网/环回/链路本地/保留地址（防贴错地址与 DNS rebinding）。"""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme != "https" or parts.hostname not in WEBHOOK_HOSTS:
        return False
    try:
        infos = socket.getaddrinfo(parts.hostname, 443,
                                   socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


def build_card(ev):
    if not ev:
        return {"config": {"wide_screen_mode": True},
                "header": {"template": "blue", "title": {
                    "tag": "plain_text", "content": "🕐 Codex 额度情报"}},
                "elements": [{"tag": "div", "text": {"tag": "lark_md",
                             "content": "接口暂不可达，稍后自动恢复。"}}]}
    url = ev.get("url") or "https://aihot.news/codex-reset"
    title = (ev.get("title") or "").strip()
    est = ev.get("estimate") or {}
    if ev.get("status") == "announced":
        window = ""
        try:
            frm = datetime.fromisoformat(est.get("from")).astimezone(BJT)
            thru = datetime.fromisoformat(est.get("through")).astimezone(BJT)
            window = f"\n\n**预计 {frm:%m-%d %H:%M} ~ {thru:%m-%d %H:%M}**（北京时间）"
        except (TypeError, ValueError):
            pass
        return {
            "config": {"wide_screen_mode": True},
            "header": {"template": "red", "title": {
                "tag": "plain_text", "content": "📢 义父预告：Codex 额度将重置"}},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md",
                 "content": f"**{title}**{window}\n\n{HINT}"}},
                {"tag": "hr"},
                {"tag": "action", "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "📍 蹲住日历"},
                     "type": "danger", "url": url}]},
                {"tag": "note", "elements": [{"tag": "plain_text",
                 "content": "来源 aihot.news/codex-reset（非官方）"}]},
            ]}
    when = ""
    for k in ("occurredOn", "confirmedAt", "updatedAt"):
        v = ev.get(k)
        if v:
            try:
                when = f"（{datetime.fromisoformat(str(v)).astimezone(BJT):%m-%d %H:%M}）"
            except ValueError:
                when = f"（{str(v)[:10]}）"
            break
    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": "blue", "title": {
            "tag": "plain_text", "content": "🕐 Codex 额度情报：暂无新预告"}},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md",
             "content": f"**上次动作：{title}**{when}\n\n{HINT}"}},
            {"tag": "hr"},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "查看日历"},
                 "type": "default", "url": url}]},
            {"tag": "note", "elements": [{"tag": "plain_text",
             "content": "来源 aihot.news/codex-reset（非官方）"}]},
        ]
    }


def gen_sign(timestamp, secret):
    """飞书自定义机器人签名校验（官方算法）：
    key = timestamp + "\\n" + 密钥，对空字符串做 HMAC-SHA256，结果 Base64。"""
    string_to_sign = "{}\n{}".format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"),
                         digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def send_webhook(card, url):
    """走飞书自定义机器人 webhook 发卡片；url 必须是 main() 校验通过的 https 地址。"""
    payload = {"msg_type": "interactive", "card": card}
    secret = os.environ.get("FEISHU_WEBHOOK_SECRET")
    if secret:
        ts = str(int(datetime.now(BJT).timestamp()))
        payload["timestamp"] = ts
        payload["sign"] = gen_sign(ts, secret)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.stderr.write(e.read().decode("utf-8", "replace")[-1500:])
        return False
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"webhook 发送失败: {e}\n")
        return False
    if body.get("code") == 0 or body.get("StatusCode") == 0:
        return True
    sys.stderr.write(json.dumps(body, ensure_ascii=False)[:1500])
    return False


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save_state(st):
    try:
        STATE_FILE.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        sys.stderr.write(f"warn: 写状态文件失败 {e}\n")


def main():
    dry = ("--dry-run" in sys.argv) or ("--print-card" in sys.argv)
    url = os.environ.get("FEISHU_WEBHOOK_URL")
    if url and not validate_webhook_url(url):
        sys.stderr.write(
            "FEISHU_WEBHOOK_URL 校验未通过：必须是 https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
            "（或 open.larksuite.com），且域名解析不到内网地址\n")
        return 2
    if not dry and not url:
        sys.stderr.write(
            "缺少发送通道（自选其一）：\n"
            "  1) lark-cli 管道：python3 push_reset.py --print-card | lark-cli --as bot im +messages-send "
            "--chat-id oc_xxx --msg-type interactive --content - --idempotency-key \"reset-push-$(date +%Y%m%d-%H)\"\n"
            "     （定时任务用 RESET_CHAT_ID=oc_xxx bash install.sh 一键安装；lark-cli 见 https://github.com/larksuite/cli）\n"
            "  2) webhook 内置发送：export FEISHU_WEBHOOK_URL="
            "https://open.feishu.cn/open-apis/bot/v2/hook/xxx（飞书群自定义机器人）\n")
        return 2
    now = datetime.now(BJT)
    card = build_card(fetch_latest())
    if dry:
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return 0
    key = f"reset-push-{now:%Y%m%d}-{'%02d' % now.hour}"
    if load_state().get("last_key") == key:
        print(f"SKIP reset-push {now:%Y-%m-%d %H:%M}（本时段已发过）")
        return 0
    if not send_webhook(card, url):
        print(f"FAIL reset-push {now:%Y-%m-%d %H:%M}")
        return 1
    save_state({"last_key": key})
    print(f"OK reset-push {now:%Y-%m-%d %H:%M}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
