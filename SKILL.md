---
name: codex-reset-notification
version: 1.0.0
description: 义父情报卡（Codex 额度重置通知）：push_reset.py 定时查询 aihot codex-resets 数据源并生成飞书卡片（红=义父预告/蓝=上次动作），投递双通道——lark-cli 管道（官方开源 CLI，--print-card 出 JSON 由调用方发送）或内置飞书自定义机器人 webhook（零依赖）；analyze.py 对历史事件快照做重置时间统计与推送班次模拟。含数据源端点/字段语义/限流、时间口径坑、幂等设计与 45 条实测统计结论。用户提到"义父情报卡/义父预告/额度重置通知/充值时间/重置卡/push_reset/重置时间统计/推送排查"时使用。
---

# codex-reset-notification（义父情报卡 · Codex 额度重置通知）

aihot codex-resets API → `scripts/push_reset.py`（cron 触发）→ 飞书卡片：

- 最新事件 `status=announced` → 红「义父预告」卡（预计窗口 + 历史高发时段提示）
- 其他 → 蓝「上次动作」卡（occurredOn/confirmedAt/updatedAt 首个可用时刻）
- API 不可达 → 蓝「接口暂不可达」卡

**职责边界**：skill 本职=跑通「获取重置情报 → 生成卡片」；投递方式由调用方选：

1. **lark-cli 管道**（推荐）：`push_reset.py --print-card` 输出卡片 JSON，`lark-cli --as bot im +messages-send --content -` 从 stdin 收（lark-cli 为飞书官方开源 CLI，https://github.com/larksuite/cli）；幂等靠 lark-cli 服务端 `--idempotency-key`
2. **webhook 内置发送**：`FEISHU_WEBHOOK_URL`（+可选 `FEISHU_WEBHOOK_SECRET`）环境变量直接发；幂等靠本地 `.push_state.json`

旁线：`scripts/analyze.py` 对事件快照做时间统计 + 推送班次模拟，回答"一天推几班、几点推，事前通知率最高"。

本仓库为开源线，与作者私有部署版并存、互不回写；改行为=改脚本+升 frontmatter 版本号。

## 一、脚本与参数

| 脚本 | 职责 | 用法 |
|---|---|---|
| `scripts/push_reset.py` | 查 events[0] 生成卡片（见上）；webhook 模式内置发送 | `python3 scripts/push_reset.py --print-card`（输出卡片 JSON，不发送）；webhook 发送：`FEISHU_WEBHOOK_URL=... python3 scripts/push_reset.py` |
| `scripts/analyze.py` | 快照统计 + 班次模拟 | `python3 scripts/analyze.py <快照.json>`；明细落快照同目录 `events-detail.json` |
| `scripts/install.sh` | 本机 crontab 一键安装，双模式（幂等，行尾标记 `# codex-reset-notification`） | `RESET_CHAT_ID=oc_xxx bash scripts/install.sh`（lark-cli 管道）或 `FEISHU_WEBHOOK_URL=... bash scripts/install.sh`（webhook）；`RESET_HOURS` / `RESET_MINUTE` 可调班次 |

- **lark-cli 管道标准形**：
  `python3 push_reset.py --print-card | lark-cli --as bot im +messages-send --chat-id oc_xxx --msg-type interactive --content - --idempotency-key "reset-push-$(date +%Y%m%d-%H)"`
  bot 需在目标群内；chat-id 必须是 `oc_` 开头的十六进制群 ID（install.sh 会校验）
- **URL 校验**（webhook）：地址必须是 `open.feishu.cn` / `open.larksuite.com` 的 https 前缀，且 DNS 解析结果不含私网/环回/链路本地地址（防贴错与 DNS rebinding）
- **签名**（webhook）：机器人开启签名校验时按飞书官方算法（key=timestamp+"\n"+secret，对空串 HMAC-SHA256 后 Base64）自动附带 timestamp+sign
- **限流**：飞书 webhook 单机器人 100 次/分钟、5 次/秒，整点/半点易触发限流——cron 分钟位取 7 错峰；aihot 全量端点每客户端 10 分钟一次，班距 ≥ 1 小时即安全

## 二、部署形态（按人群三选一）

1. **agent / lark-cli 用户（推荐）**：`npx @larksuite/cli@latest install` + `lark-cli auth login` → 仓库放进 `~/.agents/skills/` → `RESET_CHAT_ID=oc_xxx bash scripts/install.sh`；此后 agent 按 SKILL.md 接管运维（推送/统计/排查）
2. **GitHub Actions 免服务器**：`.github/workflows/notify.yml`，secrets 配 `FEISHU_WEBHOOK_URL`（+可选 `FEISHU_WEBHOOK_SECRET`）；UTC cron `7 21,0,2,4,9 * * *` = 北京 05/08/10/12/17 点 :07。注意仓库 60 天无提交 GitHub 暂停计划任务
3. **本机 cron + webhook**：`install.sh` 写入 `7 5,8,10,12,17 * * *`（默认班次）

## 三、数据源（aihot codex-resets）

