"""Vị trí địa lý cho bản đồ tồn kho: bang / tỉnh của kho nội bộ, kho CastleGate và chuẩn hóa bang giao hàng.

Mã vùng: Mỹ = mã bang 2 chữ (CA, TX...), Canada = mã tỉnh 2 chữ (ON, BC...), Úc = mã bang (NSW, VIC...).
Kho nội bộ không có cột bang trong DWH nên gán tay theo tên kho (WAREHOUSE_REGION). Kho chưa gán -> hiện trong danh sách
"Chưa rõ bang" dưới bản đồ; sửa ở đây khi có kho mới.
"""

# wh_warehouses.id -> (nước, mã vùng). None = chưa biết bang.
WAREHOUSE_REGION: dict[int, tuple[str, str | None]] = {
    46: ("US", "CA"),    # US - Y4A - Brea
    47: ("US", "TX"),    # US - Pax - Dallas
    48: ("US", "CA"),    # US - Hytx - Azusa
    49: ("US", "CA"),    # US - Thang Long - INS (California, user xác nhận 08/11/2026)
    58: ("US", "CA"),    # US - NEO - Pico (Pico Rivera)
    59: ("US", "NC"),    # US - UPSWING - Charlotte
    73: ("US", "SC"),    # US GSW Orangeburg (South Carolina, user xác nhận 08/11/2026)
    51: ("CA", "ON"),    # Canada - BJ - Missi (Mississauga)
    52: ("CA", "ON"),    # Canada - BJ - Scar (Scarborough)
    53: ("CA", "ON"),    # Canada - DWS - Missi
    57: ("CA", "BC"),    # Canada - BJ - Vcv (Vancouver)
    77: ("CA", "ON"),    # Canada - Proshipper - ON
    56: ("AU", "NSW"),   # AU - TRIWAY - NSW
    72: ("AU", "NSW"),   # AU - PNL - NSW
}

# kho CastleGate không bắt đầu bằng mã bang
CG_SPECIAL = {"CAN - MISSISSAUGA": ("CA", "ON"), "FLORENCE RETURNS WAREHOUSE": ("US", "KY")}

US_STATES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA", "COLORADO": "CO",
    "CONNECTICUT": "CT", "CT.": "CT", "DELAWARE": "DE", "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY",
    "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH",
    "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA",
    "WASHINGTON": "WA", "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY", "PUERTO RICO": "PR",
}
CA_PROVINCES = {"ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "NT", "NU", "YT"}
AU_STATES = {"NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"}
AU_NAMES = {"NEW SOUTH WALES": "NSW", "VICTORIA": "VIC", "QUEENSLAND": "QLD", "WESTERN AUSTRALIA": "WA",
            "SOUTH AUSTRALIA": "SA", "TASMANIA": "TAS", "AUSTRALIAN CAPITAL TERRITORY": "ACT", "NORTHERN TERRITORY": "NT"}


def ship_region(country: str | None, state: str | None, state_code: str | None) -> str | None:
    """Bang / tỉnh giao hàng của đơn Amazon -> mã vùng chuẩn (None nếu không nhận ra)."""
    st = (state or "").strip().upper()
    code = (state_code or "").strip().upper()
    if country == "US":
        if len(st) == 2 and st.isalpha():
            return st
        return US_STATES.get(st)
    if country == "CA":
        for x in (code, st):
            if x in CA_PROVINCES:
                return x
        return None
    if country == "AU":
        for x in (code, st):
            if x in AU_STATES:
                return x
        return AU_NAMES.get(st)
    return None


def cg_region(title: str) -> tuple[str, str | None]:
    """Tên kho CastleGate ("CA - LATHROP") -> (nước, mã bang)."""
    t = (title or "").strip().upper()
    if t in CG_SPECIAL:
        return CG_SPECIAL[t]
    code = t.split(" - ")[0].strip()
    return ("US", code) if len(code) == 2 and code.isalpha() else ("US", None)
