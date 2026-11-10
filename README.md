# SaleSappV2: Báo cáo bán hàng, quảng cáo (Amazon, Wayfair, Shopify) và tồn kho

Hệ thống báo cáo quảng cáo Amazon (Sponsored Products / Brands / Display) cho mọi tài khoản HMD.
Dữ liệu lấy từ schema MySQL `staging`, được tổng hợp sang schema `ads_mart`, rồi hiển thị trên web app (FastAPI + HTML/JS). Mỗi báo cáo đều xuất được ra file HTML độc lập.

```
DWH (server khác) · staging (sem__*, amazon_profiles_base, prd_*, s__amazon_orders…)
   │  bước đồng bộ (etl/sync_staging.py): chỉ chép các bảng và khoảng ngày cần dùng
   ▼
MySQL nội bộ · staging (bản sao)
   │  python -m etl.run          (SQL INSERT…SELECT + Python phân loại từ khóa)
   ▼
MySQL nội bộ · ads_mart (dim_*, fact_*_daily, dim_term, bridge_term_ngram, dict_*)
   │  uvicorn app.main:app
   ▼
Web app  /  /export/<báo cáo>.html
```

## Cài đặt

Yêu cầu: Python 3.11+ và **MySQL 8.0+** (ETL dùng window function và `INSERT … SELECT … ON DUPLICATE KEY UPDATE`).

```bash
python -m venv .venv
```
```bash
.venv/Scripts/python -m pip install -r requirements.txt
```

Sao chép `.env.example` thành `.env` rồi điền thông tin kết nối:

| Nhóm biến | Trỏ tới | Quyền cần |
|---|---|---|
| `DB_*`, `STAGING_SCHEMA`, `MART_SCHEMA` | MySQL nội bộ, nơi chứa bản sao staging và `ads_mart` | `CREATE`, `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER` trên hai schema này |
| `SOURCE_DB_*`, `SOURCE_SCHEMA` | DWH staging thật (server khác) | Chỉ `SELECT` |

Nếu staging nằm cùng server với `DB_*`, để trống `SOURCE_DB_HOST`: ETL sẽ đọc thẳng `STAGING_SCHEMA` mà không đồng bộ.

### Đồng bộ từ DWH

Mỗi lần chạy `etl.run`, trước khi tổng hợp, ETL chép đúng các bảng cần dùng từ DWH về bản sao nội bộ:
- **Bảng danh mục / nhỏ** (profile, campaign, ad group, sản phẩm, listing, tỷ giá USD/CAD/AUD/MXN, từ điển search term): chép lại toàn bộ.
- **Bảng report theo ngày** (`sem__sp_*`, `sem__sb_*`, `sem__sdp_*`, `sem__campaigns_base_daily`): xóa rồi chép lại đúng khoảng ngày đang nạp, theo từng đợt 31 ngày.
- **Đơn hàng**: theo `purchased_date`; chi tiết đơn lấy theo các đơn trong khoảng đó.
- **Bid** (`sem__keywords_base_daily`, khoảng 26GB ở nguồn): không quét cả bảng. Chỉ tra theo khóa chính những cặp keyword × ngày có trong report và còn thiếu ở bản sao.

Bản sao được tạo bằng `SHOW CREATE TABLE` của nguồn, cộng thêm index theo cột ngày. Lần `--init` đầu tiên chép toàn bộ lịch sử từ `ETL_BACKFILL_START`, nên có thể mất khá lâu tùy tốc độ mạng tới DWH. Các lần chạy hằng ngày chỉ chép 60 ngày gần nhất. Dùng `--no-sync` để tổng hợp lại từ bản sao đang có mà không kết nối DWH.

Lần đầu: tạo schema và nạp lịch sử từ `ETL_BACKFILL_START`. ETL chạy theo từng đợt 31 ngày.

```bash
.venv/Scripts/python -m etl.run --init
```

Chạy web app chỉ trên máy hiện tại, sau đó mở http://localhost:8000:

```bash
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

### Truy cập từ các máy trong LAN (Windows)

Máy chủ trong cấu hình này có địa chỉ **192.168.1.42/24**, mạng **192.168.1.0/24**, cổng web **8000**. Máy khách mở **http://192.168.1.42:8000**. Địa chỉ `localhost` trên máy khách là chính máy khách, còn `0.0.0.0` chỉ là địa chỉ lắng nghe của server, không phải địa chỉ để mở trong trình duyệt.

Các lệnh dưới chạy tại thư mục gốc dự án. Khởi động web chạy nền:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_server.ps1
```

Script khởi động Uvicorn lắng nghe `0.0.0.0:8000`, ghi log vào `logs/web_stdout.log` và `logs/web_stderr.log`. Có thể gọi lại: nếu cổng đã có tiến trình, script kiểm tra ứng dụng đang chạy và không tự tắt tiến trình đó. Nếu server cũ chỉ lắng nghe `127.0.0.1`, cần khởi động lại để nhận kết nối LAN.

