"""PIC (nhân viên phụ trách nhóm sản phẩm) trong báo cáo: bộ lọc PIC và cột PIC.

Phân công lấy từ backend (prd_product_assigned -> map_group_pic, s_users -> dim_pic, nạp ở etl/sql/10_dims.sql).
Phân công theo nhóm SP, không tách theo sàn; một nhóm có thể có nhiều PIC.
- Bộ lọc: tham số `pic` (user_id; 0 = nhóm chưa có PIC) đổi thành danh sách nhóm SP, giao với bộ lọc Nhóm SP nếu
  có, nên mọi báo cáo đang lọc theo nhóm SP tự áp dụng được.
- Cột: bảng nào có cột "group_name" được chèn cột "PIC" ngay sau (lấy theo group_id của dòng, không có thì theo tên
  nhóm), trước khi lọc bảng nên lọc được theo cột PIC.
"""
from app.db import fetch_all
from app.metrics import col

NO_PIC = 0
NO_PIC_LABEL = "Chưa có PIC"


def options() -> list[dict]:
    rows = fetch_all("""SELECT d.user_id, d.name, d.code, d.active, COUNT(m.group_id) AS n_groups
                        FROM dim_pic d JOIN map_group_pic m ON m.user_id = d.user_id
                        GROUP BY d.user_id, d.name, d.code, d.active ORDER BY d.active DESC, d.name""")
    out = [{"id": r["user_id"], "label": f"{r['name'] or r['code']} · {r['n_groups']} nhóm"
            + ("" if r["active"] else " (đã nghỉ)")} for r in rows]
    return out + [{"id": NO_PIC, "label": NO_PIC_LABEL}]


def groups_for(pic_ids: list[int]) -> list[int]:
    """Nhóm SP của các PIC đã chọn; trả [-1] khi không có nhóm nào để bộ lọc ra kết quả rỗng thay vì 'tất cả'."""
    groups: set[int] = set()
    users = [p for p in pic_ids if p != NO_PIC]
    if users:
        marks = ", ".join(f":u{i}" for i in range(len(users)))
        groups |= {r["group_id"] for r in fetch_all(
            f"SELECT DISTINCT group_id FROM map_group_pic WHERE user_id IN ({marks})",
            {f"u{i}": u for i, u in enumerate(users)})}
    if NO_PIC in pic_ids:
        groups |= {r["group_id"] for r in fetch_all(
            """SELECT DISTINCT group_id FROM dim_product
               WHERE group_id IS NOT NULL AND group_id NOT IN (SELECT group_id FROM map_group_pic)""")}
    return sorted(groups) or [-1]


def _labels() -> tuple[dict[int, str], dict[str, str]]:
    rows = fetch_all("""SELECT m.group_id, MAX(p.group_name) AS group_name,
                               GROUP_CONCAT(DISTINCT COALESCE(d.name, d.code) ORDER BY d.name SEPARATOR ', ') AS pics
                        FROM map_group_pic m JOIN dim_pic d ON d.user_id = m.user_id
                        LEFT JOIN dim_product p ON p.group_id = m.group_id
                        GROUP BY m.group_id""")
    by_id = {r["group_id"]: r["pics"] for r in rows}
    by_name = {r["group_name"]: r["pics"] for r in rows if r["group_name"]}
    return by_id, by_name


def add_columns(result: dict) -> None:
    tables = [t for t in result.get("tables") or [] if any(c["key"] == "group_name" for c in t.get("columns", []))]
    if not tables:
        return
    by_id, by_name = _labels()
    for t in tables:
        if any(c["key"] == "pic" for c in t["columns"]):
            continue
        i = next(n for n, c in enumerate(t["columns"]) if c["key"] == "group_name")
        t["columns"].insert(i + 1, col("pic", "PIC"))
        for r in t.get("rows") or []:
            if r.get("group_id") is not None:
                r["pic"] = by_id.get(r["group_id"])
            elif r.get("group_name"):
                r["pic"] = by_name.get(r["group_name"])
            if r.get("group_name") and not r.get("pic"):
                r["pic"] = NO_PIC_LABEL
