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
# 分布视图依赖这两个字段，缺了就不计入分布，并在结果里说明是哪一项没填
DISTRIBUTION_FIELDS = ["巡检人员", "发现问题数"]


def parse_problem_count(value: Any) -> int | None:
    """把发现问题数解析成非负整数；空值或无法辨认的内容一律视为未填。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value.is_integer() and value >= 0 else None
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    return None


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
            rows = [row for row in rows if station in str(row.get("巡检站点", ""))]
        if person:
            rows = [row for row in rows if person in str(row.get("巡检人员", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def distribution(self, *, station: str | None = None) -> dict[str, Any]:
        """巡检问题分布：按站点、按人员汇总发现问题数，并给出本月发现总量。

        巡检人员或发现问题数没填的记录不进分布，单独列在 excluded 里说明缺哪一项；
        切换站点范围后没有可统计的记录时，用 empty_reason 说明原因。
        """
        all_rows = store.rows(MODULE)
        stations = sorted({str(row.get("巡检站点") or "").strip() for row in all_rows} - {""})
        rows = all_rows
        if station:
            rows = [row for row in rows if str(row.get("巡检站点") or "").strip() == station]

        month = date.today().strftime("%Y-%m")
        valid: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        for row in rows:
            missing = []
            person = str(row.get("巡检人员") or "").strip()
            if not person:
                missing.append("巡检人员")
            problem_count = parse_problem_count(row.get("发现问题数"))
            if problem_count is None:
                missing.append("发现问题数")
            if missing:
                excluded.append({
                    "id": row.get("id"),
                    "巡检单号": row.get("巡检单号"),
                    "巡检站点": row.get("巡检站点"),
                    "missing": missing,
                    "reason": "、".join(f"{field}未填" for field in missing),
                })
                continue
            valid.append({
                "id": row.get("id"),
                "巡检单号": row.get("巡检单号"),
                "巡检站点": str(row.get("巡检站点") or "").strip(),
                "巡检人员": person,
                "巡检日期": row.get("巡检日期"),
                "发现问题数": problem_count,
            })

        by_station = self._rollup(valid, "巡检站点")
        by_person = self._rollup(valid, "巡检人员")
        month_total = sum(
            item["发现问题数"]
            for item in valid
            if str(item.get("巡检日期") or "").startswith(month)
        )

        empty_reason = None
        if not valid:
            if not rows:
                empty_reason = "当前站点范围内没有巡检单，换个站点范围试试"
            else:
                empty_reason = "该范围内的巡检单都未填全巡检人员或发现问题数，不计入分布"

        return {
            "month": month,
            "station": station or "",
            "stations": stations,
            "month_total": month_total,
            "by_station": by_station,
            "by_person": by_person,
            "entries": valid,
            "excluded": excluded,
            "empty_reason": empty_reason,
        }

    @staticmethod
    def _rollup(entries: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
        """把有效巡检单按某个字段分组，汇总发现问题数与巡检单数，按问题数降序排列。"""
        grouped: dict[str, dict[str, Any]] = {}
        key_name = "station" if field == "巡检站点" else "person"
        for entry in entries:
            name = str(entry.get(field) or "")
            bucket = grouped.setdefault(name, {key_name: name, "problem_count": 0, "entry_count": 0})
            bucket["problem_count"] += int(entry["发现问题数"])
            bucket["entry_count"] += 1
        return sorted(grouped.values(), key=lambda item: (-int(item["problem_count"]), str(item[key_name])))

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
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
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"巡检单已{action}"