Để khởi động lại và xem log trực tiếp trong cửa sổ PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\restart_server.ps1 -Port 8000 -BindAddress 0.0.0.0
```

Lệnh khởi động lại giữ server ở cửa sổ hiện tại; `Ctrl+C` hoặc đóng cửa sổ sẽ dừng server. Dùng script chạy nền ở trên cho vận hành thường ngày. Giữ **một worker** vì trạng thái phân loại từ khóa và khóa xử lý audit hiện nằm trong bộ nhớ của từng tiến trình; không dùng `--reload` khi phục vụ người dùng.

Để áp dụng cấu hình Windows, chạy lệnh sau trong **PowerShell với quyền Administrator**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure_lan.ps1
```

Cấu hình dự kiến gồm rule Windows Firewall cho **TCP 8000**, profile **Private**, địa chỉ máy chủ **192.168.1.42**, chỉ nhận từ **192.168.1.0/24**; cùng tác vụ **SaleSappV2-Web** trong Task Scheduler để chạy web khi người dùng hiện tại đăng nhập, với quyền thông thường. Cần xem kết quả thực thi script để xác nhận từng bước đã áp dụng thành công. Đây là khởi động **khi đăng nhập**, không bảo đảm web đã chạy trước màn hình đăng nhập sau khi máy khởi động lại. Máy chủ cần được bật và không ngủ trong thời gian phục vụ.

Kiểm tra ứng dụng trên máy chủ, rồi chạy lại các lệnh sau **trên một máy khác trong LAN**:

```powershell
Test-NetConnection 192.168.1.42 -Port 8000
$lanHealth = Invoke-RestMethod -Uri 'http://192.168.1.42:8000/api/health'
if ($lanHealth.ok -ne $true) { throw 'Web nhận kết nối nhưng kiểm tra ứng dụng/cơ sở dữ liệu chưa thành công.' }
```

`TcpTestSucceeded` cần là `True`; `/api/health` cần trả về **`ok: true`**, không chỉ HTTP 200. Sau đó mở trang và thử tải một báo cáo. Nếu máy chủ truy cập được nhưng máy khác không được, kiểm tra profile mạng, rule firewall và việc router/Wi-Fi có chặn liên lạc giữa các máy hoặc VLAN hay không. Địa chỉ `192.168.1.42/24` hiện đã được đặt tĩnh trong Windows (`PrefixOrigin: Manual`), nên không cần DHCP reservation để giữ địa chỉ hiện tại; người quản trị mạng cần bảo đảm router không cấp địa chỉ này cho máy khác. Nếu chuyển máy chủ hoặc chuyển sang DHCP, nhờ người quản trị router đặt reservation phù hợp; khi đổi IP hoặc subnet, cập nhật rule firewall và URL truy cập tương ứng.

Ứng dụng hiện **chưa có đăng nhập/phân quyền**: máy được phép kết nối có thể xem báo cáo, sửa giá vốn/mục tiêu/từ điển, upload audit và gửi thử Google Chat. Phạm vi LAN ở trên phù hợp với nhóm người dùng được tin cậy; cần bổ sung xác thực và phân quyền trước khi chia sẻ cho phạm vi rộng hơn. Máy khách chỉ kết nối cổng web, **không cần mở MySQL 3306** cho LAN và không cần sửa `DB_HOST` chỉ để bật truy cập web.

Nếu sử dụng link báo cáo trong Google Chat, đặt `NOTIFY_APP_URL=http://192.168.1.42:8000` trong `.env` và khởi động lại ứng dụng để nhận cấu hình. Chart.js và dữ liệu bản đồ hiện được tải từ CDN; máy khách cần Internet cho các phần này, hoặc phải lưu tài nguyên CDN vào ứng dụng nếu muốn dùng hoàn toàn ngoại tuyến.

## Vận hành hằng ngày

Nên chạy sau khi các DAG `hmd_SEM_*` hoàn tất (khoảng 20:00 theo log cập nhật). Lệnh dưới nạp lại `ETL_REFRESH_DAYS` (mặc định 60) ngày gần nhất, vì số liệu quy đổi của Amazon về trễ:

```bash
.venv/Scripts/python -m etl.run
```

Trên Windows có thể đặt lệnh này trong Task Scheduler. Các lệnh khác:

| Lệnh | Công dụng |
|---|---|
| `python -m etl.run --start 2025-01-01 --end 2025-06-30` | Nạp lại một khoảng ngày |
| `python -m etl.run --days 7` | Nạp lại 7 ngày gần nhất |
| `python -m etl.run --reclassify` | Phân loại lại toàn bộ từ khóa (hoặc bấm nút trên tab *Từ điển từ khóa*) |

Mỗi bước ETL được ghi vào `ads_mart.etl_run_log`; xem nhanh qua `GET /api/health`.

## Quy ước số liệu

