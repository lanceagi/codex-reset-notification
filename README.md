<div align="center">

# 义父情报卡

**Codex 额度要重置了? 义父的预告, 第一时间推到你的飞书群**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python 3.6+](https://img.shields.io/badge/python-3.6%2B-blue.svg)
![dependencies](https://img.shields.io/badge/dependencies-0-success.svg)
[![godfather](https://img.shields.io/badge/%E4%B9%89%E7%88%B6-approved-red.svg)](#-彩蛋为什么叫义父)

收到的卡片长这样:

```
🔴 红卡 · 义父预告(有新预告时)
     10 月额度重置
     预计 10-16 08:00 ~ 10-16 15:00(北京时间)
     历史高发时段(45 条实测): 北京上午 8-12 点, 午后 15 点前, 凌晨有夜袭
     [📍 蹲住日历]

🔵 蓝卡 · 上次动作(每班一张心跳卡)
     上次动作: Tibo 确认重置(10-15 12:55)
     [查看日历]
```

<details>
<summary>English TL;DR</summary>

Push Codex quota-reset announcements (from the unofficial [aihot.news](https://aihot.news/codex-reset) aggregator) to your Feishu/Lark group as red "godfather forecast" / blue "last action" cards. The skill's core job is fetching reset intel and building the card; delivery is pluggable — pipe to the official [lark-cli](https://github.com/larksuite/cli), or use the built-in custom-bot webhook (works serverless via GitHub Actions). Zero Python dependencies. Non-commercial use only; MIT covers code, not the data source.

</details>

</div>

> ⚠️ **非官方工具**: 数据来自 [aihot.news](https://aihot.news/codex-reset), 仅限非商业使用 — 部署前请先读[使用边界](#usage-boundary).

## 📑 目录

- [✨ 特性](#-特性)
- [🚀 快速开始](#-快速开始)
  - [路径一: lark-cli 用户(推荐)](#路径一lark-cli-用户推荐)
  - [路径二: 免服务器 · GitHub Actions + webhook](#路径二免服务器--github-actions--webhook)
  - [路径三: 本机 cron · webhook](#路径三本机-cron--webhook)
  - [手动单发一条](#手动单发一条)
- [🥚 彩蛋: 为什么叫"义父"](#-彩蛋为什么叫义父)
- [📊 义父什么时候发额度? (45 条实测)](#-义父什么时候发额度45-条实测)
- [⚙️ 配置](#️-配置)
- [⚠️ 使用边界(先读)](#usage-boundary)
- [📁 目录结构](#-目录结构)
- [❓ FAQ](#-faq)
- [🗺 Roadmap](#-roadmap)
- [🤝 贡献](#-贡献)
- [📄 License](#-license)

## ✨ 特性

- 🤖 **skill 本职清晰**: 跑通"获取重置情报 → 生成卡片", 投递方式你自己挑
- 🚀 **一键部署**: `lark-cli`(飞书官方开源 CLI)一条管道直推; 或 30 秒 webhook 免服务器
- 📦 **零 Python 依赖**: 纯标准库, 没有 `pip install`
- 🔴 **义父预告红卡**: 新预告带预计时间窗口 + 45 条实测高发时段提示
- 🔵 **心跳蓝卡**: 每班播报上次动作, 挂了立刻能发现
- 🚫 **不碰账号**: 不读取你的 OpenAI 凭据, 数据全部来自 aihot.news 公开接口
- 🔁 **幂等**: 同一时段重跑不重发; webhook 地址做了域名白名单 + 解析校验

## 🚀 快速开始

skill 的本职是**跑通"获取重置情报"**: 拉 aihot 数据 → 判断预告/心跳 → 生成飞书卡片. 接收渠道随你定, 三条路径按人群取用.

### 路径一: lark-cli 用户(推荐)

适合在用 AI Agent(ZCode / Claude Code 等)或已装 [lark-cli](https://github.com/larksuite/cli)(飞书官方开源 CLI)的人 — 装一次全局可用, 不用为每个群建机器人.

```bash
# 1. 安装 lark-cli(一次性; 需 Node.js)
npx @larksuite/cli@latest install
lark-cli auth login        # 按提示完成配置与授权, 详见 lark-cli README

# 2. 部署 skill: 把本仓库放进 agent 技能目录(ZCode/Claude Code 约定路径)
#    ~/.agents/skills/codex-reset-notification/
#    此后对 agent 说"推送义父情报卡 / 看重置时间统计"即可, SKILL.md 是它的运维手册

# 3. 一键装上定时推送(把 bot 先拉进目标群, oc_xxx 换成群 ID)
RESET_CHAT_ID=oc_xxx bash scripts/install.sh

# 4. 手动预览一张卡
python3 scripts/push_reset.py --print-card
```

install.sh 装进 crontab 的定时任务是这条管道(默认北京时间 05:07/08:07/10:07/12:07/17:07, 分钟位错开整点防飞书限流):

```bash
python3 push_reset.py --print-card | lark-cli --as bot im +messages-send \
  --chat-id oc_xxx --msg-type interactive --content - \
  --idempotency-key "reset-push-$(date +%Y%m%d-%H)"
```

### 路径二: 免服务器 · GitHub Actions + webhook

不想装任何东西: fork 仓库 + 填一个 secret. 先在飞书群 → 设置 → 群机器人 → 添加"自定义机器人"→ 复制 Webhook 地址(形如 `https://open.feishu.cn/open-apis/bot/v2/hook/xxxx`).

1. Fork 本仓库
2. Settings → Secrets and variables → Actions → New repository secret: `FEISHU_WEBHOOK_URL`(必填), `FEISHU_WEBHOOK_SECRET`(选填, 机器人开了签名校验才需要)
3. Actions 页启用"义父情报卡定时推送", Run workflow 手动跑一次 — 群里收到蓝卡即部署成功

推送时间同路径一. 仓库 60 天无提交时 GitHub 会暂停定时任务, 回来 Enable 一次即可.

### 路径三: 本机 cron · webhook

不想用 lark-cli 的本机用户:

```bash
git clone https://github.com/lanceagi/codex-reset-notification.git
cd codex-reset-notification
python3 scripts/push_reset.py --print-card      # 先看卡片样式
FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" \
  bash scripts/install.sh                       # 一键装 crontab(幂等, 可卸载)
```

### 手动单发一条

**lark-cli 管道**(卡片 JSON 出 stdout, `--content -` 从 stdin 读入):

```bash
python3 scripts/push_reset.py --print-card | lark-cli --as bot im +messages-send \
  --chat-id oc_xxx --msg-type interactive --content - \
  --idempotency-key "reset-push-$(date +%Y%m%d-%H)"
```

**webhook 内置发送**:

```bash
FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" \
  python3 scripts/push_reset.py
```

## 🥚 彩蛋: 为什么叫"义父"

社区黑话: Codex 的额度什么时候重置, 什么时候发卡, 全看官方安排 — 大家半开玩笑地尊称那位"掌管额度生死"的官方为**义父**. 额度是义父给的, 预告是义父发的, 做子女的自然要第一时间知道义父的动向, 所以红卡题头就叫"义父预告".

纯属社区玩梗, 与 OpenAI, aihot.news 及任何真实人物无关 🙏

## 📊 义父什么时候发额度? (45 条实测)

基于 2026-06-17 ~ 10-13 的 45 条重置事件(数据来自 aihot.news, 用 `scripts/analyze.py` 可在自己的快照上重跑):

- **高发时段**: 北京上午 8-12 点, 午后 15 点前; 凌晨有夜袭(00-05 点 10 条)
- **预告提前量**: 中位数 6.7 小时(n=26, 最短 6 分钟, 最长 86 小时)
- **36% 的重置没有预告直接执行** — 事前通知的理论天花板是 64%
- **推送班次 vs 事前率**: 三班(08/10/17)77% → 五班(05/08/10/12/17)88% → 每小时 96%(边际 +8% 要换每天 24 张蓝卡, 默认取五班的平衡点)

## ⚙️ 配置

| 变量 / 参数 | 用途 | 默认 |
|---|---|---|
| `RESET_CHAT_ID`(install.sh) | lark-cli 管道通道的目标群 ID | 无 |
| `FEISHU_WEBHOOK_URL` | webhook 内置发送(唯一必需配置, webhook 模式) | 无 |
| `FEISHU_WEBHOOK_SECRET` | 机器人开启"签名校验"时填写 | 无 |
| `--print-card` / `--dry-run` | 拉数据输出卡片 JSON, 不发送(管道/预览用) | — |
| `RESET_HOURS`(install.sh) | 推送班次(小时, 逗号分隔) | `5,8,10,12,17` |
| `RESET_MINUTE`(install.sh) | cron 分钟位(错开整点防飞书限流) | `7` |
| `HINT` 常量(push_reset.py) | 卡片里的高发时段提示语 | 45 条口径 |

改卡片样式: 编辑 `push_reset.py` 的 `build_card()`(飞书卡片 1.0 结构).

## ⚠️ 使用边界(先读)

- 本项目是**非官方**第三方工具, 数据来自 aihot.news, 条款见 <https://aihot.news/terms>
- **MIT 许可只覆盖本仓库代码, 不覆盖 aihot.news 的数据与品牌**
- **禁止把数据快照提交进仓库**(`.gitignore` 已排除 `codex-resets-raw-*.json`, `events-detail.json`)
- 商业使用 AIHOT 数据需书面授权: wzglyay@virxact.com(见其 ToS)
- 全量端点限流**每客户端 10 分钟一次**; 自建调度班距务必 ≥ 该间隔(默认班次最短 2 小时, 安全)

## 📁 目录结构

```
├── SKILL.md                        # 运维手册(agent 部署后它就是说明书): 数据源/限流/时间口径/坑
├── scripts/
│   ├── push_reset.py               # 获取情报+生成卡片+webhook 发送(零依赖)
│   ├── analyze.py                  # 快照统计 + 班次模拟(零依赖)
│   └── install.sh                  # crontab 一键安装(lark-cli 管道 / webhook 双模式)
├── .github/workflows/notify.yml    # GitHub Actions 免服务器定时推送(webhook)
├── LICENSE                         # MIT(仅代码)
└── README.md
```

## ❓ FAQ

**lark-cli 是什么? **
飞书(Lark)官方开源的命令行工具, 封装 2500+ 飞书 API, 专为人类终端和 AI Agent 设计: [github.com/larksuite/cli](https://github.com/larksuite/cli). 安装: `npx @larksuite/cli@latest install`, 然后 `lark-cli auth login` 完成授权; bot 身份发送需先把 bot 拉进目标群.

**怎么拿到 Webhook 地址? **
飞书群 → 设置 → 群机器人 → 添加"自定义机器人"→ 复制 Webhook. 地址必须以 `https://open.feishu.cn/open-apis/bot/v2/hook/` 开头, 脚本会校验.

**会碰我的 OpenAI 账号吗? **
不会. 数据全部来自 aihot.news 公开接口, 本项目唯一的凭据是你自己的飞书 webhook / lark-cli 授权(只存在于你的环境里, 仓库里没有任何密钥).

**收不到卡片 / Actions 跑红了? **
先本地 `python3 scripts/push_reset.py --print-card` 看数据源通不通; lark-cli 管道看 lark-cli 报错(bot 在不在群里); webhook 模式带环境变量手跑看 stderr. GitHub 免费版定时任务可能延迟几分钟 — 对小时级的重置窗口没有影响.

**蓝卡太吵? **
`install.sh` 传 `RESET_HOURS="10,17"` 减班次; "无预告不发蓝卡"的 `--quiet` 见 Roadmap.

**想推钉钉 / 企业微信? **
卡片 JSON 已经在 stdout 了(`--print-card`), 接你自己的发送命令即可, 欢迎 PR.

**数据多久更新一次? **
以 aihot.news 为准; 全量端点每客户端 10 分钟限流一次, 别自行加高频轮询.

## 🗺 Roadmap

- [ ] 卡片真实截图 / 演示 GIF
- [ ] `push_reset.py --quiet`: 无预告时不发蓝卡
- [ ] 事件级红卡去重(每个预告只提醒一次)
- [ ] 完整英文 README

## 🤝 贡献

欢迎 Issue / PR: fork → 建分支 → 改动 → 提 PR. 跑一遍 `python3 scripts/push_reset.py --print-card` 确认不报错即可. 统计数据类 PR 请附 `analyze.py` 的输出与快照口径说明(**快照文件本身不要提交**).

## 📄 License

[MIT](LICENSE). 仅覆盖本仓库代码; aihot.news 的数据与品牌不在 MIT 范围内, 商用需其书面授权.
