"""Render the actual mutable inputs into the release notes."""


def cell(value):
    return str(value or "未提供").replace("|", "\\|").replace("\n", " ")


def render(lock):
    lines = ["", "## 本次数据库记录", "", "上游时间与获取时间均按 UTC 记录；获取时间不代表数据库内容更新。",
             "", "| 文件 | 上游版本/提交 | 源更新时间 | 获取时间 | 来源模式 | SHA256（前12位） |",
             "|---|---|---|---|---|---|"]
    for item in lock["geodata"]:
        version = item.get("release") or item.get("source_commit", "")[:12] or "无独立版本号"
        updated = item.get("source_updated_at") or item.get("asset_updated_at")
        fetched = item.get("downloaded_at") if item.get("mode") == "fallback" else item.get("fetched_at")
        values = [item["file"], version, updated, fetched, item.get("mode", "online"), item["sha256"][:12]]
        lines.append("| " + " | ".join(map(cell, values)) + " |")
    if any(i.get("mode") == "fallback" for i in lock["geodata"]):
        lines += ["", "**本次使用仓库托底快照；在线数据未通过下载或固定核心加载检查。** 回退原因、原始来源和完整摘要见 build-lock.json。"]
    lines += ["", "完整来源地址、发布资产信息及 SHA256 见随固件保存的 build-lock.json。", ""]
    return "\n".join(lines)