| Quy ước | Chi tiết |
|---|---|
| Tiền tệ | Mọi chỉ số tiền đều quy USD theo tỷ giá ngày (`staging.exchange_rate_usd`). Ngày thiếu tỷ giá lấy tỷ giá gần nhất trước đó. Bảng fact vẫn giữ `cost`/`sales` theo tiền gốc. |
| Cửa sổ quy đổi | `orders`/`units`/`sales`: **SP 7 ngày, SB/SD 14 ngày**, giống Ads Console của seller. Cột `orders_14d`/`sales_14d_usd` dùng 14 ngày cho mọi loại, để so sánh. |
| SD | Campaign **vCPM** dùng quy đổi view + click, campaign CPC dùng click. Ở nguồn `sem__sdp_campaigns`, cột đơn NTB và doanh số NTB bị đảo cho nhau; ETL đảo lại. |
| SB | Bảng `_video` được nạp trước, bảng thường ghi đè khi trùng khóa, nên không bị đếm hai lần. |
| Tổng doanh số (TACoS) | Lấy từ `s__amazon_orders` + `s__amazon_order_details`: `item_price`, bỏ đơn Canceled, theo ngày `purchased_date`. Đơn Pending chưa có giá nên vài ngày gần nhất có thể thấp hơn thực tế. Ngày đơn hàng theo giờ nguồn, có thể lệch vài giờ so với ngày báo cáo QC. |
| Keyword → sản phẩm | Ad group SP thường chứa nhiều biến thể của một nhóm sản phẩm. `map_adgroup_product` lưu tỷ trọng chi phí của từng sản phẩm và đánh dấu sản phẩm chủ đạo. Bộ lọc Nhóm SP/Brand giữ những campaign có sản phẩm thuộc nhóm đó (SD chưa có map sản phẩm). |

**Chỉ số:** Impressions, Clicks, CTR, Spend, CPC, Orders, Units, CVR, Ad Sales, ACoS, ROAS, CPA, AOV, NTB Orders/%, DPV, TACoS, % doanh số từ QC, doanh số organic, Top-of-Search IS, mức dùng ngân sách và số ngày hết ngân sách.

## Báo cáo (tab trên web app)

Tổng quan (KPI so với kỳ trước; hai đồ thị Spend / Ad Sales và ACoS / TACoS theo ngày, không dùng hai trục; bảng theo loại QC, theo tài khoản kèm TACoS thu gọn bên dưới) · Campaign / Ad group · Keyword / Target · Search term · **Phân tích từ khóa** · **N-gram** · **Thêm / Phủ định** · Sản phẩm (kèm TACoS) · Halo & Brand Halo · Placement SB · Ngân sách · Từ điển từ khóa.

**Lọc trong từng bảng** (`app/table_filters.py`), ngoài thanh lọc chung:
- *Lọc theo chỉ số*: các điều kiện kết hợp bằng VÀ, ví dụ Spend ≥ $10 và Orders = 0. Có sẵn các mẫu nhanh: Tiêu tiền 0 đơn, Nhiều click 0 đơn, ACoS cao, Hiệu quả tốt, CTR thấp. Tỷ lệ nhập theo %. Ô trống (ví dụ ACoS khi chưa có doanh số) không thỏa điều kiện nào.
- *Lọc theo cột*: dòng ngay dưới tiêu đề. Cột có không quá 300 giá trị (Loại, Match, Phân nhóm, Số từ…) có danh sách chọn giống Excel; cột nhiều giá trị (Campaign, Keyword…) có ô "chứa…", gõ xong bấm Enter.
- *Cột ▾*: bỏ tick để ẩn cột. Lựa chọn nhớ riêng cho từng bảng của từng tab (trong trình duyệt) và áp cả khi Xuất HTML (tham số `hc`).
- *Xuất HTML*: file HTML độc lập gồm thẻ KPI, **các đồ thị như trên app** và các bảng (bấm tiêu đề cột để sắp xếp). Đồ thị vẽ bằng `app/static/export_charts.js` (bản chỉ xem của phần đồ thị trong app.js, nhúng thẳng vào file; sửa kiểu đồ thị ở app.js thì sửa cả ở đây). Cần mạng khi mở file để tải Chart.js (và bản đồ Mỹ ở tab CastleGate). Đường tồn SKU nhúng sẵn số liệu của SKU mặc định.
- Lọc chạy ở server trên tối đa 5.000 dòng đứng đầu theo thứ tự của báo cáo (mặc định theo Spend). Dòng Tổng và file HTML xuất ra chỉ tính các dòng đã lọc. Bộ lọc được nhớ riêng cho từng tab trong trình duyệt.

## Tổng hợp mọi kênh

Nút **Tổng hợp** (đầu thanh trên cùng, mặc định khi mở app lần đầu) gom doanh số, chi phí QC và tồn kho của mọi kênh lên một trang. Bộ lọc: ngày, **Kênh** (Amazon / Wayfair / Shopify / Khác), **Nước** (US / CA / AU), Nhóm SP, Brand.

| Kênh | Doanh số lấy từ |
|---|---|
| Amazon | đơn hàng (`fact_total_sales_daily`), giá bán lẻ `item_price`, bỏ đơn Canceled |
| Wayfair | đơn hàng theo **giá sỉ** (`fact_wf_total_sales_daily`), nước của khách |
| Shopify | `fact_shop_line`, sau giảm giá, chưa trừ hoàn tiền |
| Khác (Walmart, eBay, bán sỉ, AVC…) | `fact_channel_sales_daily`, các kênh không phải `AMZ-` / `WAYFAIR-` / `SPF-` |

