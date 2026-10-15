#!/usr/bin/env bash
# 义父情报卡一键安装（写入本机 crontab 定时推送）
#
# 发送通道二选一（按传入的环境变量自动选择）：
#   RESET_CHAT_ID=oc_xxx                 lark-cli 管道通道（飞书官方开源 CLI，
#                                        需先安装并完成 auth login）
#   FEISHU_WEBHOOK_URL=https://...       飞书自定义机器人 webhook 通道（零 CLI 依赖）
# 可选环境变量：
#   FEISHU_WEBHOOK_SECRET="xxx"          webhook 机器人开启"签名校验"时填写
#   RESET_HOURS="5,8,10,12,17"           推送班次（小时，逗号分隔）
#   RESET_MINUTE="7"                     分钟位。默认 7：避开整点，防飞书 webhook 整点限流
#
# 幂等：重复执行只保留一条定时任务（按行尾标记识别）。
# 卸载：crontab -l | grep -vF '# codex-reset-notification' | crontab -
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBHOOK="${FEISHU_WEBHOOK_URL:-}"
CHAT="${RESET_CHAT_ID:-}"
SECRET="${FEISHU_WEBHOOK_SECRET:-}"
HOURS="${RESET_HOURS:-5,8,10,12,17}"
MINUTE="${RESET_MINUTE:-7}"
MARKER="# codex-reset-notification"

command -v python3 >/dev/null 2>&1 || { echo "✗ 需要 python3"; exit 1; }

if [ -n "$CHAT" ] && [ -n "$WEBHOOK" ]; then
  echo "✗ RESET_CHAT_ID 与 FEISHU_WEBHOOK_URL 只能二选一"; exit 1
fi
if [ -z "$CHAT" ] && [ -z "$WEBHOOK" ]; then
  echo "✗ 需要发送通道（二选一）：RESET_CHAT_ID=oc_xxx（lark-cli 管道）或 FEISHU_WEBHOOK_URL=https://...（webhook）"
  echo "  lark-cli（飞书官方开源 CLI）安装：npx @larksuite/cli@latest install，见 https://github.com/larksuite/cli"
  exit 1
fi

if [ -n "$CHAT" ]; then
  if [[ ! "$CHAT" =~ ^oc_[0-9a-f]{8,}$ ]]; then
    echo "✗ RESET_CHAT_ID 格式不对（应形如 oc_ 开头的十六进制群 ID）"; exit 1
  fi
  command -v lark-cli >/dev/null 2>&1 \
    || { echo "✗ lark-cli 未安装：npx @larksuite/cli@latest install（https://github.com/larksuite/cli）"; exit 1; }
  SEND_CMD="python3 push_reset.py --print-card 2>>push_reset.log | lark-cli --as bot im +messages-send --chat-id $CHAT --msg-type interactive --content - --idempotency-key \"reset-push-\$(date +\%Y\%m\%d-\%H)\""
else
  case "$WEBHOOK" in
    https://open.feishu.cn/open-apis/bot/v2/hook/*|https://open.larksuite.com/open-apis/bot/v2/hook/*) ;;
    *) echo "✗ FEISHU_WEBHOOK_URL 应形如 https://open.feishu.cn/open-apis/bot/v2/hook/xxx"; exit 1 ;;
  esac
  SEND_CMD="FEISHU_WEBHOOK_URL='$WEBHOOK' FEISHU_WEBHOOK_SECRET='$SECRET' python3 push_reset.py"
fi

echo "== 1/3 试跑 --print-card（拉一次数据验证连通，不发送）=="
python3 "$SCRIPT_DIR/push_reset.py" --print-card >/dev/null \
  || { echo "✗ 数据源不可达，检查网络后重试"; exit 1; }
echo "   OK"

echo "== 2/3 写入 crontab（北京 $HOURS 点每班推送，分钟位 $MINUTE）=="
CRON_LINE="$MINUTE $HOURS * * * cd '$SCRIPT_DIR' && $SEND_CMD >> push_reset.log 2>&1 $MARKER"
PREV="$(crontab -l 2>/dev/null | grep -vF "$MARKER" || true)"
{ if [ -n "$PREV" ]; then printf '%s\n' "$PREV"; fi
  printf '%s\n' "$CRON_LINE"; } | crontab -
crontab -l | grep -F "$MARKER" >/dev/null || { echo "✗ crontab 写入失败"; exit 1; }

echo "== 3/3 完成 =="
echo "   · 日志：$SCRIPT_DIR/push_reset.log"
echo "   · 手动单发一条：见 README「手动单发一条」"
echo "   · 卸载：crontab -l | grep -vF '$MARKER' | crontab -"
