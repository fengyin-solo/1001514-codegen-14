"""巡检任务业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "inspection"
REQUIRED_FIELDS = ["巡检单号", "巡检站点", "巡检人员"]
STATUS_ORDER = ["待派发", "巡检中", "已提交", "已作废"]
ACTION_RULES = {"派发巡检": "巡检中", "提交结果": "已提交", "作废巡检": "已作废"}
NEGATIVE_ACTIONS = ["作废巡检"]


def _text(value: Any) -> str:
    """转成去空白的字符串；None 视为空，数字 0 是有效值不能丢。"""
    if value is None:
        return ""
    return str(value).strip()


def _parse_issues(value: Any) -> int | None:
    """发现问题数只认非负整数；空值或非数字都视为未有效填写，返回 None。"""
    text = _text(value)
    if not text:
        return None
    try:
        number = int(text)
    except ValueError:
        return None
    return number if number >= 0 else None


class InspectionService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        station: str | None = None,
        person: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("巡检单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if station:
            rows = [row for row in rows if _text(row.get("巡检站点")) == station.strip()]
        if person:
            rows = [row for row in rows if _text(row.get("巡检人员")) == person.strip()]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["巡检状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"巡检单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于巡检任务可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["巡检状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"巡检单已{action}"

    def distribution(self, *, station: str | None = None) -> dict[str, Any]:
        """巡检问题分布：按站点、按人员汇总发现问题数，并给出本月发现总量。

        巡检人员或发现问题数未有效填写的巡检单不进入问题数与人员分布，
        逐条说明缺的是哪一项；站点条数仍统计范围内全部巡检单，
        与列表页在同一站点范围下的条数保持一致。
        """
        rows = store.rows(MODULE)
        stations = sorted({_text(row.get("巡检站点")) for row in rows if _text(row.get("巡检站点"))})
        scope = _text(station)
        scoped = [row for row in rows if not scope or _text(row.get("巡检站点")) == scope]

        month = date.today().strftime("%Y-%m")
        by_station: dict[str, dict[str, Any]] = {}
        by_person: dict[str, dict[str, Any]] = {}
        excluded: list[dict[str, Any]] = []
        month_total = 0
        total_issues = 0

        for row in scoped:
            station_name = _text(row.get("巡检站点")) or "未填站点"
            station_bucket = by_station.setdefault(
                station_name, {"station": station_name, "orders": 0, "issues": 0}
            )
            station_bucket["orders"] += 1

            missing: list[str] = []
            person = _text(row.get("巡检人员"))
            if not person:
                missing.append("巡检人员未填")
            issues = _parse_issues(row.get("发现问题数"))
            if issues is None:
                missing.append("发现问题数未填" if not _text(row.get("发现问题数")) else "发现问题数不是有效数字")
            if missing:
                excluded.append({
                    "id": row.get("id"),
                    "order_no": _text(row.get("巡检单号")) or f"巡检单{row.get('id')}",
                    "station": station_name,
                    "missing": missing,
                })
                continue

            station_bucket["issues"] += issues
            total_issues += issues
            person_bucket = by_person.setdefault(person, {"person": person, "orders": 0, "issues": 0})
            person_bucket["orders"] += 1
            person_bucket["issues"] += issues
            if str(row.get("巡检日期") or "").startswith(month):
                month_total += issues

        status_counts = {status: 0 for status in STATUS_ORDER}
        for row in scoped:
            status = str(row.get("status") or "")
            if status in status_counts:
                status_counts[status] += 1

        if not scoped:
            message = (
                f"站点范围「{scope}」内还没有巡检记录，可切换其它站点范围"
                if scope else "还没有巡检记录，可先登记巡检单"
            )
        elif not by_person:
            message = "当前站点范围内的巡检单都未进入分布，缺失项见下方说明"
        else:
            message = ""

        return {
            "month": month,
            "scope_station": scope,
            "stations": stations,
            "month_total": month_total,
            "total_issues": total_issues,
            "by_station": sorted(by_station.values(), key=lambda item: (-item["issues"], item["station"])),
            "by_person": sorted(by_person.values(), key=lambda item: (-item["issues"], item["person"])),
            "excluded": excluded,
            "status_counts": status_counts,
            "message": message,
        }