- **DS sau phí sàn** = doanh số × (1 − phí sàn mặc định của kênh). Phí sửa ở *Công cụ › Giá vốn & phí*; mặc định Amazon 15%, Wayfair 0% (giá sỉ đã trừ hoa hồng), Shopify 3% (phí thanh toán), kênh khác 15%.
- **Spend QC** gồm Amazon, Wayfair và chi phí QC Shopify nhập tay (khi kỳ có tháng đã nhập; không tính khi lọc nhóm SP / brand). **TACoS chung** = spend ÷ doanh số mọi kênh. ACoS chỉ hiện riêng Amazon / Wayfair vì hai sàn dùng cửa sổ quy đổi khác nhau, Shopify không có DS từ QC.
- Lọc Nhóm SP / Brand: KPI spend dùng cùng cách với tab của từng sàn (giữ campaign có sản phẩm thuộc nhóm). Bảng *Theo nhóm SP* thì chia spend của campaign cho các nhóm theo tỷ trọng sản phẩm quảng cáo, nên tổng có thể lệch nhẹ so với KPI.
- **Lọc kênh**: chỉ giữ doanh số và chi phí QC của các kênh chọn (đồ thị, thẻ, cột theo kênh cũng chỉ còn các kênh đó).
- **5 đồ thị chính** (theo ngày, kỳ dài gộp theo tuần): (1) doanh số theo thị trường US / CA / AU; (2) doanh số theo kênh bán; (3) doanh số theo **công ty**: gán theo tên tài khoản Amazon / Wayfair, store Shopify, mã kênh khác (`company_of` trong `app/reports_all.py`: DHI / DH Intra, Megsu, Arozu, Senno (gồm kênh Amazon Úc "Hurav Senno" và Tranquillo), Hurav, Infideals, Idzo…; không khớp = *Khác / chưa rõ*); (4) chi phí QC theo thị trường, kèm đường TACoS tổng ở trục phải; (5) dự báo tồn kho theo nước. Bên dưới: 15 nhóm SP theo kênh, 15 SKU sắp hết hàng.
- **Tồn kho & dự báo** (ảnh chụp mới nhất, không theo khoảng ngày): nút ALL-<nước> = kho nội bộ + CastleGate, chưa có FBA. Mỗi SKU × nước vào một nhóm: *đang hết hàng*; *hết trong 14 ngày* / *15–30 ngày* theo ngày dự kiến hết hàng đã cộng hàng đang về theo ETA; còn lại *ổn* (< 90 ngày) hoặc *tồn nhiều* (≥ 90 ngày) theo số ngày đủ bán với tồn hiện có (cùng ngưỡng với tab Tồn kho); *có tồn, không bán 90 ngày*. Thẻ "SKU hết trong 30 ngày" gồm cả SKU hết trong 14 ngày. Khi lọc kênh, chỉ giữ SKU × nước có bán trên kênh đó trong kỳ (kho dùng chung mọi kênh). Bảng: Kênh × nước, Theo công ty, Theo nhóm SP, Tồn kho theo nước, SKU đang hết / sắp hết (kênh có bán, lô hàng kế, thiếu để đủ 60 ngày, DS mất ước tính).
- Nội dung: KPI so với kỳ trước · doanh số theo kênh theo ngày/tuần · so kỳ trước theo kênh · TACoS theo ngày/tuần · 15 nhóm SP lớn nhất chia theo kênh · bảng Kênh × Nước (kèm ngày có dữ liệu đến) · bảng Nhóm SP (doanh số từng kênh, spend, TACoS, số SKU hết / sắp hết hàng, DS mất ước tính 90 ngày).

## Shopify (website)

Nút **Shopify**: store DHIntra.com (CA), Megsu.com (US), Tranquillo (AU). Tab *Tổng quan* (KPI, doanh số theo store, khách mới / quay lại, nguồn đơn, top sản phẩm), *Sản phẩm* (theo SKU hoặc nhóm SP, kèm kỳ trước và tồn kho cả nước) và *Chi phí QC* (nhập tay theo tháng).