- 端点：`https://aihot.news/api/v1/codex-resets`（全量历史）；`/api/v1/codex-resets/recent`（最近变更，不撞全量限流）
- 头部有 schemaVersion/timezone/today/checkedAt；`events[]` 新→旧排序，`events[0]`=最新
- 事件字段：`id/type(direct_reset=全员重置, reset_credit=重置卡发放)/status(announced=预告中, confirmed=已确认)/title/displayLabel/createdAt/updatedAt/confirmedAt/occurredOn/estimate(from~through 预告窗口)/schedule(precision/from/through/label)/posts[]`（每帖 id/publishedAt/stage=预告|确认完成/text/url）
- **限流（2026-10-14 实测）**：全量端点**每客户端 10 分钟一次**，超出返回 429+retryAfter(秒)，按值等待后重拉即可
- 时间原生 +08:00（北京时间），无需转换
- 本项目为非官方第三方工具，数据源条款见 https://aihot.news/terms

## 四、时间口径与统计结论（45 条实测，2026-06-17~10-13）

**时间口径**：confirmedAt/occurredOn=站方**确认收录时刻，非重置执行瞬间**（执行通常更早 0-数小时）；重置"发生时刻"只能用窗口逼近：预告窗口（schedule/estimate from~through）是官方承诺，deadline=through。

**重置发生时刻分布（45 条）**：

- 官方窗口截止时刻：15 点最大峰（×8），其次 10 点（×5）、02/06 点（×3）
- 站方确认时刻：峰 08/11/12 点；夜袭（00-05 点）10 条
- 预告提前量（deadline−首预告帖，n=26）：min 0.1h / p50 6.7h / max 86.2h
- **36%（16/45）官方无预告直接执行（偷袭型）——事前通知理论天花板 64%**

**推送班次研究**（判定口径=首个可见班次 q1 < deadline 为事前）：

| 班次（小时） | 事前率（有预告可判定事件） |
|---|---|
| 08/10/17 | 20/26（77%） |
| 08/10/12/17 | 21/26（81%） |
| **05/08/10/12/17** | **23/26（88%）** |
| 每小时 | 25/26（96%），余 1 条=3 分钟窗口物理不可覆盖 |

- 错过型共性：凌晨 00:47-04:43 出预告+窗口仅 1-3 小时，早 8 点班前已截止
- 不推荐每小时轮询：需防蓝卡刷屏+事件级去重，边际仅 +2 条历史场景；且班距必须 ≥ 全量端点限流间隔（10 分钟/客户端），留足冗余

更新统计：等限流窗口过后重拉全量快照（**快照不入库提交**）→ `python3 scripts/analyze.py <快照>` → 对照本节口径写新报告。

## 五、坑与经验（全部实测）

1. 全量端点 10 分钟限流：429 带 retryAfter，按值 sleep 后重拉；连续分析场景先落盘再统计
2. 蓝卡是心跳：每班必发（含"暂无新预告"），班次越密蓝卡越多，嫌吵可加 `--quiet`（无预告不发，尚未实现）
3. push_reset 只看 events[0]：一天内多个事件时旧的会被跳过（重置事件间隔通常 ≥2 天，未观测到问题）
4. lark-cli 管道模式：`--content -` 从 stdin 读卡片 JSON；发送身份 `--as bot` 需 bot 已入群，鉴权问题见 lark-cli README
5. 飞书 webhook 整点/半点易限流（错误码 11232），cron 分钟位错峰（默认 :07）；单机器人 100 次/分钟、5 次/秒，请求体 ≤ 20KB
6. API 不可达=限流或网络，等 10 分钟再试

## 六、常见任务

- 预览卡片：`python3 scripts/push_reset.py --print-card`
- 手动单发：lark-cli 管道标准形（见第一节）；webhook 模式带环境变量直跑
- 排查失败：先 `--print-card` 看数据源；lark-cli 报错查 bot 在不在群；webhook 模式看 stderr；Actions 跑红先查 secret
- 改班次：重跑 `install.sh` 带 `RESET_HOURS`；Actions 改 `notify.yml` 的 cron（UTC=北京−8）
- 改推送样式：`push_reset.py` 的 `build_card()`（飞书卡片 1.0：header template 红/蓝，elements div·hr·action·note）；`HINT` 常量=高发时段提示语（口径见第四节）
- 更新统计：见第四节重跑流程

## 七、License 与使用边界

- 代码以 MIT 发布；**MIT 只覆盖代码，不覆盖 aihot.news 的数据与品牌**
- 数据快照（codex-resets-raw-*.json、events-detail.json）不入库（`.gitignore` 已排除）
- 商业使用 AIHOT 数据需书面授权（见其 ToS）
- 全量端点限流 10 分钟/客户端，自建调度务必留足班距

## 八、相关

- 数据源：aihot.news（非官方工具，条款 https://aihot.news/terms）
- 发送工具：lark-cli（飞书官方开源 CLI，https://github.com/larksuite/cli）
- 部署与彩蛋说明见 `README.md`
