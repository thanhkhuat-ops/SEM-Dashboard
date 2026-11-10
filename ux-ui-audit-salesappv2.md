# SaleSappV2 — Đánh giá UX/UI & Accessibility (plugin `ux-ui-audit`)

**Phạm vi:** Amazon (Tổng quan, Campaign, Search term, Thêm / Phủ định, Gửi tin PIC, Từ điển từ khóa) · Wayfair (Tổng quan, Keyword) · Tồn kho (Tổng quan, Dự kiến hết hàng)
**Viewport:** 1440×900 sáng · 375×812 tối (và kiểm tra 1440 sáng cho Tồn kho) · **Ngày:** 2026-10-30
**Dữ liệu:** MySQL thật. Amazon đo trên `localhost:8000`; Wayfair/Tồn kho đo trên `localhost:8002` vì server 8000 chạy code cũ từ 2026-10-29 và trả 404 cho `wf_overview`/`wf_keywords` (xem #22).
**Cách làm:** các probe của plugin (`probe-core`, `probe-heuristics`, `probe-perception`, `probe-ltr`, `probe-focus`) được chạy trong trang. Mã probe chỉ lấy từ thư mục plugin qua một static server cục bộ, không tải gì từ bên ngoài. Sau đó có thêm phần đọc nội dung, đối chiếu với API (chỉ dùng GET) và đọc mã nguồn. Không sửa dòng code nào.
**Chuẩn đối chiếu:** WCAG 2.2 AA cho a11y. Phần usability dùng heuristic Nielsen, Hick và Fitts. Thang mức độ và thứ tự "tác động ÷ công sức" là quy ước của plugin, không phải tiêu chuẩn.

## Tóm tắt

| Mức | Số lượng |
|---|---|
| Critical | 2 |
| Major | 10 |
| Accessibility | 6 |
| Note | 4 |

Kết quả so với 12 mục review trước:
- **Khớp và có số đo mới:** P1-1, P1-2, P1-3, P1-4, P2-5, P2-6, P2-7, P2-8, P2-9, P3-11, P3-12.
- **Một phần sai:** P3-10. `#b54708` trong CSS đã có override cho dark mode (`styles.css:137`). Ý "trạng thái chỉ bằng màu" (P3-11) cũng không đúng với bảng, vì ô trạng thái có chữ.
- **Phát hiện mới quan trọng nhất:**
  - Hàng "Tổng" của bảng Campaign mâu thuẫn với tab Tổng quan (#01).
  - Khoảng ngày lưu dạng tuyệt đối nên bị "đóng băng" (#03).
  - Nút xóa trong Từ điển không có xác nhận (#06).

## Danh sách phát hiện

| # | Mức | Màn hình | Phát hiện | Bằng chứng đo được | So với review trước |
|---|---|---|---|---|---|
| 01 | **Critical** | Amazon › Campaign | Hàng "Tổng" của bảng **mâu thuẫn** với KPI Tổng quan cùng khoảng ngày, vì tổng chỉ cộng 500 dòng đã bị cắt. API cũng không trả tổng số dòng thật. | Cùng khoảng 09-28→10-27: Tổng quan Spend **$40,950.57**, Ad Sales **$273,325.50**; hàng Tổng bảng Campaign Spend **$39,318.14**, Ad Sales **$259,923.77** (lệch $1,632 / $13,402, ≈4–5%). API `/api/report/campaigns` trả `rows: 500`, không có trường total. Search term và Wayfair Keyword cũng dừng ở "(1000 dòng)". | P1-3. **Mở rộng:** không chỉ cắt im lặng mà còn ra số tổng sai. |
| 02 | **Critical** | Amazon và Wayfair › Tổng quan | Ngày cuối chưa đủ dữ liệu làm biểu đồ và KPI sai. Amazon tụt về gần 0, còn Wayfair thì TACoS **vọt lên**. Header vẫn ghi "đến 2026-10-28" như thể ngày đó đã đủ dữ liệu. | Amazon (end = 10-28): Spend 10-27 **1,371.54** → 10-28 **40.90**; Ad Sales 8,830 → **0**; CVR 0.007 → **0**. Wayfair: TACoS 10-27 **4.5%** → 10-28 **25.4%** (doanh số sỉ của ngày cuối chưa đủ). Hệ thống cũng nhận end = 10-30 (sau ngày có dữ liệu) mà không cảnh báo. | P1-1. **Mới:** biến thể Wayfair, số bị đẩy lên thay vì tụt. |
| 03 | Major | Mọi kênh | Khoảng ngày được lưu dạng **tuyệt đối** vào localStorage. Tuần sau người dùng mở lại vẫn thấy khoảng ngày cũ, còn ô "Chọn nhanh…" không cho biết đang ở preset nào. | `ssv2.dates={"start":"2026-09-28","end":"2026-10-27"}`. Khi khởi động, `init()` dùng lại giá trị này (`app.js:1244-1246`). Lúc đo, dữ liệu đã có đến 10-28 nhưng màn hình vẫn dừng ở 10-27. | **Mới** |
| 04 | Major | Amazon Campaign, Search term, Thêm/Phủ định; Wayfair Keyword; Dự kiến hết hàng | Các cột số chính bị đẩy ra khỏi màn hình. Cột đầu không cố định. | 1440px: vùng bảng rộng 1376px, nhưng cột Spend bắt đầu ở x=1359, Ad Sales ở 1675, ACoS ở 1772; scrollWidth 2164. Mobile: vùng bảng 341px, Spend ở x=1359 (≈4 lần bề ngang màn hình). Wayfair Keyword có 7 cột chữ trước cột số đầu tiên (scrollWidth 2215). Dự kiến hết hàng có 24 cột, rộng 3240px. `td` đầu tiên là `position: static`. | P1-2 |
| 05 | Major | Toàn app | Tab, kênh và bộ lọc không lên URL nên không chia sẻ link được, nút Back cũng không hoạt động. | Sau khi chuyển 3 kênh và khoảng 10 tab, `location.href` vẫn là `http://localhost:8002/` và `history.length` = 2. | P1-4 |
| 06 | Major | Amazon › Từ điển từ khóa | Nút ✕ xóa xóa ngay, không hỏi lại và không có hoàn tác. Nút nhỏ, và mọi nút đều có cùng tên "Xóa". Xóa một brand sẽ làm phân nhóm search term thay đổi. | Kích thước **19×20px** (<24px, WCAG 2.5.8), 26 nút. Code: `title: 'Xóa'` → gọi `DELETE` ngay (`app.js:1227-1228`). Ngược lại, xóa webhook PIC thì có `confirm()` (`app.js:1104`), nên hai chỗ không nhất quán. | **Mới** |
| 07 | Major | Bộ lọc (mọi kênh) | Khối lọc chiếm nhiều chỗ, không sticky, nội dung chính bắt đầu rất thấp. | Desktop: 150px. Mobile: header 117px + bộ lọc 304px = **421px (52% màn 812px)**; KPI đầu tiên ở y=477. `position: static`. | P2-6 |
| 08 | Major | Search term, Wayfair Keyword | Khi tải lâu chỉ có dòng chữ "Đang tải…": không có skeleton, không có `aria-busy`, không có live region. | Search term **3,837 ms**, Wayfair Keyword **1,611 ms**, cả hai vượt ngưỡng Doherty 400 ms. Probe ghi nhận `liveRegions: 0`, `spinnerElements: 0`. | P3-12 (đề xuất **nâng mức**) |
| 09 | Major | Toàn app (đọc nội dung) | Cùng một chỉ số mang tên khác nhau giữa các kênh. Tiếng Anh và tiếng Việt trộn lẫn. Enum thô và có ba kiểu định dạng ngày. | Amazon "Ad Sales" / "Tổng doanh số" và Wayfair "DS QC (giá sỉ)" / "Tổng DS sỉ". Ô Trạng thái hiển thị `ENABLED`, `ARCHIVED`, `PAUSED`, `–` (null). Ngày: ISO `2026-10-28` (header, trục biểu đồ), `29/10` (gantt hết hàng), `09/28/2026` (ô date theo locale trình duyệt). Probe LTR: 9 nhãn Title Case và 12 nhãn Sentence case cùng cấp. | **Mới** |
| 10 | Major | Amazon (13 tab), Wayfair (11 tab) | Thanh tab phẳng, không nhóm, trên mobile phải cuộn ngang. | Hick: 13 lựa chọn, chỉ số 3.81. Probe chunking: "13 lựa chọn phẳng, vượt 7±2". Mobile: scrollWidth **1338** / 375 (≈3.6 màn), chỉ thấy khoảng 3.5 tab. | P2-7 |
| 11 | Major | Amazon và Wayfair › Tổng quan | 15 thẻ KPI cùng trọng số, không có điểm vào. | 15/15 thẻ đều 20px. Tỉ lệ tiêu đề/thân **1.43** (<1.5). 14 lần lặp lại "so với kỳ trước". Spend ▲1.0% tô đỏ trong khi Impressions ▲1.0% tô xanh: quy ước màu tốt/xấu có tồn tại nhưng không có chú giải. | P2-8 |
| 12 | Major | Bộ lọc | Cách áp dụng bộ lọc không nhất quán: preset tự tải, các bộ lọc khác phải bấm "Xem báo cáo", ô campaign thì Enter là tải. Không có dấu hiệu "đã đổi nhưng chưa áp dụng". | `app.js:1247` (preset → `load()`), `:1248` (nút), `:1249` (Enter). Probe: `ariaExpanded: 0`, không có trạng thái "dirty". | P2-5 |
| 13 | A11y · 4.1.2 / 1.3.1 / 3.3.2 | Toàn app | **Không có một thuộc tính ARIA nào** trong DOM. Tab và kênh đang chọn chỉ thể hiện qua class. Nhiều input không có tên. | Đếm `[aria-*],[role]` được **0**. Tab: `<button class="active">`, không có `aria-selected`/`aria-pressed`. Dropdown đa chọn không có `aria-expanded`. Tab Gửi tin PIC có **28 input không tên** (webhook, số, checkbox). `#f-campaign` và "Tìm trong bảng…" chỉ có placeholder. Các nút lọc cột đều tên "Tất cả ▾", không gắn với cột nào. | P3-11 |
| 14 | A11y · 2.1.1 | Mọi bảng | Tiêu đề cột sắp xếp được nhưng không dùng được bằng bàn phím và không báo hướng sắp xếp. | 0/22 `th` có `tabindex`; click handler đặt trên `th` (`app.js:991`). `aria-sort` = null. CSS không có rule `:focus` hay `:focus-visible` nào (probe `focus: 0`). | P3-11 |
| 15 | A11y · 1.4.11 | Biểu đồ Amazon, Tồn kho | Một số màu biểu đồ dưới ngưỡng tương phản 3:1. Biểu đồ Amazon dùng hex cứng nên không đổi theo theme. | Nền sáng (#fff): "Thấp" `#fab219` **1.83:1**, "Không bán" `#c3c2b7` **1.79:1**, "Nguy cấp" `#ec835a` **2.64:1**. Nền tối (#1d2027): TACoS/CVR `#9c36b5` **2.80:1**, "Không bán" `#5c5b56` **2.40:1**. Hex cứng ở `app.js:343-346, 722-733`, trong khi Wayfair dùng palette theo theme (`app.js:356-357`). | P3-10. **Đính chính:** `#b54708` trong CSS đã có override dark (`styles.css:137`). |
| 16 | A11y · 2.5.8 | Bảng, Từ điển, PIC | Một số vùng bấm nhỏ hơn 24px. | Nút lọc cột **70×23**, ✕ Từ điển **19×20**, checkbox PIC **13×13**, summary "Cách lấy webhook" cao **19px**. Tab PIC có 71 vùng bấm ở mức 24–44px. | **Mới** |
| 17 | A11y · 1.4.1 | Dự kiến hết hàng (gantt) | "Còn đủ bán" và "Đứt hàng" chỉ phân biệt bằng xanh lá và đỏ. | `#0ca30c` và `#d03b3b` có độ sáng gần nhau (≈1.43:1 giữa hai màu), khó phân biệt với người mù màu đỏ-lục. | **Mới** |
| 18 | A11y · 1.3.1 / 2.4.1 | Toàn app | Không có h1 và không có skip link. Tab Từ điển có H3 nhưng không có H2. | `h1Count: 0`, `skipLink: false`. | **Mới** (Note) |
| 19 | Note | Tồn kho › Tổng quan | Vẫn hiện Từ/Đến/Chọn nhanh dù dòng gợi ý nói ngày chỉ áp cho một tab. Nhãn "14 ngày" và "30 ngày" chồng lên nhau và lên cột. | Gợi ý: "khoảng ngày chỉ áp cho tab Bán theo kênh / nước". Ảnh chụp ở cả 375px và 1440px cho thấy nhãn đè cột CastleGate Megsu. | P2-9 |
| 20 | Note | Header | Nút kênh đang chọn dùng đúng màu xanh đặc của nút chính "Xem báo cáo", nên hai thứ cạnh tranh nhau. | Cả hai đều `rgb(47,111,222)` / 600. Probe đếm 7 kiểu hiển thị khác nhau cho button. | **Mới** |
| 21 | Note | Lỗi tải | Khi lỗi, màn hình hiện chuỗi thô và các KPI để trống, không có nút thử lại hay lời giải thích. | Server 8000: `Không có báo cáo 'wf_keywords'`, header "Dữ liệu QC đến –". | **Mới** |
| 22 | Note | Xuất | Chỉ xuất được HTML. Chưa kiểm tra lại chi tiết. | — | P3-12 |

## Những gì đang làm tốt (có số đo)

- **Tương phản chữ:** 0 lỗi trên khoảng 150 node đo mỗi màn, cả sáng lẫn tối, mọi màn đã kiểm tra.
- **Focus ring:** dùng mặc định của trình duyệt, `rgb(229,151,0)` đạt **6.8:1** trên nền tối, qua chuẩn 1.4.11.
- **Design system gọn:** 5 cỡ chữ, 1 font, 2 bo góc (6/8px), 5 màu chữ, 11 giá trị spacing.
- **Dark mode qua token:** `--bg #14161b`, `--card #1d2027`, `--text #e7e9ee`. Biểu đồ Wayfair đổi palette theo theme.
- **Không tràn ngang cả trang ở 375px:** scrollWidth bằng 375; chỉ bảng cuộn bên trong.
- **Bảng:** `th` và `tfoot` sticky.
- **Ô trạng thái có chữ:** bảng Tồn kho hiện "Hết hàng", không chỉ tô màu.
- **Thao tác rủi ro trên tab PIC có xác nhận:** gửi tin và xóa webhook đều qua `confirm()`.
- **Trang đúng ngôn ngữ:** `lang="vi"`.
- **Hiệu năng:** 0 long task trên 50 ms.

## Nên sửa trước (theo tác động ÷ công sức)

1. **#01** Tính hàng Tổng trên toàn bộ dữ liệu ở server, hoặc ghi rõ "Tổng của 500 dòng đầu / N dòng". Công sức nhỏ, mà gỡ được một con số sai.
2. **#02** Bỏ ngày chưa đủ dữ liệu ra khỏi mặc định, hoặc đánh dấu "tạm tính"; chặn ngày kết thúc sau mốc có dữ liệu.
3. **#03** Lưu preset (ví dụ "30 ngày qua") thay vì ngày tuyệt đối.
4. **#06** Thêm `confirm` hoặc hoàn tác cho nút ✕ trong Từ điển, tăng vùng bấm lên ≥24px, đặt `aria-label="Xóa <từ>"`.
5. **#05** Ghi kênh, tab và bộ lọc lên URL bằng `history.replaceState`/`pushState`.
6. **#13 / #14** Các bản sửa ARIA nhanh: `aria-selected`, `aria-expanded`, `aria-sort`, `tabindex` cho `th`, label cho input.
7. **#04** Cố định cột tên, đưa các cột Spend, Ad Sales, ACoS lên trước.
8. **#15 / #17** Dùng palette theo theme cho biểu đồ Amazon và Tồn kho, đảm bảo ≥3:1.
9. **#08, #07, #10, #11, #09, #12**: các thay đổi bố cục và nội dung lớn hơn.

## Trạng thái sửa (cập nhật 2026-10-30)

Đã sửa toàn bộ 22 mục, theo thứ tự ở mục trên; kiểm tra trên localhost:8002 (desktop + mobile, sáng + tối), unit test và
test đầu-cuối trên MySQL Docker đều đạt.

| Mục | Đã làm |
|---|---|
| 01 | Tổng và số dòng thật tính ở server (hàm cửa sổ trước LIMIT); "500 trong 1,579 dòng" + nút tải tối đa 5,000 dòng |
| 02, 03 | Ngày mới nhất coi là tạm tính: preset dừng ở ngày trước, cảnh báo + nét đứt trên đồ thị; lưu preset thay vì ngày cố định |
| 04 | Ghim cột định danh khi cuộn ngang; Spend / Ad Sales / ACoS đứng ngay sau |
| 05 | Kênh, tab, ngày, bộ lọc lên URL; Back / Forward hoạt động |
| 06 | ✕ Từ điển hỏi lại trước khi xóa, 28×28px, tên riêng từng nút |
| 07 | Bộ lọc thu gọn trên mobile kèm dòng tóm tắt; thanh tab dính trên cùng |
| 08 | Khung chờ (skeleton) + thông báo khi tải lâu |
| 09 | Trạng thái campaign tiếng Việt, ngày dd/mm/yyyy |
| 10 | Tab chia nhóm Hiệu suất / Từ khóa / Công cụ; mobile dùng ô chọn |
| 11 | 4 KPI chính lớn, một dòng chú giải màu tốt / xấu |
| 12 | Nút "Xem báo cáo (đã đổi bộ lọc)" khi bộ lọc chưa áp dụng |
| 13, 14, 18 | ARIA cho tab / kênh / dropdown / sắp xếp, nhãn cho input, focus-visible, skip link, h1, live region |
| 15, 17 | Bảng màu biểu đồ theo theme, mọi màu ≥ 3:1; "Đứt hàng" có sọc chéo |
| 16 | Vùng bấm ≥ 24px (nút lọc cột, summary); checkbox 18px |
| 19 | Ẩn ngày ở tab tồn kho không theo ngày; nhãn vạch 14 / 30 ngày không đè cột |
| 20 | Nút kênh đang chọn đổi sang kiểu nhạt, không tranh với nút chính |
| 21 | Màn lỗi có giải thích theo loại lỗi + nút Thử lại |
| 22 | Mỗi bảng có nút Tải CSV (dòng đang hiện, mở được bằng Excel) |

## Giới hạn

- Không đo được đúng phân tích hiệu năng khi tải trang (FCP 11.9s là do pane chạy nền nên không đáng tin).
- Không kiểm tra trình đọc màn hình thật.
- Chưa kiểm tra lại chi tiết file xuất HTML.
- Amazon đo trên server 8000 (code cũ), nhưng file tĩnh frontend thì giống nhau. Các số của Amazon có thể lệch nhẹ so với server mới.