| Quy ước | Chi tiết |
|---|---|
| Nguồn | `s__shopify_orders_v2`, `s__shopify_order_details_v2` (lấy qua API, DWH cập nhật lại 3 tháng gần nhất mỗi ngày), `s__shopify_order_refund_line_items`. Không chép email, địa chỉ của khách. Bảng cũ `s__shopify_orders` có trạng thái sai nên không dùng. |
| Doanh số | `price × quantity − discount_allocations_amount` (giảm giá cấp đơn đã chia về dòng). Chưa trừ hoàn tiền, chưa gồm thuế / phí ship. Bỏ đơn `voided`. USD theo tỷ giá ngày đặt. |
| Ngày | `DATE(created_at)` như nguồn lưu, khớp báo cáo doanh số của backend. |
| Hoàn tiền | tiền hàng đã hoàn của dòng (`refund_line_items.subtotal`), tính vào ngày đặt đơn. |
| Khách mới | đơn đầu tiên của `customer_id` trong store. Đơn có từ 01/2025, nên khách mua trước đó bị tính là khách mới. Đơn không có mã khách = *Không rõ*. |
| Nguồn đơn | `source_name`: web, Shopify Collective, đơn tạo tay, Faire, eBay… Nguồn chỉ là mã số được hiện là *App #…*. |
| Chi phí QC | DWH chưa có bảng Google / Meta nên team nhập tay ở tab *Chi phí QC*: tổng cả tháng (USD) theo store × nền tảng (Google, Meta, Khác), lưu ở `cfg_shop_ad_spend`. Báo cáo chia đều số của tháng cho các ngày trong tháng; store / tháng chưa nhập tính là 0, kỳ không có tháng nào được nhập thì để trống. Chỉ có TACoS (chi phí ÷ doanh số), không có ACoS. Lọc nhóm SP / brand thì không tính chi phí (chi phí theo store, không theo sản phẩm). |
| Chưa có | traffic / sessions nên chưa có CVR. |

`fact_shop_line` được dựng lại toàn bộ mỗi lần ETL (`etl/sql/77_shop_sales.sql`, vài nghìn đơn).

## Quảng cáo Wayfair

Nút **Amazon / Wayfair** ở góc trên chuyển giữa hai bộ báo cáo. Wayfair dùng chung web app, bộ lọc Nhóm SP / Brand / tên campaign, từ điển từ khóa và cách xuất HTML với Amazon.

| Quy ước | Chi tiết |
|---|---|
| Nguồn | Sponsored Products: `sem_wayfair__wsp_campaign`, `_wsp_product` (campaign Product Targeting theo listing), `_wsp_keyword_targeting` (keyword × listing), `_wsp_keyword_optimization` (keyword × search term), `_wsp_search_term_research` (share of search), `_campaign_info_daily` (trạng thái, daily cap), `_keyword_info_daily` (max bid). Sponsored Shop đã ngừng từ 11/2025 nên không nạp. |
| Doanh số | `sales` = doanh số quy đổi theo **giá sỉ** (`attr_wholesale_cost`, tiền Wayfair trả công ty), dùng cho ACoS, ROAS, TACoS. Doanh số giá lẻ (`attr_rsales`) hiển thị ở cột phụ. |
| Cửa sổ quy đổi | View-through 14 ngày, mặc định của Wayfair. Không so trực tiếp ACoS Wayfair với Amazon. |
| Thị trường, tiền tệ | Theo store hiển thị quảng cáo: wayfair.com = US (USD), wayfair.ca = CA (CAD), quy USD theo tỷ giá ngày. Bộ lọc Tài khoản có dạng "Arozu - US". |
| Tổng doanh số (TACoS) | `s__wayfair_orders` + `s__wayfair_order_details`: `wholesale_price × (quantity − cancelled_quantity)`, gồm dropship và CastleGate, bỏ PO CANCELLED/REJECTED và REPLACEMENT, theo ngày `po_date` và nước của khách. Chỉ chép về các cột cần dùng, không chép tên/địa chỉ khách. |
| Listing → sản phẩm | Listing = Wayfair SKU × tài khoản, gồm nhiều biến thể. Map theo `wayfair_map_sku_product_id`, `sem_wayfair_map_sku_product_id`, sau đó đến part number của listing trong `prd_wayfair_products`. Sản phẩm đại diện là biến thể bán nhiều unit nhất; campaign thuộc các nhóm SP theo tỷ trọng spend của listing (`map_wf_campaign_group`). |
| Từ khóa | `term_id` dùng cùng quy tắc với Amazon (12 ký tự đầu MD5 của chữ thường), nên keyword và search term Wayfair dùng chung `dim_term`, bộ phân loại, n-gram và từ điển. Match type của Wayfair là Smart Exact / Smart Phrase. Report keyword không có Units. |

**Tab:** Tổng quan (KPI, xu hướng, theo tài khoản kèm TACoS, theo loại targeting, doanh số Dropship/CastleGate) · Campaign · Listing / Nhóm SP (kèm TACoS) · Keyword (kèm max bid) · Search term · Phân tích từ khóa · N-gram · Thêm / Phủ định (gợi ý thêm thành Smart Exact) · Share of search (thị phần hiển thị trên trang 1 / top 8 so với spend QC) · Ngân sách.

**Thời gian chạy:** các bảng `sem_wayfair__wsp_*` ở DWH không có index theo ngày. Mỗi lần ETL quét toàn bộ mỗi bảng một lần; riêng keyword optimization (~22 triệu dòng) mất khoảng 5 phút. Nên nhờ team data thêm index `campaign_date_run` / `report_date`.

## Tồn kho & dự kiến hết hàng

Nút **Tồn kho** ở góc trên. Tồn kho là ảnh chụp mới nhất, làm mới mỗi lần ETL chạy; khoảng ngày chỉ áp cho tab *Bán theo kênh / nước*. Bộ lọc Nhóm SP / Brand dùng chung.

