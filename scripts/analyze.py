#!/usr/bin/env python3
"""Codex 额度重置/充值时间统计分析（对 aihot codex-resets 快照做统计+推送班次模拟）。

时间口径（详见 README/SKILL.md）：
- t_announce = 最早预告帖 publishedAt（posts 中 stage 含"预告"）；无预告帖 = 偷袭型，无法事前通知
- deadline   = schedule.through（预告窗口最晚时刻 = 官方"在此之前发生"）
- t_confirm  = confirmedAt（站方确认收录时刻，非重置执行瞬间，执行通常更早 0-数小时）
- 事前判定（窗口口径）：首个班次 q1 满足 q1 < deadline → 收到通知时官方窗口未截止 = 事前
- 事后判定（确认口径）：q1 > t_confirm → 确认都已收录 = 事后
- 之间 = GRAY（deadline 已过但未确认，实际可能已发生）

用法：python3 analyze.py <codex-resets 快照.json>
快照自取（全量端点每客户端 10 分钟一次，勿频繁拉取）：
  curl -H "User-Agent: codex-reset-notification/1.0" \
       https://aihot.news/api/v1/codex-resets -o codex-resets.json
明细结果落在快照同目录 events-detail.json（勿提交入库）。
"""
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

BJT = timezone(timedelta(hours=8))


def parse(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)).astimezone(BJT)
    except (TypeError, ValueError):
        return None


def next_slot(t, hours):
    """t 之后（含 t 当刻）第一个班次时刻。"""
    day = t.replace(hour=0, minute=0, second=0, microsecond=0)
    for delta in range(5):
        for h in sorted(hours):
            q = (day + timedelta(days=delta)).replace(hour=h, minute=0, second=0, microsecond=0)
            if q >= t:
                return q
    return None


def load_events(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    evs = d.get("events") or []
    if not evs:
        raise SystemExit(f"数据文件无事件: {path}")
    return evs


def event_fields(ev):
    """抽取每事件的判定字段。"""
    posts = ev.get("posts") or []
    ann = None
    for p in sorted(posts, key=lambda p: str(p.get("publishedAt") or "")):
        if "预告" in str(p.get("stage") or ""):
            t = parse(p.get("publishedAt"))
            if t and (ann is None or t < ann):
                ann = t
    sch = ev.get("schedule") or {}
    est = ev.get("estimate") or {}
    return {
        "id": ev.get("id"),
        "type": ev.get("type"),
        "status": ev.get("status"),
        "label": ev.get("displayLabel") or ev.get("label"),
        "t_announce": ann,
        "deadline": parse(sch.get("through") or est.get("through")),
        "win_from": parse(sch.get("from") or est.get("from")),
        "t_confirm": parse(ev.get("confirmedAt")),
    }


def verdict(f, hours):
    """模拟：预告可见后第一个班次落在哪个区间。"""
    if f["t_announce"] is None:
        return "NO-ANNOUNCE", None
    q1 = next_slot(f["t_announce"], hours)
    dl, cf = f["deadline"], f["t_confirm"]
    if dl is None:
        return "NO-WINDOW", q1
    if q1 < dl:
        return "BEFORE", q1  # 事前：窗口未截止
    if cf and q1 > cf:
        return "AFTER", q1  # 事后：确认已收录
    return "GRAY", q1  # deadline 过、确认未到


def main(path):
    evs = load_events(path)
    rows = [event_fields(e) for e in evs]

    print(f"== 全量 {len(rows)} 条（{rows[-1]['t_confirm'] or rows[-1]['t_announce']} ~ "
          f"{rows[0]['t_confirm'] or rows[0]['t_announce']}）==")
    print("type 分布:", dict(Counter(r["type"] for r in rows)))
    print("status 分布:", dict(Counter(r["status"] for r in rows)))

    # --- 重置发生时刻分布（充值时间统计）---
    for key, name in (("deadline", "预告窗口截止(官方deadline)"),
                      ("win_from", "预告窗口起点"),
                      ("t_confirm", "站方确认时刻")):
        hrs = Counter(r[key].hour for r in rows if r[key] is not None)
        print(f"\n{name} 小时分布(北京):",
              " ".join(f"{h:02d}点×{hrs[h]}" for h in sorted(hrs)))

    # --- 预告提前量 ---
    leads = [(r["deadline"] - r["t_announce"]) for r in rows
             if r["t_announce"] and r["deadline"]]
    if leads:
        leads_h = sorted(round(l.total_seconds() / 3600, 1) for l in leads)
        print(f"\n预告提前量 deadline-首预告帖 (n={len(leads)}): "
              f"min={leads_h[0]}h p50={leads_h[len(leads_h)//2]}h max={leads_h[-1]}h")

    # --- 调度模拟对比（班次小时集合可按需增删）---
    scheds = [
        ("三班 08/10/17", {8, 10, 17}),
        ("两班 10/17", {10, 17}),
        ("四班 00/08/10/17", {0, 8, 10, 17}),
        ("五班 00/08/12/17/21", {0, 8, 12, 17, 21}),
        ("每小时", set(range(24))),
    ]
    print("\n== 调度模拟（对有预告事件：首个可见班次 vs 窗口/确认）==")
    for name, hours in scheds:
        c = Counter(verdict(r, hours)[0] for r in rows)
        n = len(rows)
        withann = n - c.get("NO-ANNOUNCE", 0)
        ok = c.get("BEFORE", 0)
        print(f"{name}: 事前 {ok}/{withann} 有预告事件"
              f"（偷袭无预告 {c.get('NO-ANNOUNCE', 0)}，GRAY {c.get('GRAY', 0)}，"
              f"事后 {c.get('AFTER', 0)}，无窗口 {c.get('NO-WINDOW', 0)}）")

    # --- 明细表（基线班次 08/10/17）---
    def fmt(t):
        return f"{t:%m-%d %H:%M}" if t else "—"

    print("\n== 明细（基线 08/10/17 班次口径）==")
    print(f"{'#':>2}  {'日期':<10} {'类型':<12} {'首预告':<12} {'窗口截止':<12} "
          f"{'确认':<12} {'首班':<12} 判定")
    for i, r in enumerate(rows, 1):
        v, q1 = verdict(r, {8, 10, 17})
        d0 = r["t_announce"] or r["t_confirm"]
        print(f"{i:>2}  {d0.strftime('%m-%d'):<10} {str(r['label'])[:6]:<12} "
              f"{fmt(r['t_announce']):<12} {fmt(r['deadline']):<12} "
              f"{fmt(r['t_confirm']):<12} {fmt(q1):<12} {v}")

    # 落明细 JSON 供复核（快照同目录，勿提交入库）
    out = Path(path).resolve().parent / "events-detail.json"
    out.write_text(json.dumps([
        {**{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in r.items()},
         "verdict_current": verdict(r, {8, 10, 17})[0],
         "q1_current": (verdict(r, {8, 10, 17})[1] or datetime.now(BJT)).isoformat()}
        for r in rows], ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n明细已落 {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write("用法: python3 analyze.py <codex-resets 快照.json>\n")
        sys.exit(2)
    main(sys.argv[1])