**Nút tồn kho:**

| Nút | Gồm | Doanh số trừ vào |
|---|---|---|
| `POOL-<nước>` | Các kho nội bộ / 3PL thật của nước (US, CA, AU). Kho ảo Direct Import vẫn hiện ở tab Tổng quan nhưng không được tính. | FBM, dropship (Wayfair…), website, eBay, Walmart MKP, bán sỉ |
| `CG-<tài khoản>` | Wayfair CastleGate của tài khoản (gộp các kho CG; chi tiết từng kho ở tab *CastleGate theo kho*) | Kênh Wayfair … CG |
| `FBA-<kênh>` | Amazon FBA. **Chưa có số tồn** vì báo cáo MYI ở DWH đã ngừng cập nhật. | Kênh Amazon … FBA |
| `ALL-<nước>` | Cả nước = POOL + CG (chưa gồm FBA) | Các kênh của POOL + CG |

Kênh bán → nút theo `s_sales_channels` (`map_channel_node`).

| Dữ liệu | Nguồn |
|---|---|
| Tồn kho nội bộ | `wh_product_inventory_available` (on-hand − giữ cho đơn đang mở, ngày mới nhất), bổ sung từ `wh_product_inventory` |
| Tồn CastleGate | `wh_wayfair_castlegate_inventory`: on hand, bán được (fulfillable), đang gửi lên (on order) |
| Doanh số theo kênh | `s_sales_report_data_by_orderdate`. Combo được tách ra sản phẩm con (`prd_productcombo`, tối đa 2 cấp); doanh thu combo chia theo tỷ lệ số lượng. |
| Lịch sử tồn (ngày còn hàng) | `wh_product_inventory_trace` (POOL), `wh_wayfair_castlegate_inventory_history` (CG) |
| Hàng đang về | **PO** còn mở (trạng thái 1–3) trừ phần đã đóng container (`sc_delivery_receipt_containers`), chưa biết về nước nào nên không tính vào dự báo · **Container** chưa nhập kho (Startup / trên biển / đã cập cảng), ETA về kho · **FBA**: shipment chưa nhận xong (đã gửi − Amazon đã nhận; "đang chuẩn bị" = hàng còn ở kho nội bộ) · **CastleGate**: `qty_on_order` của Wayfair, chưa có ETA nên giả định 14 ngày. Bảng inbound shipment CastleGate của backend không cập nhật số đã nhận nên không dùng. |

**Cách tính** (`etl/inventory.py`):
- Ngày tính là ngày sau ngày có doanh số cuối cùng, thường là hôm nay.
- **Tốc độ bán / ngày** = 25% tốc độ 7 ngày + 50% tốc độ 30 ngày + 25% tốc độ 90 ngày. Mỗi tốc độ = units / số ngày còn hàng trong cửa sổ, tối thiểu ¼ cửa sổ để vài ngày còn hàng không thổi phồng tốc độ.
- **Mô phỏng từng ngày** trong 180 ngày: cộng hàng về theo ETA (ETA đã qua = về hôm nay; quá hạn trên 60 ngày coi là dữ liệu cũ, bỏ qua) và trừ tốc độ bán. Ngày đầu tiên không đủ hàng bán = **ngày dự kiến hết hàng**.
- **Trạng thái** theo số ngày đủ bán với tồn khả dụng hiện tại: Hết hàng · Nguy cấp < 14 · Thấp < 30 · Ổn < 90 · Tồn nhiều ≥ 90 · Không bán 90 ngày.
- **Thiếu để đủ 60 ngày** = tốc độ × 60 − tồn khả dụng − hàng về trong 60 ngày.

**Tab:** Tổng quan (theo nước, theo nút, từng kho, hàng đang về) · Dự kiến hết hàng (chọn nút / nước / trạng thái) · Bán theo kênh / nước (units theo FBA / CastleGate / dropship / FBM / website, kèm tồn cả nước) · Hàng đang về · CastleGate theo kho.

**Đồ thị** (mỗi tab 1–2 đồ thị, bảng chi tiết thu gọn bên dưới; bấm đồ thị để lọc bảng, bảng tự mở ra):
- Tổng quan: *Sức khỏe tồn kho theo nước* (số SKU theo trạng thái; bấm → sang tab Dự kiến hết hàng đã lọc nước + trạng thái) · *Số ngày đủ bán theo nút* (vạch 14 / 30 ngày; bấm → SKU của nút).
- Dự kiến hết hàng: *Lịch đứt hàng* 20 SKU có doanh số mất ước tính 90 ngày lớn nhất (xanh = còn đủ bán, đỏ = đứt hàng, ◆ = lô hàng kế tiếp về) · *Đường tồn dự kiến* của SKU đang chọn: 60 ngày tồn on-hand thực tế + 120 ngày mô phỏng, ▲ = hàng về (`GET /api/inv/series?node_id=&product_id=`). Bấm một dòng ở lịch hoặc trong bảng để chọn SKU.
- Bán theo kênh / nước: units theo tuần theo hình thức bán · tỷ trọng hình thức bán theo nước.
- Hàng đang về: hàng về theo tuần (theo nguồn, có cột "Quá ETA") · pipeline theo giai đoạn.
- CastleGate theo kho: on hand theo kho CG, chia theo tài khoản.

**Đơn vị Units / Container 40HQ** (ô *Đơn vị* trên thanh lọc của Tồn kho): ở chế độ container, mọi số lượng (tồn, đang về, đã bán, tốc độ bán, lượng thiếu) được quy theo thể tích từng sản phẩm `prd_product.volume` (CBM/unit) ÷ `INV_CONTAINER_CBM` (mặc định 68 CBM, khớp mức đóng thực tế 66–74 CBM của container 40ft). Số ngày, tiền và số SKU không đổi. SKU chưa có thể tích (khoảng 4% số unit tồn) được tính là 0.

**Doanh số mất ước tính** = unit thiếu trong 90 ngày tới (mô phỏng từng ngày) × giá bán trung bình USD/unit 90 ngày qua của nút.

**Chưa làm:** tồn FBA (cần nhờ team DWH sửa task MYI, kéo qua SP-API, hoặc upload file), cảnh báo SKU sắp hết hàng mà đang chạy QC, gợi ý chuyển hàng nội bộ → FBA / CastleGate.

## Gửi tin cho PIC (Google Chat)

Mỗi tối, sau khi ETL chạy xong, mỗi PIC nhận một bản tóm tắt về các nhóm sản phẩm mình phụ trách (`app/notify/`).

- **PIC là ai:** lấy từ phân công nhóm sản phẩm ở backend (`staging.prd_product_assigned`, phiên bản mới nhất của mỗi bản ghi), cộng với `s_users`. Từ `s_users` chỉ đồng bộ 7 cột: id, tên, email, mã NV, quản lý, loại, trạng thái. Kết quả nằm ở `ads_mart.dim_pic` và `map_group_pic`.
- **Nội dung:** mỗi tin gồm phần **Amazon** và phần **Wayfair** (Wayfair tính doanh số, ACoS theo giá sỉ). Mỗi phần có KPI 7 ngày so với 7 ngày trước (Spend, doanh số QC, ACoS, Orders, CVR, TACoS) và các cảnh báo (tối đa 3 dòng mỗi cảnh báo):
  - campaign tiêu từ $20 trở lên mà không có đơn;
  - campaign có ACoS cao hơn mục tiêu;
  - search term tiêu từ `NOTIFY_WASTE_SPEND` trở lên mà không có đơn (14 ngày);
  - search term nên thêm thành Exact (Amazon) / Smart Exact (Wayfair);
  - campaign hết ngân sách nhưng ACoS tốt.

  Kỳ báo cáo của từng kênh bỏ `NOTIFY_LAG_DAYS` ngày gần nhất (tính từ ngày dữ liệu mới nhất của kênh đó) vì đơn quy đổi về trễ. Nhóm SP không chạy QC ở một kênh thì phần đó chỉ có một dòng. ACoS mục tiêu của PIC áp cho cả hai kênh.
- **Gửi riêng từng người:** webhook Google Chat chỉ gửi được vào một space, nên mỗi PIC dùng một space riêng có webhook riêng. Cách cài:
  1. Trong Google Chat, mở space → Apps & integrations → Webhooks.
  2. Sao chép URL webhook và dán vào mục **Gửi tin PIC** (nút trên thanh đầu trang, cạnh Amazon / Wayfair / Tồn kho).
  3. Bấm **Gửi thử** để kiểm tra.
  4. Tick **Nhận tin** để đưa PIC vào lịch gửi.

  Ứng dụng chỉ nhận URL dạng `https://chat.googleapis.com/v1/spaces/…`. URL này không bao giờ được gửi ngược ra trình duyệt.
- **Lịch gửi:** `scripts/run_etl_daily.cmd` chạy `python -m app.notify.run` sau khi ETL thành công. Bước này chỉ gửi khi `.env` có `NOTIFY_ENABLED=true`, và mỗi PIC nhận tối đa một tin mỗi ngày. Lịch sử gửi lưu ở `ads_mart.notify_log`.

```bash
.venv/Scripts/python -m app.notify.run --dry-run
```

## Phân tích từ khóa

Mỗi search term và keyword được chuẩn hóa (viết thường, bỏ dấu nháy, đưa về số ít), sau đó phân loại theo thứ tự ưu tiên:

1. Biểu thức target → `AUTO` (close/loose-match, substitutes, complements), `PRODUCT_TARGET` (asin=), `CATEGORY_TARGET`, `AUDIENCE` (SD)
2. Search term là ASIN → `ASIN_OWN` / `ASIN_COMPETITOR`
3. Ghi đè thủ công (`dict_term_override`)
4. Chứa brand của mình / đối thủ (`dict_brand`) → `BRANDED` / `COMPETITOR`
5. Chứa thuộc tính (`dict_attribute`), hoặc có con số/kích thước → `TARGETED` (Mục tiêu)
6. Chỉ gồm từ loại sản phẩm (`dict_product_term`) → `GENERIC` (Chung)
7. Còn lại: số từ không tính stop-word ≤ `GENERIC_MAX_WORDS` (mặc định 2) → `GENERIC`, ngược lại → `TARGETED`

Số từ (cột Số từ: 1 / 2 / 3 / 4 / 5+) đếm mọi từ trong search term. N-gram 1–3 từ được tách sau khi bỏ stop-word. Mỗi cụm n-gram nhận toàn bộ số liệu của search term chứa nó, nên **không cộng tổng** các dòng n-gram; chỉ so sánh tỷ lệ như ACoS và CVR.

Từ điển brand được nạp sẵn từ `prd_brands`. Team bổ sung brand đối thủ, thuộc tính, từ loại sản phẩm và stop-word trên tab *Từ điển từ khóa*, rồi bấm *Phân loại lại* để áp dụng cho dữ liệu đã có.

## Giá bán SKU (xuất Excel)

```
.venv\Scripts\python.exe -m etl.sku_prices                 # 365 ngày đến hết hôm qua
.venv\Scripts\python.exe -m etl.sku_prices --days 90 --end 2026-10-01 --out exports\gia_q3.xlsx
```

File mặc định nằm ở `exports\gia_ban_sku_<từ>_<đến>.xlsx`, gồm 3 sheet: *Tổng hợp* (mỗi dòng = SKU × kênh × tài khoản × fulfillment: số đơn, units, median, mode, median USD), *Median theo ngày*, *Ghi chú* (định nghĩa giá từng kênh).

| Kênh | Giá đơn vị | Nguồn |
|---|---|---|
| Amazon | (item_price − promotion_discount) / quantity_ordered, bỏ Canceled | bản sao staging nội bộ |
| Wayfair | wholesale_price (giá sỉ bán cho Wayfair, không phải giá khách lẻ), units = quantity − cancelled_quantity | DWH nguồn |
| Walmart | charge_amount / order_quantity (dòng PRODUCT) | DWH nguồn |
| eBay | transaction_price | DWH nguồn |

Median/mode tính theo units; USD quy đổi từng dòng theo tỷ giá ngày đặt hàng. Script không ghi gì vào DWH hay mart.

## Lưu ý dữ liệu nguồn

- `s_sales_traffic_amazon` dừng cập nhật từ 2026-06-11, nên chưa có sessions/CVR traffic. TACoS vẫn tính được vì lấy tổng doanh số từ bảng orders.
- `s_brand_search_query_*` mới là dữ liệu thử (1–2 ASIN), nên chưa có lượng tìm kiếm hay thị phần của từ khóa.
- `finance__product_ads_payment_ev` dừng từ 2025-08, nên chưa đối soát được chi phí quảng cáo thực trừ.
- Các bảng report `sem__*` lớn và không có index theo `report_date`. Mỗi lần ETL sẽ quét toàn bảng. Nên đề nghị team data thêm index:
  `ALTER TABLE staging.sem__sp_targeting ADD INDEX idx_report_date (report_date);` (tương tự cho `sem__sp_search_term`, `sem__sp_advertised_product`, `sem__sb_*`, `sem__sdp_*`, `sem__campaigns_base_daily`).

## Kiểm thử

- Unit test: `.venv/Scripts/python -m pytest -q tests` (bộ phân loại, audit, Shopify / Tổng hợp…)
- Kiểm thử đầu-cuối trên MySQL Docker. `tests/integration/staging_schema.sql` được sinh từ từ điển dữ liệu; `seed_staging.py` tạo dữ liệu thử có kiểm soát; `run_e2e.py` chạy ETL hai lần (kiểm tra idempotent), đối chiếu số liệu và gọi mọi API.
  ```bash
  .venv/Scripts/python -m tests.integration.run_e2e
  ```
  Cần container `mysql:8.0` chạy ở cổng 33306, với mật khẩu ghi trong `tests/integration/test.env`. Chạy web app trên DB thử: `python -m tests.integration.serve_test` (cổng 8010).
- Kiểm thử bước đồng bộ, chạy sau `run_e2e`: giả lập DWH là schema `staging`, đồng bộ về `staging_local`, tổng hợp vào `ads_mart_sync`, rồi so sánh với `ads_mart` phải khớp tuyệt đối.
  ```bash
  .venv/Scripts/python -m tests.integration.run_sync_e2e
  ```

## Cấu trúc

```
app/        main.py · config.py · db.py · filters.py · metrics.py · reports.py · reports_wf.py · reports_inv.py
            reports_shop.py (Shopify) · reports_all.py (Tổng hợp)
            keywords/ (normalize, classifier) · routers/ (api, dictionaries, export)
            static/ (index.html, app.js, export_charts.js, styles.css) · templates/export.html
etl/        run.py · sync_staging.py · terms.py · inventory.py · sql/00_schema … 90_inventory.sql (15/35/75/85 = Wayfair, 76/90 = tồn kho, 77 = Shopify)
tests/      test_classifier.py · integration/
```
