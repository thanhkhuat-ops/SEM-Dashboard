/* SaleSappV2 – giao diện báo cáo quảng cáo Amazon / Wayfair */
(function () {
  'use strict';

  var TABS = [
    { id: 'overview', label: 'Tổng quan', report: 'overview' },
    { id: 'campaigns', label: 'Campaign', report: 'campaigns',
      controls: [{ name: 'level', label: 'Cấp', type: 'select', options: [['campaign', 'Campaign'], ['adgroup', 'Ad group']] }] },
    { id: 'targets', label: 'Keyword / Target', report: 'targets', kw: true },
    { id: 'search_terms', label: 'Search term', report: 'search_terms', kw: true,
      controls: [{ name: 'level', label: 'Gộp theo', type: 'select', options: [['term', 'Search term'], ['target', 'Search term × Keyword']] }] },
    { id: 'keyword_analysis', label: 'Phân tích từ khóa', report: 'keyword_analysis', kw: true,
      controls: [{ name: 'source', label: 'Nguồn', type: 'select', options: [['search_term', 'Search term khách gõ'], ['keyword', 'Keyword đặt giá thầu']] }] },
    { id: 'ngrams', label: 'N-gram', report: 'ngrams', kw: true,
      controls: [{ name: 'n', label: 'Độ dài cụm', type: 'select', options: [['1', '1 từ'], ['2', '2 từ'], ['3', '3 từ']] },
                 { name: 'min_clicks', label: 'Click tối thiểu', type: 'number', value: 5 }] },
    { id: 'audit', label: 'Audit từ khóa' },
    { id: 'harvest', label: 'Thêm / Phủ định', report: 'harvest', kw: true,
      controls: [{ name: 'min_orders', label: 'Đơn tối thiểu', type: 'number', value: 2 },
                 { name: 'max_acos', label: 'ACoS tối đa', type: 'number', value: 0.3, step: 0.05 },
                 { name: 'neg_clicks', label: 'Click không đơn', type: 'number', value: 15 },
                 { name: 'neg_spend', label: 'Spend tối thiểu ($)', type: 'number', value: 20 }] },
    { id: 'products', label: 'Sản phẩm', report: 'products',
      controls: [{ name: 'level', label: 'Cấp', type: 'select', options: [['product', 'Sản phẩm'], ['asin', 'ASIN'], ['group', 'Nhóm SP']] }] },
    { id: 'halo', label: 'Halo', report: 'halo' },
    { id: 'placements', label: 'Placement SB', report: 'placements' },
    { id: 'budget', label: 'Ngân sách', report: 'budget' },
    { id: 'costs', label: 'Giá vốn & phí' },
    { id: 'month_targets', label: 'Mục tiêu tháng' },
    { id: 'dict', label: 'Từ điển từ khóa' },
    { id: 'audit_rules', label: 'Quy tắc audit' }
  ];
  TABS.forEach(function (t) { t.channel = 'amazon'; });

  var WF_TABS = [
    { id: 'wf_overview', label: 'Tổng quan', report: 'wf_overview' },
    { id: 'wf_campaigns', label: 'Campaign', report: 'wf_campaigns' },
    { id: 'wf_products', label: 'Listing / Nhóm SP', report: 'wf_products',
      controls: [{ name: 'level', label: 'Cấp', type: 'select', options: [['listing', 'Listing (Wayfair SKU)'], ['group', 'Nhóm SP']] }] },
    { id: 'wf_keywords', label: 'Keyword', report: 'wf_keywords', kw: true,
      controls: [{ name: 'level', label: 'Cấp', type: 'select', options: [['keyword', 'Keyword'], ['listing', 'Keyword × Listing']] }] },
    { id: 'wf_search_terms', label: 'Search term', report: 'wf_search_terms', kw: true,
      controls: [{ name: 'level', label: 'Gộp theo', type: 'select', options: [['term', 'Search term'], ['keyword', 'Search term × Keyword']] }] },
    { id: 'wf_keyword_analysis', label: 'Phân tích từ khóa', report: 'wf_keyword_analysis', kw: true,
      controls: [{ name: 'source', label: 'Nguồn', type: 'select', options: [['search_term', 'Search term khách gõ'], ['keyword', 'Keyword đặt giá thầu']] }] },
    { id: 'wf_ngrams', label: 'N-gram', report: 'wf_ngrams', kw: true,
      controls: [{ name: 'n', label: 'Độ dài cụm', type: 'select', options: [['1', '1 từ'], ['2', '2 từ'], ['3', '3 từ']] },
                 { name: 'min_clicks', label: 'Click tối thiểu', type: 'number', value: 5 }] },
    { id: 'wf_audit', label: 'Audit từ khóa' },
    { id: 'wf_harvest', label: 'Thêm / Phủ định', report: 'wf_harvest', kw: true,
      controls: [{ name: 'min_orders', label: 'Đơn tối thiểu', type: 'number', value: 2 },
                 { name: 'max_acos', label: 'ACoS tối đa', type: 'number', value: 0.3, step: 0.05 },
                 { name: 'neg_clicks', label: 'Click không đơn', type: 'number', value: 15 },
                 { name: 'neg_spend', label: 'Spend tối thiểu ($)', type: 'number', value: 20 }] },
    { id: 'wf_share_of_search', label: 'Share of search', report: 'wf_share_of_search', kw: true,
      controls: [{ name: 'min_impr', label: 'Impr 30 ngày tối thiểu', type: 'number', value: 100 }] },
    { id: 'wf_budget', label: 'Ngân sách', report: 'wf_budget' },
    { id: 'costs', label: 'Giá vốn & phí' },
    { id: 'month_targets', label: 'Mục tiêu tháng' },
    { id: 'dict', label: 'Từ điển từ khóa' },
    { id: 'wf_audit_rules', label: 'Quy tắc audit' }
  ];
  WF_TABS.forEach(function (t) { t.channel = 'wayfair'; });

  var INV_TABS = [
    { id: 'inv_overview', label: 'Tổng quan', report: 'inv_overview',
      controls: [{ name: 'loc', label: 'Vị trí tồn', type: 'select', options: [['', 'Tất cả (trong kho + đang về)'],
                   ['STOCK', 'Đã nằm trong kho'], ['LOCAL', '— Kho nội bộ'], ['CG', '— CastleGate'], ['FBA', '— FBA'],
                   ['PIPE', 'Đang về / đang gửi'], ['FBA_IN', '— Đang gửi lên FBA (inbound)'],
                   ['CG_IN', '— Đang gửi lên CastleGate'], ['CONTAINER', '— Container về kho (incoming)'],
                   ['PO', '— PO chưa đóng container']] },
                 { name: 'country', label: 'Nước', type: 'select', options: [['', 'Tất cả'], ['US', 'US'], ['CA', 'CA'], ['AU', 'AU']] }] },
    { id: 'inv_products', label: 'Dự kiến hết hàng', report: 'inv_products',
      controls: [{ name: 'node', label: 'Nút tồn kho', type: 'select', options: [['ALL', 'Cả nước (nội bộ + CastleGate + FBA)'],
                   ['POOL', 'Kho nội bộ'], ['CG', 'CastleGate'], ['FBA', 'FBA'], ['', 'Mọi nút']] },
                 { name: 'country', label: 'Nước', type: 'select', options: [['', 'Tất cả'], ['US', 'US'], ['CA', 'CA'], ['AU', 'AU']] },
                 { name: 'status', label: 'Trạng thái', type: 'select', options: [['RISK', 'Hết / nguy cấp / thấp'], ['', 'Tất cả'],
                   ['OOS', 'Hết hàng'], ['CRITICAL', 'Nguy cấp < 14 ngày'], ['LOW', 'Thấp < 30 ngày'], ['OK', 'Ổn'],
                   ['OVER', 'Tồn nhiều ≥ 90 ngày'], ['NO_SALES', 'Không bán 90 ngày']] }] },
    { id: 'inv_channel_sales', label: 'Bán theo kênh / nước', report: 'inv_channel_sales', dated: true,
      controls: [{ name: 'country', label: 'Nước', type: 'select', options: [['', 'Tất cả'], ['US', 'US'], ['CA', 'CA'], ['AU', 'AU']] }] },
    { id: 'inv_incoming', label: 'Hàng đang về', report: 'inv_incoming',
      controls: [{ name: 'source', label: 'Nguồn', type: 'select', options: [['', 'Tất cả'], ['PO', 'PO (chưa đóng container)'],
                   ['CONTAINER', 'Container'], ['FBA_SHIPMENT', 'Shipment lên FBA'], ['CG_ON_ORDER', 'Đang gửi lên CastleGate']] },
                 { name: 'country', label: 'Nước', type: 'select', options: [['', 'Tất cả'], ['US', 'US'], ['CA', 'CA'], ['AU', 'AU']] }] },
    { id: 'inv_castlegate', label: 'CastleGate theo kho', report: 'inv_castlegate' },
    { id: 'inv_inbound', label: 'Đề xuất inbound', report: 'inv_inbound',
      controls: [{ name: 'target', label: 'Gửi lên', type: 'select', options: [['', 'FBA + CastleGate'], ['FBA', 'FBA'], ['CG', 'CastleGate']] },
                 { name: 'country', label: 'Nước', type: 'select', options: [['', 'Tất cả'], ['US', 'US'], ['CA', 'CA'], ['AU', 'AU']] },
                 { name: 'cover', label: 'Đủ bán (ngày)', type: 'number', value: 45 },
                 { name: 'lt_fba_us', label: 'Gửi FBA US (ngày)', type: 'number', value: 50 },
                 { name: 'lt_fba_ca', label: 'Gửi FBA CA', type: 'number', value: 30 },
                 { name: 'lt_fba_au', label: 'Gửi FBA AU', type: 'number', value: 25 },
                 { name: 'lt_cg', label: 'Gửi CastleGate', type: 'number', value: 21 },
                 { name: 'reserve', label: 'Giữ kho nội bộ (ngày)', type: 'number', value: 10 }] }
  ];
  INV_TABS.forEach(function (t) { t.channel = 'inventory'; });

  // Tổng hợp: mọi kênh trên một trang; Shopify: bán hàng website (chi phí QC nhập tay theo tháng)
  var MATRIX_TABS = [{ id: 'matrix', label: 'Matrix Chart', report: 'matrix', matrix: true, channel: 'matrix' }];
  var ALL_TABS = [{ id: 'all_overview', label: 'Tổng quan', report: 'all_overview', channel: 'all',
    controls: [{ name: 'compare', label: 'So sánh với', type: 'select',
                 options: [['prev', 'Kỳ liền trước'], ['month', 'Cùng kỳ tháng trước'], ['year', 'Cùng kỳ năm trước']] }] },
    { id: 'pnl_overview', label: 'Lợi nhuận (P&L)', report: 'pnl_overview', channel: 'all',
      controls: [{ name: 'compare', label: 'So sánh với', type: 'select',
                   options: [['prev', 'Kỳ liền trước'], ['month', 'Cùng kỳ tháng trước'], ['year', 'Cùng kỳ năm trước']] }] }];
  var SHOP_TABS = [
    { id: 'shop_overview', label: 'Tổng quan', report: 'shop_overview' },
    { id: 'shop_products', label: 'Sản phẩm', report: 'shop_products',
      controls: [{ name: 'level', label: 'Cấp', type: 'select', options: [['product', 'Sản phẩm (SKU)'], ['group', 'Nhóm SP']] }] },
    { id: 'shop_ad_spend', label: 'Chi phí QC' }
  ];
  SHOP_TABS.forEach(function (t) { t.channel = 'shopify'; });

  // gửi tin PIC là mục riêng (một tin gồm cả Amazon và Wayfair), không có bộ lọc báo cáo
  var NOTIFY_TABS = [{ id: 'notify', label: 'Gửi tin PIC', channel: 'notify' }];

  // nhóm tab (thanh tab có vạch chia + nhãn nhóm; mobile dùng ô chọn có nhóm). Tab không có nhóm đứng riêng.
  var TAB_GROUPS = {
    campaigns: 'Hiệu suất', products: 'Hiệu suất', halo: 'Hiệu suất', placements: 'Hiệu suất', budget: 'Hiệu suất',
    targets: 'Từ khóa', search_terms: 'Từ khóa', audit: 'Từ khóa', keyword_analysis: 'Từ khóa', ngrams: 'Từ khóa', harvest: 'Từ khóa',
    dict: 'Công cụ', costs: 'Công cụ', month_targets: 'Công cụ', audit_rules: 'Công cụ',
    wf_campaigns: 'Hiệu suất', wf_products: 'Hiệu suất', wf_budget: 'Hiệu suất',
    wf_keywords: 'Từ khóa', wf_search_terms: 'Từ khóa', wf_keyword_analysis: 'Từ khóa', wf_ngrams: 'Từ khóa',
    wf_harvest: 'Từ khóa', wf_share_of_search: 'Từ khóa', wf_audit: 'Từ khóa', wf_audit_rules: 'Công cụ'
  };
  var GROUP_ORDER = ['', 'Hiệu suất', 'Từ khóa', 'Công cụ'];
  function groupedTabs() {
    var tabs = channel().tabs;
    return GROUP_ORDER.map(function (g) {
      return { name: g, tabs: tabs.filter(function (t) { return (t.channel !== 'inventory' && TAB_GROUPS[t.id] || '') === g; }) };
    }).filter(function (g) { return g.tabs.length; });
  }

  var CHANNELS = {
    all: { brand: 'Tổng hợp', tabs: ALL_TABS, first: 'all_overview', fresh: ['total_sales', 'wf_total_sales', 'shop_sales'],
           freshLabels: ['Amazon đến ', 'Wayfair đến ', 'Shopify đến '],
           hint: 'Tiền tệ USD · Amazon giá lẻ, Wayfair giá sỉ, Shopify sau giảm giá · Spend QC gồm Amazon, Wayfair và chi phí Shopify nhập tay' },
    amazon: { brand: 'Amazon Ads', tabs: TABS, first: 'overview', fresh: ['campaign', 'total_sales'],
              hint: 'Tiền tệ USD · Quy đổi SP 7 ngày, SB/SD 14 ngày' },
    wayfair: { brand: 'Wayfair Ads', tabs: WF_TABS, first: 'wf_overview', fresh: ['wf_campaign', 'wf_total_sales'],
               hint: 'Tiền tệ USD · Doanh số QC, ACoS, ROAS, TACoS theo giá sỉ · Quy đổi view-through 14 ngày' },
    shopify: { brand: 'Shopify', tabs: SHOP_TABS, first: 'shop_overview', fresh: ['shop_sales'], freshLabels: ['Đơn Shopify đến '],
               hint: 'Tiền tệ USD · Doanh số sau giảm giá, chưa trừ hoàn tiền · Chi phí QC nhập tay theo tháng' },
    inventory: { brand: 'Tồn kho', tabs: INV_TABS, first: 'inv_overview', fresh: ['inv_stock', 'inv_sales'],
                 freshLabels: ['Tồn kho tính ngày ', 'Doanh số đến '], freshExtra: [['inv_fba', 'Tồn FBA (sheet) đọc ngày ']],
                 hint: 'Tồn kho là ảnh chụp mới nhất; khoảng ngày chỉ áp cho tab Bán theo kênh / nước · Tồn FBA từ Google Sheet inventory details' },
    matrix: { brand: 'Matrix Chart', tabs: MATRIX_TABS, first: 'matrix', fresh: ['campaign', 'total_sales', 'wf_campaign', 'wf_total_sales'],
              freshLabels: ['QC Amazon đến ', 'DS Amazon đến ', 'QC Wayfair đến ', 'DS Wayfair đến '],
              hint: 'Tiền tệ USD · Tài khoản / Loại QC / Portfolio chỉ áp cho đồ thị Amazon, TK Wayfair chỉ cho đồ thị Wayfair · Wayfair theo giá sỉ' },
    notify: { brand: 'Gửi tin PIC', tabs: NOTIFY_TABS, first: 'notify', fresh: ['campaign', 'wf_campaign'],
              freshLabels: ['QC Amazon đến ', 'QC Wayfair đến '], hint: '', noFilters: true }
  };

  var state = { channel: 'amazon', tab: 'overview', meta: null, charts: [], rowLimit: {} };
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') node.textContent = attrs[k];
      else if (k === 'class') node.className = attrs[k];
      else if (k.slice(0, 2) === 'on') node.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== null && attrs[k] !== undefined) node.setAttribute(k, attrs[k]);  // null = bỏ thuộc tính
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return node;
  }

  function store(key, value) {
    try {
      if (value === undefined) return JSON.parse(localStorage.getItem('ssv2.' + key));
      localStorage.setItem('ssv2.' + key, JSON.stringify(value));
    } catch (e) { return null; }
  }

  // ---------- định dạng ----------
  // trạng thái campaign từ API (ENABLED…) hiển thị bằng tiếng Việt; giá trị lọc vẫn là mã gốc
  var STATE_LABEL = { ENABLED: 'Đang chạy', PAUSED: 'Tạm dừng', ARCHIVED: 'Lưu trữ', COMPLETED: 'Đã kết thúc',
                      ACTIVE: 'Đang chạy', INACTIVE: 'Tạm dừng',
                      enabled: 'Đang chạy', paused: 'Tạm dừng', archived: 'Lưu trữ', active: 'Đang chạy', inactive: 'Tạm dừng' };
  function cellText(c, v) { return c.key === 'state' && STATE_LABEL[v] ? STATE_LABEL[v] : fmt(v, c.fmt); }
  // ngày hiển thị dd/mm/yyyy (dd/mm trên trục đồ thị); API và URL vẫn dùng ISO
  function isIsoDate(v) { return typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v); }
  function dmy(s) { return isIsoDate(s) ? s.slice(8, 10) + '/' + s.slice(5, 7) + '/' + s.slice(0, 4) : s; }

  function fmt(v, kind) {
    if (v === null || v === undefined || v === '') return '–';
    var n = Number(v);
    switch (kind) {
      case 'int': return isNaN(n) ? v : n.toLocaleString('en-US', { maximumFractionDigits: 0 });
      case 'money': return isNaN(n) ? v : '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      case 'pct': return isNaN(n) ? v : (n * 100).toFixed(1) + '%';
      case 'num2': return isNaN(n) ? v : n.toFixed(2);
      case 'date': return dmy(String(v));
      default: return String(v);
    }
  }

  // ngày tính theo UTC nửa đêm để iso() không lệch một ngày theo múi giờ máy
  function iso(d) { return d.toISOString().slice(0, 10); }
  function today() { var t = new Date(); return new Date(Date.UTC(t.getFullYear(), t.getMonth(), t.getDate())); }
  function addDays(d, n) { var x = new Date(d); x.setUTCDate(x.getUTCDate() + n); return x; }
  function parseIso(s) { return new Date(s + 'T00:00:00Z'); }
  function dayMonth(s) { return s.slice(8, 10) + '/' + s.slice(5, 7); }
  // tồn kho: đếm theo units hay quy ra container 40HQ (server quy đổi theo thể tích sản phẩm)
  function qtyUnit() { return $('#f-qty-unit').value === 'cont' ? 'cont' : 'unit'; }
  function daysAgo(n) { return addDays(today(), -n); }

  // ---------- multi-select ----------
  function buildMultiSelect(box, items) {
    var param = box.dataset.key || box.dataset.param, label = box.dataset.label;
    var saved = store('f.' + param) || [];
    box.innerHTML = '';
    var btn = el('button', { type: 'button', 'aria-haspopup': 'true', 'aria-expanded': 'false' });
    var panel = el('div', { class: 'panel', role: 'group', 'aria-label': label });
    var tools = el('div', { class: 'tools' }, [
      el('button', { type: 'button', class: 'link', text: 'Chọn hết', onclick: function () { setAll(true); } }),
      el('button', { type: 'button', class: 'link', text: 'Bỏ chọn', onclick: function () { setAll(false); } })
    ]);
    panel.appendChild(tools);
    items.forEach(function (it) {
      var cb = el('input', { type: 'checkbox', value: String(it.id) });
      if (saved.indexOf(String(it.id)) >= 0) cb.checked = true;
      cb.addEventListener('change', refresh);
      panel.appendChild(el('label', {}, [cb, it.label]));
    });
    if (!items.length) panel.appendChild(el('div', { class: 'muted', text: 'Chưa có dữ liệu' }));
    function setAll(on) { $$('input', panel).forEach(function (c) { c.checked = on; }); refresh(); box.dispatchEvent(new Event('change', { bubbles: true })); }
    function refresh() {
      var n = $$('input:checked', panel).length;
      btn.textContent = label + (n ? ' (' + n + ')' : ': tất cả') + ' ▾';
      btn.classList.toggle('on', n > 0);
    }
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      $$('.ms.open').forEach(function (o) { if (o !== box) closeMs(o); });
      box.classList.toggle('open');
      btn.setAttribute('aria-expanded', String(box.classList.contains('open')));
    });
    panel.addEventListener('click', function (e) { e.stopPropagation(); });
    box.appendChild(btn);
    box.appendChild(panel);
    refresh();
  }
  function closeMs(box) {
    box.classList.remove('open');
    var b = box.querySelector('button[aria-expanded]');
    if (b) b.setAttribute('aria-expanded', 'false');
  }
  document.addEventListener('click', function () { $$('.ms.open').forEach(closeMs); });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    $$('.ms.open').forEach(function (o) { closeMs(o); o.querySelector('button').focus(); });
    closePickers();
  });

  // ---------- bộ lọc → query string ----------
  function filterParams() {
    var p = new URLSearchParams();
    p.set('start', $('#f-start').value);
    p.set('end', $('#f-end').value);
    $$('.ms').forEach(function (box) {
      if (box.closest('.kw-only') && !currentTab().kw) return;
      if (!channelBox(box)) return;
      var vals = $$('.panel input:checked', box).map(function (c) { return c.value; });
      store('f.' + (box.dataset.key || box.dataset.param), vals);
      vals.forEach(function (v) { p.append(box.dataset.param, v); });
    });
    var q = $('#f-campaign').value.trim();
    if (q && channelBox($('#f-campaign'))) p.set('campaign_q', q);
    if (state.channel === 'inventory') p.set('qty_unit', qtyUnit());
    if (currentTab().report && tfParam()) p.set('tf', tfParam());
    if (state.rowLimit[state.tab]) p.set('limit', state.rowLimit[state.tab]);
    $$('[data-opt]', $('#controls')).forEach(function (inp) {
      if (inp.value !== '') p.set(inp.dataset.opt, inp.value);
      store('o.' + state.tab + '.' + inp.dataset.opt, inp.value);
    });
    store('dates', { preset: $('#f-preset').value, start: $('#f-start').value, end: $('#f-end').value });
    return p;
  }

  // ngày mới nhất có dữ liệu của sàn hiện tại (lấy ngày sớm hơn giữa số liệu QC và doanh số). Ngày đó thường chưa
  // nạp đủ (report Amazon / Wayfair và đơn hàng về trễ) nên coi là "tạm tính"; các preset dừng ở ngày trước đó.
  function provisionalFrom() {
    var f = (state.meta || {}).freshness || {};
    var ds = channel().fresh.map(function (k) { return f[k]; }).filter(Boolean).sort();
    return ds[0] || null;
  }
  function lastComplete() { var p = provisionalFrom(); return p ? addDays(parseIso(p), -1) : daysAgo(1); }
  function datedTab() { var t = currentTab(); return !!t.report && (state.channel !== 'inventory' || !!t.dated); }

  function applyPreset(v) {
    var end = lastComplete(), start, t = today();
    if (v === 'mtd') { start = new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth(), 1)); if (start > end) start = end; }
    else if (v === 'lm') { end = addDays(new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth(), 1)), -1); start = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), 1)); }
    else start = addDays(end, 1 - Number(v));
    $('#f-preset').value = v;
    $('#f-start').value = iso(start);
    $('#f-end').value = iso(end);
  }

  function channel() { return CHANNELS[state.channel]; }
  function currentTab() { return channel().tabs.filter(function (t) { return t.id === state.tab; })[0]; }
  // ô lọc chỉ dành cho một sàn (amz-only / wf-only)
  function channelBox(box) {
    var mx = state.channel === 'matrix';
    if (box.classList.contains('amz-only')) return state.channel === 'amazon' || mx;
    if (box.classList.contains('wf-only')) return state.channel === 'wayfair' || mx;
    if (box.classList.contains('ads-only')) return state.channel === 'amazon' || state.channel === 'wayfair' || mx;
    if (box.classList.contains('mkt-only')) return state.channel === 'all' || state.channel === 'shopify' || mx;
    if (box.classList.contains('all-only')) return state.channel === 'all';
    if (box.classList.contains('inv-only')) return state.channel === 'inventory';
    return true;
  }

  // ---------- sàn, tab & control riêng ----------
  function setChannel(ch) {
    state.channel = CHANNELS[ch] ? ch : 'amazon';
    store('channel', state.channel);
    state.tab = store('tab.' + state.channel) || channel().first;
    if (!currentTab()) state.tab = channel().first;
    $$('#channels button').forEach(function (b) {
      b.classList.toggle('active', b.dataset.channel === state.channel);
      b.setAttribute('aria-pressed', String(b.dataset.channel === state.channel));
    });
    $('#brand-channel').textContent = channel().brand;
    $('#hint').textContent = channel().hint;
    $$('.amz-only, .wf-only, .ads-only, .inv-only, .mkt-only, .all-only').forEach(function (b) { b.style.display = channelBox(b) ? '' : 'none'; });
    // Matrix hiện cả ô lọc Amazon lẫn Wayfair: ghi rõ ô nào của sàn nào
    var MX_LABELS = { profile_id: ['Tài khoản', 'TK Amazon'], ad_type: ['Loại QC', 'Loại QC Amazon'],
                      portfolio_id: ['Portfolio', 'Portfolio Amazon'], wf_account: ['Tài khoản', 'TK Wayfair'] };
    Object.keys(MX_LABELS).forEach(function (param) {
      var box = $('.ms[data-param="' + param + '"]'), want = MX_LABELS[param][state.channel === 'matrix' ? 1 : 0];
      if (!box || box.dataset.label === want) return;
      box.dataset.label = want;
      if (state.lists) buildMultiSelect(box, state.lists[box.dataset.key || param] || []);
    });
    $('#filters').style.display = $('#tabs').style.display = channel().noFilters ? 'none' : '';
    if (state.meta && $('#f-preset').value) applyPreset($('#f-preset').value);  // mỗi sàn có ngày dữ liệu mới nhất riêng
    showFreshness();
  }

  function showFreshness() {
    var f = (state.meta || {}).freshness || {}, k = channel().fresh, l = channel().freshLabels || ['Dữ liệu QC đến ', 'Doanh số đến '];
    // freshExtra: chỉ hiển thị, không dùng để tính ngày tạm tính
    $('#freshness').textContent = state.meta ? k.map(function (key, i) { return l[i] + dmy(f[key] || '–'); })
      .concat((channel().freshExtra || []).map(function (x) { return x[1] + dmy(f[x[0]] || '–'); })).join(' · ') : '';
    var p = provisionalFrom();
    if (p) {
      $('#freshness').title = 'Ngày ' + dayMonth(p) + ' có thể chưa nạp đủ số liệu (tạm tính). Các khoảng chọn nhanh dừng ở ngày trước đó.';
      $('#f-end').max = $('#f-start').max = k.map(function (key) { return f[key]; }).filter(Boolean).sort().pop();
    }
  }

  function goTab(id) { toggleFilters(false); state.tab = id; store('tab.' + state.channel, id); state.navPush = true; renderTabs(); renderControls(); load(); }

  function renderTabs() {
    var nav = $('#tabs'), list = el('div', { class: 'tablist', role: 'tablist', 'aria-label': 'Báo cáo' });
    var pick = el('select', { class: 'tab-select', 'aria-label': 'Chọn báo cáo' });
    nav.innerHTML = '';
    groupedTabs().forEach(function (g, gi) {
      if (gi) list.appendChild(el('span', { class: 'tab-sep', role: 'presentation', 'aria-hidden': 'true' }));
      if (g.name) list.appendChild(el('span', { class: 'tab-group', role: 'presentation', 'aria-hidden': 'true', text: g.name }));
      var holder = g.name ? el('optgroup', { label: g.name }) : pick;
      g.tabs.forEach(function (t) {
        list.appendChild(el('button', { type: 'button', role: 'tab', 'aria-selected': String(t.id === state.tab),
          class: t.id === state.tab ? 'active' : '', text: t.label, title: g.name ? g.name + ' › ' + t.label : t.label,
          onclick: function () { goTab(t.id); } }));
        var o = el('option', { value: t.id, text: t.label });
        if (t.id === state.tab) o.selected = true;
        holder.appendChild(o);
      });
      if (holder !== pick) pick.appendChild(holder);
    });
    pick.addEventListener('change', function () { goTab(pick.value); });
    nav.appendChild(list);
    nav.appendChild(pick);
    $$('.kw-only').forEach(function (r) { r.style.display = currentTab().kw ? '' : 'none'; });
    $('#filters').classList.toggle('no-dates', !datedTab());
    $('#btn-export').style.display = currentTab().report && !currentTab().matrix ? '' : 'none';
  }

  function renderControls() {
    var box = $('#controls');
    box.innerHTML = '';
    (currentTab().controls || []).forEach(function (c) {
      var saved = store('o.' + state.tab + '.' + c.name);
      var input;
      if (c.type === 'select') {
        input = el('select', { 'data-opt': c.name }, c.options.map(function (o) { return el('option', { value: o[0], text: o[1] }); }));
      } else {
        input = el('input', { type: 'number', 'data-opt': c.name, step: c.step || 1, min: 0 });
        input.value = c.value;
      }
      if (saved !== null && saved !== undefined && saved !== '') input.value = saved;
      input.addEventListener('change', load);
      box.appendChild(el('label', {}, [c.label, input]));
    });
  }

  // ---------- tải & hiển thị báo cáo ----------
  function api(url, opts) {
    return fetch(url, opts).then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok) throw new Error(body.detail || ('HTTP ' + r.status));
        return body;
      });
    });
  }

  function announce(text) { var live = $('#live'); if (live) live.textContent = text; }

  function destroyCharts() { state.charts.forEach(function (c) { c.destroy(); }); state.charts = []; state.matrixCharts = []; }

  // ---------- trạng thái trên URL (gửi link cho người khác, nút Back / Forward) ----------
  // URL = kênh + tab + preset (hoặc khoảng ngày) + các tham số báo cáo. Mở một link thì ghi các giá trị đó vào bộ
  // nhớ trình duyệt rồi khởi động như bình thường (hydrateFromUrl).
  function urlParams() {
    var p = new URLSearchParams({ ch: state.channel, tab: state.tab });
    if (!currentTab().report) return p;
    var preset = $('#f-preset').value;
    if (preset) p.set('preset', preset);
    filterParams().forEach(function (v, k) {
      if (!(preset && (k === 'start' || k === 'end'))) p.append(k, v);
    });
    return p;
  }

  function syncUrl() {
    var q = '?' + urlParams().toString(), push = state.navPush;
    state.navPush = false;
    if (q === location.search) return;
    if (push) history.pushState(null, '', q); else history.replaceState(null, '', q);
  }

  function hydrateFromUrl() {
    var p = new URLSearchParams(location.search), ch = p.get('ch');
    if (p.get('tab') === 'notify') ch = 'notify';  // link cũ: Gửi tin PIC từng là tab của Amazon
    if (!CHANNELS[ch]) return false;
    var tab = p.get('tab'), def = CHANNELS[ch].tabs.filter(function (t) { return t.id === tab; })[0];
    store('channel', ch);
    if (def) store('tab.' + ch, tab);
    if (!def || !def.report) return true;  // tab không phải báo cáo (Gửi tin PIC, Từ điển): chỉ cần kênh + tab
    if (p.get('preset')) store('dates', { preset: p.get('preset') });
    else if (p.get('start')) store('dates', { preset: '', start: p.get('start'), end: p.get('end') || p.get('start') });
    $$('.ms').forEach(function (box) {
      if ((box.classList.contains('amz-only') && ch !== 'amazon') || (box.classList.contains('wf-only') && ch !== 'wayfair')) return;
      if (box.classList.contains('mkt-only') && ch !== 'all' && ch !== 'shopify') return;
      if (box.classList.contains('all-only') && ch !== 'all') return;
      if (box.closest('.kw-only') && !def.kw) return;  // URL của tab không có từ khóa không mang bộ lọc từ khóa
      store('f.' + (box.dataset.key || box.dataset.param), p.getAll(box.dataset.param));
    });
    $('#f-campaign').value = p.get('campaign_q') || '';
    if (p.get('qty_unit')) store('qty_unit', p.get('qty_unit'));
    (def.controls || []).forEach(function (c) { if (p.has(c.name)) store('o.' + tab + '.' + c.name, p.get(c.name)); });
    var tf = {};
    try { tf = JSON.parse(p.get('tf') || '{}') || {}; } catch (e) { tf = {}; }
    store('tf.' + tab, tf);
    delete state.tf[tab];
    if (p.get('limit')) state.rowLimit[tab] = Number(p.get('limit')); else delete state.rowLimit[tab];
    return true;
  }

  function restoreDates() {
    var dates = store('dates');
    if (dates && dates.preset) applyPreset(dates.preset);
    else if (dates && dates.start) { $('#f-preset').value = ''; $('#f-start').value = dates.start; $('#f-end').value = dates.end; }
    else applyPreset('30');
  }

  function rebuildFilters() {
    $$('.ms').forEach(function (box) { buildMultiSelect(box, (state.lists || {})[box.dataset.key || box.dataset.param] || []); });
    $('#f-qty-unit').value = store('qty_unit') === 'cont' ? 'cont' : 'unit';
  }

  // khung xám giữ chỗ trong lúc chờ báo cáo (không làm trang nhảy khi dữ liệu về)
  function skeleton() {
    var box = el('div', { class: 'skeleton', 'aria-hidden': 'true' }), k = el('div', { class: 'kpis' });
    for (var i = 0; i < 4; i++) k.appendChild(el('div', { class: 'kpi sk sk-kpi' }));
    box.appendChild(k);
    box.appendChild(el('div', { class: 'sk sk-chart' }));
    for (var j = 0; j < 6; j++) box.appendChild(el('div', { class: 'sk sk-row' }));
    return box;
  }

  // ---------- bộ lọc: tóm tắt khi thu gọn (mobile) và trạng thái "đã đổi, chưa áp dụng" ----------
  function activeFilterCount() {
    var n = $$('.ms').filter(function (box) {
      return channelBox(box) && !(box.closest('.kw-only') && !currentTab().kw) && box.querySelector('button.on');
    }).length;
    return n + (channelBox($('#f-campaign')) && $('#f-campaign').value.trim() ? 1 : 0);
  }
  function updateFilterSummary() {
    var n = activeFilterCount(), a = $('#f-start').value, b = $('#f-end').value;
    $('#f-summary').textContent = (!datedTab() ? 'không theo ngày' : a && b ? dayMonth(a) + '–' + dayMonth(b) : '') + (n ? ' · ' + n + ' bộ lọc' : '') +
      ($('#btn-apply').classList.contains('dirty') ? ' · chưa áp dụng' : '');
  }
  function setDirty(on) {
    var btn = $('#btn-apply');
    btn.classList.toggle('dirty', on);
    btn.textContent = on ? 'Xem báo cáo (đã đổi bộ lọc)' : 'Xem báo cáo';
    updateFilterSummary();
  }
  function toggleFilters(open) {
    $('#filters').classList.toggle('expanded', open);
    $('#f-toggle').setAttribute('aria-expanded', String(open));
  }

  function renderError(content, tab, e) {
    var msg = e && e.message || String(e), why;
    if (e instanceof TypeError) why = 'Không kết nối được server. Kiểm tra server còn chạy không rồi thử lại.';
    else if (/Không có báo cáo/.test(msg)) why = 'Server đang chạy phiên bản cũ, chưa có báo cáo này. Khởi động lại server rồi thử lại.';
    else why = 'Có thể do kết nối cơ sở dữ liệu hoặc bộ lọc không hợp lệ. Thử lại; nếu vẫn lỗi, gửi chi tiết bên dưới cho người quản trị.';
    content.innerHTML = '';
    content.appendChild(el('div', { class: 'error', role: 'alert' }, [
      el('strong', { text: 'Không tải được báo cáo "' + tab.label + '".' }),
      el('p', { text: why }),
      el('button', { type: 'button', class: 'primary', text: 'Thử lại', onclick: load }),
      el('details', {}, [el('summary', { text: 'Chi tiết lỗi' }), el('code', { text: msg })])
    ]));
    announce('Lỗi khi tải ' + tab.label);
  }

  function load() {
    var tab = currentTab(), content = $('#content');
    syncUrl();
    var seq = state.loadSeq = (state.loadSeq || 0) + 1;  // kết quả của lần tải cũ (đã đổi tab/bộ lọc) bị bỏ qua
    function current() { return seq === state.loadSeq; }
    destroyCharts();
    closePickers();
    $('#btn-apply').disabled = false;
    if (!tab.report) {
      ({ notify: renderNotify, costs: renderCosts, month_targets: renderTargets, shop_ad_spend: renderShopSpend, audit_rules: renderAuditRules, audit: renderAudit,
         wf_audit: function (c) { renderAudit(c, 'wayfair'); }, wf_audit_rules: function (c) { renderAuditRules(c, 'wayfair'); }
       }[tab.id] || renderDict)(content);
      return;
    }
    trimProvisional();
    if (tab.matrix) { renderMatrix(content, current); return; }
    content.innerHTML = '';
    var msg = el('p', { class: 'muted loading-msg', text: 'Đang tải ' + tab.label + '…' });
    content.appendChild(msg);
    content.appendChild(skeleton());
    setTimeout(function () { if (current() && content.getAttribute('aria-busy')) msg.textContent = 'Đang tải ' + tab.label + '… báo cáo nhiều dòng có thể mất vài giây.'; }, 1500);
    content.setAttribute('aria-busy', 'true');
    $('#btn-apply').disabled = true;
    setDirty(false);
    api('/api/report/' + tab.report + '?' + filterParams().toString())
      .then(function (data) { if (current()) { renderReport(content, data); announce('Đã tải ' + (data.title || tab.label)); } })
      .catch(function (e) { if (current()) renderError(content, tab, e); })
      .then(function () { if (current()) { $('#btn-apply').disabled = false; content.removeAttribute('aria-busy'); } });
  }

  var KPI_DEF = [['spend', 'Spend', 'money', -1], ['sales', 'Ad Sales', 'money', 1], ['acos', 'ACoS', 'pct', -1],
    ['tacos', 'TACoS', 'pct', -1], ['total_sales', 'Tổng DS', 'money', 1], ['organic_sales', 'DS tự nhiên (ước tính)', 'money', 1],
    ['ad_sales_share', '% DS từ QC', 'pct', 0], ['clicks', 'Clicks', 'int', 1], ['ctr', 'CTR', 'pct', 1],
    ['cpc', 'CPC', 'money', -1], ['cvr', 'CVR', 'pct', 1], ['orders', 'Orders', 'int', 1], ['units', 'Units', 'int', 1],
    ['aov', 'Giá trị đơn QC (AOV)', 'money', 1], ['ntb_share', '% đơn khách mới (NTB)', 'pct', 1]];

  var WF_KPI_DEF = [['spend', 'Spend', 'money', -1], ['sales', 'DS QC (giá sỉ)', 'money', 1], ['acos', 'ACoS', 'pct', -1],
    ['tacos', 'TACoS', 'pct', -1], ['total_sales', 'Tổng DS sỉ', 'money', 1], ['organic_sales', 'DS tự nhiên (ước tính)', 'money', 1],
    ['ad_sales_share', '% DS từ QC', 'pct', 0], ['retail_sales', 'DS QC (giá lẻ)', 'money', 1], ['clicks', 'Clicks', 'int', 1],
    ['ctr', 'CTR', 'pct', 1], ['cpc', 'CPC', 'money', -1], ['cvr', 'CVR', 'pct', 1], ['orders', 'Orders', 'int', 1],
    ['units', 'Units', 'int', 1], ['aov', 'Giá trị đơn QC (AOV)', 'money', 1]];

  // đường xu hướng nhỏ trong thẻ KPI: chỉ số chi phí (Spend, CPC) màu cam, còn lại xanh; di chuột để xem số từng ngày/tuần
  var SPARK_COST = { spend: 1, cpc: 1 }, SVGNS = 'http://www.w3.org/2000/svg';
  function sparkline(series, key, kind) {
    var vals = series && series.values && series.values[key];
    if (!vals || vals.filter(function (v) { return v !== null && v !== undefined; }).length < 2) return null;
    var W = 200, H = 40, P = 3, n = vals.length, lo = Infinity, hi = -Infinity;
    vals.forEach(function (v) { if (v !== null && v !== undefined) { lo = Math.min(lo, v); hi = Math.max(hi, v); } });
    if (hi === lo) { hi += 1; lo -= 1; }
    function x(i) { return n > 1 ? i / (n - 1) * W : W / 2; }
    function y(v) { return P + (1 - (v - lo) / (hi - lo)) * (H - 2 * P); }
    // ngày trống (vd chưa có tổng DS) làm đứt đường thay vì nối qua
    var line = '', area = '', seg = [];
    function flush() {
      if (seg.length) {
        var pts = seg.map(function (i) { return x(i).toFixed(1) + ',' + y(vals[i]).toFixed(1); });
        line += 'M' + pts.join('L');
        area += 'M' + x(seg[0]).toFixed(1) + ',' + H + 'L' + pts.join('L') + 'L' + x(seg[seg.length - 1]).toFixed(1) + ',' + H + 'Z';
      }
      seg = [];
    }
    vals.forEach(function (v, i) { if (v === null || v === undefined) flush(); else seg.push(i); });
    flush();
    var color = roleColor(SPARK_COST[key] ? 'c2' : 'c1');
    var svg = document.createElementNS(SVGNS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('aria-hidden', 'true');
    [['path', { d: area, fill: color, 'fill-opacity': '0.14', stroke: 'none' }],
     ['path', { d: line, fill: 'none', stroke: color, 'stroke-width': '1.5', 'vector-effect': 'non-scaling-stroke', 'stroke-linejoin': 'round' }]]
      .forEach(function (s) {
        var p = document.createElementNS(SVGNS, s[0]);
        Object.keys(s[1]).forEach(function (a) { p.setAttribute(a, s[1][a]); });
        svg.appendChild(p);
      });
    // chấm và nhãn là phần tử HTML để không bị méo theo preserveAspectRatio="none"
    var dot = el('span', { class: 'spark-dot' }), tip = el('span', { class: 'spark-tip' });
    dot.style.background = color;
    var last = n - 1;
    while (last > 0 && (vals[last] === null || vals[last] === undefined)) last--;
    function show(i, hover) {
      dot.style.left = (x(i) / W * 100) + '%';
      dot.style.top = (y(vals[i]) / H * 100) + '%';
      var week = series.grain === 'week';  // theo tuần: số tiền/số lượng là trung bình mỗi ngày (app/metrics.py: kpi_series)
      tip.textContent = hover ? (week ? 'Tuần ' : '') + dayMonth(series.labels[i]) + ': ' + fmt(vals[i], kind)
                                + (week && kind !== 'pct' ? '/ngày' : '') : '';
      tip.classList.toggle('on', !!hover);
    }
    var box = el('div', { class: 'spark', onmousemove: function (e) {
      var r = box.getBoundingClientRect(), i = Math.round((e.clientX - r.left) / r.width * (n - 1));
      i = Math.max(0, Math.min(n - 1, i));
      for (var k = 0; k < n && (vals[i] === null || vals[i] === undefined); k++) i = i > 0 ? i - 1 : n - 1;
      show(i, true);
    }, onmouseleave: function () { show(last, false); } }, [tip, dot]);
    box.insertBefore(svg, tip);
    show(last, false);
    return box;
  }

  // 4 chỉ số chính to ở hàng đầu, các chỉ số còn lại nhỏ hơn bên dưới; một dòng chú giải thay cho "so với kỳ trước" lặp lại
  var KPI_PRIMARY = ['spend', 'sales', 'acos', 'tacos'];
  function renderKpis(kpis) {
    var box = el('div', { class: 'kpi-block' }), main = el('div', { class: 'kpis primary' }), rest = el('div', { class: 'kpis secondary' });
    var a = $('#f-start').value, b = $('#f-end').value, prevTxt = 'kỳ trước';
    if (a && b) {
      var n = Math.round((parseIso(b) - parseIso(a)) / 864e5) + 1, pe = addDays(parseIso(a), -1);
      prevTxt = 'kỳ trước ' + dayMonth(iso(addDays(pe, 1 - n))) + '–' + dayMonth(iso(pe));
    }
    if (kpis.prev_label) prevTxt = kpis.prev_label;  // báo cáo tự chọn kỳ so sánh (vd cùng kỳ tháng trước)
    // báo cáo có thể tự gửi danh sách KPI: [khóa, nhãn, định dạng, hướng tốt, là chỉ số chính]
    var defs = kpis.def || (state.channel === 'wayfair' ? WF_KPI_DEF : KPI_DEF);
    defs.forEach(function (d) {
      var cur = kpis.current[d[0]], prev = kpis.previous[d[0]], delta = null, cls = 'd', tone = '';
      if (cur !== null && prev) {
        delta = (cur - prev) / Math.abs(prev);
        if (d[3] !== 0 && Math.abs(delta) > 0.001) { tone = (delta * d[3] > 0) ? 'tốt' : 'xấu'; cls += tone === 'tốt' ? ' up' : ' down'; }
      }
      var change = delta === null ? 'Kỳ trước: ' + fmt(prev, d[2]) : (delta >= 0 ? '▲ ' : '▼ ') + Math.abs(delta * 100).toFixed(1) + '%';
      ((kpis.def ? d[4] : KPI_PRIMARY.indexOf(d[0]) >= 0) ? main : rest).appendChild(el('div', { class: 'kpi' }, [
        el('div', { class: 'l', text: d[1] }),
        el('div', { class: 'v', text: fmt(cur, d[2]) }),
        el('div', { class: cls, title: 'Kỳ trước: ' + fmt(prev, d[2]), text: change },
           delta === null ? [] : [el('span', { class: 'sr-only', text: ' so với ' + prevTxt + (tone ? ', ' + tone : '') })]),
        sparkline(kpis.series, d[0], d[2])
      ]));
    });
    box.appendChild(main);
    box.appendChild(el('p', { class: 'note kpi-legend' }, ['▲▼ so với ' + prevTxt + (kpis.prev_label ? '. ' : ' (cùng số ngày). '),
      el('span', { class: 'up', text: 'Xanh = tốt' }), ', ', el('span', { class: 'down', text: 'đỏ = xấu' }),
      kpis.def ? ' theo ý nghĩa chỉ số: Spend, TACoS, hoàn tiền tăng là xấu. Di chuột lên % để xem số kỳ trước.'
               : ' theo ý nghĩa chỉ số: Spend, ACoS, TACoS, CPC tăng là xấu. ROAS, Impressions, CPA xem trong bảng chi tiết. Di chuột lên % để xem số kỳ trước.',
      kpis.series ? ' Đường nhỏ: diễn biến trong kỳ theo ' + (kpis.series.grain === 'week' ? 'tuần (số tiền, số lượng là trung bình mỗi ngày)' : 'ngày') + ', di chuột để xem từng điểm.' : '']));
    box.appendChild(rest);
    return box;
  }

  // thẻ số liệu không có kỳ trước (vd tổng quan tồn kho)
  function renderCards(cards) {
    var grid = el('div', { class: 'kpis' });
    cards.forEach(function (c) {
      grid.appendChild(el('div', { class: 'kpi' + (c.tone ? ' tone-' + c.tone : '') }, [
        el('div', { class: 'l', text: c.label }),
        el('div', { class: 'v', text: fmt(c.value, c.fmt) }),
        el('div', { class: 'd', text: c.note || '' })
      ]));
    });
    return grid;
  }

  var STATUS_CLASS = { OOS: 'st-bad', CRITICAL: 'st-bad', LOW: 'st-warn', OVER: 'st-info', NO_SALES: 'st-info' };

  function addChart(parent, config) {
    var box = el('div', { class: 'chart' }), canvas = el('canvas');
    box.appendChild(canvas);
    parent.appendChild(box);
    if (!window.Chart) { box.textContent = 'Không tải được Chart.js'; return; }
    config.options = Object.assign({ responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false } }, config.options || {});
    state.charts.push(new Chart(canvas, config));
  }

  var pctAxis = { position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: function (v) { return (v * 100).toFixed(0) + '%'; } } };

  function comboChart(parent, title, rows, labelKey) {
    addChart(parent, {
      data: { labels: rows.map(function (r) { return r[labelKey]; }), datasets: [
        { type: 'bar', label: 'Spend', data: rows.map(function (r) { return r.spend; }), yAxisID: 'y', backgroundColor: mc('spend') },
        { type: 'bar', label: 'Ad Sales', data: rows.map(function (r) { return r.sales; }), yAxisID: 'y', backgroundColor: mc('sales') },
        { type: 'line', label: 'ACoS', data: rows.map(function (r) { return r.acos; }), yAxisID: 'y1', borderColor: mc('acos'), backgroundColor: mc('acos') },
        { type: 'line', label: 'CVR', data: rows.map(function (r) { return r.cvr; }), yAxisID: 'y1', borderColor: mc('cvr'), backgroundColor: mc('cvr') }
      ] },
      options: { plugins: { title: { display: true, text: title } }, scales: { y: { position: 'left' }, y1: pctAxis } }
    });
  }

  // ---------- đồ thị mô tả bằng data.viz (app/viz.py) ----------
  // Màu: bảng categorical cố định thứ tự (đã kiểm tra mù màu, theo skill dataviz), màu trạng thái riêng, xám cho
  // "tồn nhiều / không bán". Chữ dùng màu chữ, không dùng màu series. Không dùng hai trục y.
  // Mọi màu đạt ≥ 3:1 so với nền thẻ (#fff sáng / #1d2027 tối, WCAG 1.4.11). Trạng thái tồn kho đổi theo theme.
  var PALETTE = {
    light: { c: ['#2a78d6', '#eb6834', '#16996a', '#b87d00', '#d0517f', '#008300', '#6250d6', '#e34948'], n1: '#8f8d86', n2: '#5f5d57',
             st: { OOS: '#d03b3b', CRITICAL: '#d9622b', LOW: '#a87700', OK: '#0ca30c' } },
    dark: { c: ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'], n1: '#b3b1a9', n2: '#75736d',
            st: { OOS: '#e5534b', CRITICAL: '#f08a5d', LOW: '#f2b33d', OK: '#3fbf3f' } }
  };
  // vai trò màu cố định cho chỉ số QC trong đồ thị tự vẽ (Tổng quan, combo theo nhóm)
  var METRIC_ROLE = { spend: 'c1', sales: 'c3', acos: 'c2', tacos: 'c7', cvr: 'c7', ctr: 'c1' };

  function isDark() { return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches; }
  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function roleColor(role) {
    var p = isDark() ? PALETTE.dark : PALETTE.light;
    if (!role) return p.c[0];
    if (role.charAt(0) === 'c') return p.c[(Number(role.slice(1)) - 1) % 8];
    if (role.slice(0, 3) === 'st:') {
      var st = role.slice(3);
      return p.st[st] || (st === 'OVER' ? p.n1 : p.n2);
    }
    return p[role] || p.n1;
  }
  function fmtUnit(v, unit) {
    if (v === null || v === undefined) return '–';
    if (unit === 'days') return Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 }) + ' ngày';
    if (unit === 'cont') return fmt(v, 'num2') + ' cont';
    return fmt(v, unit === 'int' ? 'int' : unit);
  }
  // tổng hợp số liệu từng series cho chú thích, vd "DS QC: $412,300 (41.2%)". Tiền / số lượng: cộng các điểm (sum_mode
  // 'last' = đồ thị lũy kế, lấy điểm cuối); đồ thị chồng thêm % trên tổng các phần; tỉ lệ (ACoS…) chỉ khi server gửi
  // sẵn s.total của cả kỳ (không cộng / trung bình theo ngày được). Thanh tăng / giảm (signed): tách tổng tăng và giảm.
  var SUM_UNITS = { money: 1, int: 1, cont: 1 };
  function sumFmt(v, unit) {
    if (unit === 'money') return (v < 0 ? '−$' : '$') + Math.abs(Math.round(v)).toLocaleString('en-US');
    if (unit === 'pct') return (v * 100).toFixed(1) + '%';
    if (unit === 'cont') return fmt(v, 'num2') + ' cont';
    return Math.round(v).toLocaleString('en-US');
  }
  function seriesSums(spec) {
    if (/waterfall|gantt|scatter|sku_line|us_map|geo_map/.test(spec.kind) || spec.sum_mode === 'none') return [];
    var stacked = /stacked/.test(spec.kind), totals = spec.series.map(function (s) {
      var u = s.unit || spec.unit;
      if (s.total !== undefined && s.total !== null) return s.total;
      if (s.dash || !SUM_UNITS[u]) return null;
      var nums = (s.raw || s.values).filter(function (v) { return typeof v === 'number' && isFinite(v); });
      if (!nums.length) return null;
      if (spec.sum_mode === 'last') return nums[nums.length - 1];
      return nums.reduce(function (a, b) { return a + b; }, 0);
    });
    var grand = 0;
    if (stacked) spec.series.forEach(function (s, i) { if (!s.line && totals[i] !== null && SUM_UNITS[s.unit || spec.unit]) grand += totals[i]; });
    return totals.map(function (t, i) {
      var s = spec.series[i], u = s.unit || spec.unit;
      if (t === null) return null;
      if (spec.signed && s.total === undefined) {
        var vals = s.raw || s.values, up = 0, down = 0;
        vals.forEach(function (v) { if (typeof v === 'number') { if (v > 0) up += v; else down += v; } });
        return 'tăng +' + sumFmt(up, u) + ' · giảm ' + sumFmt(down, u);
      }
      var txt = (u === 'pct' ? 'cả kỳ ' : '') + sumFmt(t, u);
      if (grand && !s.line && SUM_UNITS[u]) txt += ' (' + (t / grand * 100).toFixed(1) + '%)';
      return txt;
    });
  }
  // chú thích có kèm số tổng hợp; đồ thị một series thì ghi "Tổng: …" dưới tiêu đề thay cho chú thích
  function legendCfg(base, spec, sums, style, show) {
    return { display: show, position: 'bottom',
             labels: { color: base.text, usePointStyle: true, pointStyle: style, boxWidth: 10, padding: 14,
                       generateLabels: function (chart) {
                         var items = Chart.defaults.plugins.legend.labels.generateLabels(chart);
                         items.forEach(function (it) { if (sums[it.datasetIndex]) it.text += ': ' + sums[it.datasetIndex]; });
                         return items;
                       } } };
  }
  function singleSum(card, spec, sums) {
    if (spec.series.length !== 1 || !sums[0]) return;
    card.box.insertBefore(el('p', { class: 'viz-sum', text: (spec.signed ? 'Tổng: ' : 'Tổng ' + spec.series[0].name + ': ') + sums[0] }), card.wrap);
  }

  function compact(v, unit) {
    if (unit === 'pct') return Math.round(v * 100) + '%';
    if (unit === 'cont') return Math.abs(v) >= 100 ? String(Math.round(v)) : String(Math.round(v * 10) / 10);
    // 1 chữ số thập phân để trục hẹp (vd thác nước $40.5K → $41K) không ra hai nhãn giống nhau; bỏ ".0" thừa
    var a = Math.abs(v), s = a >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : a >= 1e3 ? (v / 1e3).toFixed(a >= 1e5 ? 0 : 1) + 'K' : String(Math.round(v * 100) / 100);
    s = s.replace(/\.0([KM])$/, '$1');
    return unit === 'money' ? (v < 0 ? '−$' + s.slice(1) : '$' + s) : s;
  }
  // sọc chéo phủ lên màu: dấu hiệu không dựa vào màu (vd "Đứt hàng" so với "Còn đủ bán", WCAG 1.4.1)
  function stripes(color) {
    var c = document.createElement('canvas'), x = c.getContext('2d');
    c.width = c.height = 8;
    x.fillStyle = color; x.fillRect(0, 0, 8, 8);
    x.strokeStyle = 'rgba(255, 255, 255, .6)'; x.lineWidth = 2;
    x.beginPath(); x.moveTo(-2, 10); x.lineTo(10, -2); x.moveTo(-2, 2); x.lineTo(2, -2); x.moveTo(6, 10); x.lineTo(10, 6); x.stroke();
    return x.createPattern(c, 'repeat');
  }
  function mc(key) { return roleColor(METRIC_ROLE[key]); }

  function chartBase() {
    var text = cssVar('--muted') || '#667085', grid = cssVar('--line') || '#e4e7ec';
    return { text: text, grid: grid, surface: cssVar('--card') || '#fff' };
  }

  // vạch tham chiếu (vd 14 / 30 ngày) trên trục giá trị
  var refLinePlugin = {
    id: 'refLines',
    // vạch dọc: chừa chỗ phía trên vùng vẽ để nhãn không đè lên cột
    beforeInit: function (chart, args, opts) {
      if (!opts || !opts.lines || !opts.lines.length || opts.axis === 'y') return;
      var pad = chart.options.layout.padding;
      chart.options.layout.padding = Object.assign({}, typeof pad === 'object' ? pad : {}, { top: 6 + 15 * Math.min(opts.lines.length, 2) });
    },
    afterDatasetsDraw: function (chart, args, opts) {
      if (!opts || !opts.lines || !opts.lines.length) return;
      var scale = chart.scales[opts.axis || 'x'], area = chart.chartArea, ctx = chart.ctx;
      ctx.save();
      var bg = cssVar('--card') || '#fff', rowEnd = [];
      opts.lines.forEach(function (l, i) {
        var px = scale.getPixelForValue(l.value);
        if (px < (opts.axis === 'y' ? area.top : area.left) || px > (opts.axis === 'y' ? area.bottom : area.right)) return;
        ctx.strokeStyle = opts.color; ctx.fillStyle = opts.color; ctx.lineWidth = 1; ctx.setLineDash([4, 3]);
        ctx.beginPath();
        if (opts.axis === 'y') { ctx.moveTo(area.left, px); ctx.lineTo(area.right, px); }
        else { ctx.moveTo(px, area.top - 15 * Math.min(opts.lines.length, 2)); ctx.lineTo(px, area.bottom); }
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.font = '11px system-ui, sans-serif';
        var w = ctx.measureText(l.label).width, x, y;
        if (opts.axis === 'y') { x = area.left + 4; y = px - 4; }
        else {
          var row = 0;
          while (rowEnd[row] !== undefined && px + 4 < rowEnd[row] + 6) row++;
          rowEnd[row] = px + 4 + w;
          x = px + 4; y = area.top - 4 - row * 15;
        }
        ctx.fillStyle = bg; ctx.globalAlpha = 0.9;
        ctx.fillRect(x - 2, y - 10, w + 4, 13);
        ctx.globalAlpha = 1; ctx.fillStyle = opts.color;
        ctx.fillText(l.label, x, y);
      });
      ctx.restore();
    }
  };

  function vizCard(parent, spec, height) {
    var box = el('div', { class: 'viz-card' }), canvasWrap = el('div', { class: 'viz-canvas' }), canvas = el('canvas');
    box.appendChild(el('h3', { text: spec.title }));
    if (spec.subtitle) box.appendChild(el('p', { class: 'muted small', text: spec.subtitle }));
    canvasWrap.style.height = (height || 300) + 'px';
    canvasWrap.appendChild(canvas);
    box.appendChild(canvasWrap);
    parent.appendChild(box);
    return { box: box, canvas: canvas, wrap: canvasWrap };
  }

  function newChart(canvas, config) {
    if (!window.Chart) { canvas.parentNode.textContent = 'Không tải được Chart.js'; return null; }
    var c = new Chart(canvas, config);
    state.charts.push(c);
    return c;
  }

  function axisCfg(base, unit, extra) {
    return Object.assign({ grid: { color: base.grid, drawTicks: false }, border: { display: false },
      ticks: { color: base.text, padding: 6, callback: function (v) { return compact(v, unit); } } }, extra || {});
  }
  function catAxis(base, extra) {
    return Object.assign({ grid: { display: false }, border: { color: base.grid }, ticks: { color: base.text, autoSkip: true } }, extra || {});
  }

  // bấm đồ thị -> lọc bảng (tab hiện tại) hoặc chuyển tab rồi lọc
  function setTableCols(tab, tableKey, cols, replace) {
    var all = state.tf[tab] || store('tf.' + tab) || {};
    var spec = all[tableKey] || { cond: [], cols: {} };
    spec.cols = spec.cols || {};
    spec.cond = spec.cond || [];
    var keys = Object.keys(cols);
    var same = keys.length && keys.every(function (k) { return JSON.stringify(spec.cols[k]) === JSON.stringify(cols[k]); });
    if (replace) spec.cols = {};
    keys.forEach(function (k) { if (same && !replace) delete spec.cols[k]; else spec.cols[k] = cols[k]; });
    if (spec.cond.length || Object.keys(spec.cols).length) all[tableKey] = spec; else delete all[tableKey];
    state.tf[tab] = all;
    store('tf.' + tab, all);
  }

  function vizClick(spec, labelIndex, seriesIndex, tables) {
    var f = { opts: {}, cols: {} };
    [spec.label_filters && spec.label_filters[labelIndex], spec.series[seriesIndex] && spec.series[seriesIndex].filter]
      .forEach(function (x) { if (x) { Object.assign(f.opts, x.opts || {}); Object.assign(f.cols, x.cols || {}); } });
    if (spec.goto) {
      var tab = spec.goto.tab;
      Object.keys(f.opts).forEach(function (k) { store('o.' + tab + '.' + k, f.opts[k]); });
      if (spec.goto.table) setTableCols(tab, spec.goto.table, f.cols, true);
      store('open.' + tab, true);
      state.tab = tab;
      store('tab.' + state.channel, tab);
      state.navPush = true;
      renderTabs(); renderControls(); load();
      return;
    }
    if (Object.keys(f.opts).length) {  // đổi điều khiển của tab (vd bỏ lọc trạng thái để thấy SKU vừa chọn)
      Object.keys(f.opts).forEach(function (k) { store('o.' + state.tab + '.' + k, f.opts[k]); });
      renderControls();
    }
    if (!Object.keys(f.cols).length && !Object.keys(f.opts).length) return;
    (spec.tables || []).forEach(function (key) {
      var t = (tables || []).filter(function (x) { return x.key === key; })[0];
      var cols = {};
      Object.keys(f.cols).forEach(function (k) {
        if (!t || t.columns.some(function (c) { return c.key === k; })) cols[k] = f.cols[k];
      });
      if (Object.keys(cols).length) setTableCols(state.tab, key, cols, false);
    });
    store('open.' + state.tab, true);
    load();
  }

  // popup "Xem tất cả": đồ thị top-N có spec.full (server gửi kèm mọi dòng, tối đa 300) -> vẽ đủ, tìm được, tải CSV
  function subsetSpec(spec, idx) {
    function pick(a) { return a ? idx.map(function (i) { return a[i]; }) : a; }
    return Object.assign({}, spec, { labels: pick(spec.labels), label_filters: pick(spec.label_filters),
      series: spec.series.map(function (s) { return Object.assign({}, s, { values: pick(s.values), colors: pick(s.colors), raw: pick(s.raw) }); }) });
  }
  function csvDownload(spec, name) {
    function q(v) {
      v = v === null || v === undefined ? '' : typeof v === 'number' ? String(Math.round(v * 100) / 100) : String(v);
      return /[",\n;]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
    }
    var lines = [['Tên'].concat(spec.series.map(function (s) { return s.name; })).map(q).join(',')];
    spec.labels.forEach(function (l, i) {
      lines.push([l].concat(spec.series.map(function (s) { return (s.raw || s.values)[i]; })).map(q).join(','));
    });
    var a = el('a', { href: URL.createObjectURL(new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })), download: name + '.csv' });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }
  function showAll(spec, tables, opener) {
    var full = Object.assign({}, spec, spec.full, { full: null, subtitle: null });
    var dlg = el('dialog', { class: 'viz-dialog', 'aria-label': full.title });
    var search = el('input', { type: 'search', placeholder: 'Tìm theo tên / SKU…', 'aria-label': 'Tìm trong danh sách' });
    var count = el('span', { class: 'muted small', 'aria-live': 'polite' });
    var body = el('div', { class: 'viz-dialog-body' }), chartRef = null, shown = full;
    function dispose() { if (chartRef) { chartRef.destroy(); state.charts = state.charts.filter(function (c) { return c !== chartRef; }); chartRef = null; } }
    function draw() {
      var q = search.value.trim().toLowerCase(), idx = [];
      full.labels.forEach(function (l, i) { if (!q || String(l).toLowerCase().indexOf(q) >= 0) idx.push(i); });
      shown = subsetSpec(full, idx);
      dispose(); body.innerHTML = '';
      count.textContent = (q ? idx.length + ' / ' : '') + full.labels.length + ' dòng' +
        (full.count > full.labels.length ? ' (tổng ' + full.count + ', hiện ' + full.labels.length + ' dòng đầu)' : '');
      if (!idx.length) { body.appendChild(el('p', { class: 'muted', text: 'Không có dòng nào khớp.' })); return; }
      chartRef = categoryChart(body, Object.assign({}, shown, { title: '' }), tables, { popup: true, onPick: function () { finish(false); } });
    }
    // đóng + dọn dẹp tự làm, không chờ sự kiện "close" của <dialog> (có trình duyệt nhúng không phát sự kiện này)
    var done = false;
    function finish(refocus) {
      if (done) return;
      done = true;
      dispose();
      if (dlg.open) dlg.close();
      dlg.remove();
      if (refocus && opener && document.body.contains(opener)) opener.focus();
    }
    var timer;
    search.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(draw, 150); });
    dlg.appendChild(el('div', { class: 'viz-dialog-head' }, [
      el('h3', { text: full.title }),
      el('button', { type: 'button', class: 'viz-dialog-close', 'aria-label': 'Đóng', text: '×', onclick: function () { finish(true); } })
    ]));
    dlg.appendChild(el('div', { class: 'viz-dialog-tools' }, [search, count,
      el('button', { type: 'button', text: 'Tải CSV', onclick: function () { csvDownload(shown, spec.key || 'chart'); } })]));
    if (spec.goto || (spec.tables && spec.tables.length)) dlg.appendChild(el('p', { class: 'muted small', text: 'Bấm một thanh để lọc bảng (popup sẽ đóng).' }));
    dlg.appendChild(body);
    dlg.addEventListener('click', function (e) { if (e.target === dlg) finish(true); });  // bấm ra ngoài
    dlg.addEventListener('cancel', function (e) { e.preventDefault(); finish(true); });   // phím Esc
    dlg.addEventListener('close', function () { finish(true); });
    document.body.appendChild(dlg);
    dlg.showModal();
    draw();
    search.focus();
  }

  function categoryChart(parent, spec, tables, opts) {
    opts = opts || {};
    var horizontal = spec.kind.charAt(0) === 'h', stacked = /stacked/.test(spec.kind), base = chartBase();
    // thanh ngang chồng nhiều series: chú thích chiếm chỗ nên cần cao hơn
    var height = horizontal ? Math.max(stacked && spec.series.length > 3 ? 230 : 160, spec.labels.length * (opts.popup ? 24 : 30) + 70) : 300;
    var card = opts.popup ? (function () {  // popup: không giới hạn chiều cao, khung ngoài tự cuộn
      var wrap = el('div', { class: 'viz-canvas' }), canvas = el('canvas'), box = el('div');
      wrap.style.height = height + 'px'; wrap.appendChild(canvas); box.appendChild(wrap); parent.appendChild(box);
      return { box: box, canvas: canvas, wrap: wrap };
    })() : vizCard(parent, spec, opts.height || Math.min(height, 520));
    if (spec.full && !opts.popup) {
      var more = el('button', { type: 'button', class: 'link viz-more', text: 'Xem tất cả (' + spec.full.count + ')',
        'aria-haspopup': 'dialog', onclick: function () { showAll(spec, tables, more); } });
      card.box.querySelector('h3').appendChild(more);
    }
    // series có line: true vẽ thành đường trên trục phải theo đơn vị riêng (vd TACoS % trên cột spend $)
    var lineUnit = null;
    var datasets = spec.series.map(function (s) {
      if (s.line) {
        lineUnit = s.unit || spec.unit;
        return { type: 'line', label: s.name, data: s.values, unit: lineUnit, yAxisID: 'y1', order: 0,
                 borderColor: roleColor(s.color), backgroundColor: roleColor(s.color), borderWidth: 2,
                 pointRadius: 2, tension: 0.25, spanGaps: true };
      }
      return {
        label: s.name, data: s.values, order: 1,
        backgroundColor: s.colors ? s.colors.map(roleColor) : roleColor(s.color),
        borderColor: base.surface, borderWidth: stacked ? 1 : 0, borderRadius: 3, borderSkipped: false,
        maxBarThickness: 24, raw: s.raw
      };
    });
    var valueAxis = axisCfg(base, spec.unit, stacked ? { stacked: true } : {});
    if (spec.max) valueAxis.max = spec.max;
    if (spec.min !== undefined && spec.min !== null) { valueAxis.min = spec.min; valueAxis.beginAtZero = false; }
    // thác nước / chênh lệch: các bước hiện kèm dấu +/−; cột đầu và cuối của thác nước là tổng
    var waterfall = spec.kind === 'waterfall', signed = waterfall || spec.signed;
    function valueText(raw, i) {
      if (!signed || raw === null || raw === undefined || (waterfall && (i === 0 || i === spec.labels.length - 1))) return fmtUnit(raw, spec.unit);
      return (raw >= 0 ? '+' : '−') + fmtUnit(Math.abs(raw), spec.unit);
    }
    if (spec.unit === 'pct') valueAxis.max = spec.max || 1;
    var dates = !horizontal && spec.labels.every(isIsoDate);
    var scales = horizontal ? { x: valueAxis, y: catAxis(base, { stacked: stacked, ticks: { color: base.text, autoSkip: false } }) }
                            : { x: catAxis(base, { stacked: stacked, ticks: { color: base.text, autoSkip: true, maxRotation: 0,
                                  callback: function (v) { var l = spec.labels[v]; return dates ? dayMonth(l) : l; } } }), y: valueAxis };
    if (lineUnit && !horizontal) scales.y1 = axisCfg(base, lineUnit, { position: 'right', beginAtZero: true, grid: { drawOnChartArea: false } });
    var clickable = !!(spec.goto || (spec.tables && spec.tables.length));
    var sums = seriesSums(spec);
    singleSum(card, spec, sums);
    if (opts.popup && horizontal) scales.x.position = 'top';  // danh sách dài: trục giá trị ở trên, khỏi cuộn xuống mới thấy
    var cfg = {
      type: 'bar',
      data: { labels: spec.labels, datasets: datasets },
      options: {
        indexAxis: horizontal ? 'y' : 'x', responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: 'nearest', intersect: true },
        scales: scales,
        plugins: {
          legend: Object.assign(legendCfg(base, spec, sums, 'rectRounded', spec.series.length > 1), opts.popup ? { position: 'top' } : {}),
          tooltip: { callbacks: {
            title: function (items) { return items.length ? (dates ? dmy(items[0].label) : items[0].label) : ''; },
            label: function (ctx) {
              var raw = ctx.dataset.raw ? ctx.dataset.raw[ctx.dataIndex] : ctx.raw;
              if (ctx.dataset.unit) return ' ' + ctx.dataset.label + ': ' + fmtUnit(raw, ctx.dataset.unit);
              return ' ' + (waterfall ? '' : ctx.dataset.label + ': ') + valueText(raw, ctx.dataIndex);
            } } },
          refLines: { lines: spec.refs || [], axis: horizontal ? 'x' : 'y', color: base.text }
        },
        onHover: function (evt, els) { evt.native.target.style.cursor = clickable && els.length ? 'pointer' : 'default'; },
        onClick: function (evt, els) {
          if (!clickable || !els.length) return;
          var i = els[0].index, ds = els[0].datasetIndex;
          if (!opts.onPick) { vizClick(spec, i, ds, tables); return; }
          // popup: đóng (hủy đồ thị) sau khi Chart.js xử lý xong sự kiện này, nếu không nó báo lỗi handleEvent
          setTimeout(function () { opts.onPick(); vizClick(spec, i, ds, tables); }, 0);
        }
      },
      plugins: [refLinePlugin]
    };
    if (opts.matrix) matrixCfg(cfg, spec);
    return newChart(card.canvas, cfg);
  }

  // ---------- Matrix Chart: các đồ thị dùng chung trục thời gian ----------
  // trục y cố định bề rộng để vùng vẽ của mọi đồ thị thẳng hàng; rê chuột ở một đồ thị -> vạch dọc + tooltip cùng kỳ
  // ở mọi đồ thị (state.matrixCharts)
  var MATRIX_AXIS_W = 72;
  function periodText(l, short) {
    if (!isIsoDate(l)) return l;
    if (state.matrixGran === 'month') return l.slice(5, 7) + '/' + l.slice(0, 4);
    if (state.matrixGran === 'week') return short ? dayMonth(l) : 'Tuần từ ' + dmy(l);
    return short ? dayMonth(l) : dmy(l);
  }
  function matrixCfg(cfg, spec) {
    var o = cfg.options, sc = o.scales;
    sc.y.afterFit = function (s) { s.width = MATRIX_AXIS_W; };
    if (sc.y1) sc.y1.display = false;
    sc.x.ticks = Object.assign({}, sc.x.ticks, { maxTicksLimit: 12, autoSkip: true, maxRotation: 0,
      callback: function (v) { return periodText(spec.labels[v], true); } });
    // đường cũng đặt điểm ở giữa ô như cột (mặc định đường vẽ sát mép) để cùng một kỳ thẳng hàng ở mọi đồ thị
    sc.x.offset = true;
    sc.x.afterFit = function (s) { s.paddingLeft = s.paddingRight = 0; };
    o.interaction = { mode: 'index', intersect: false };
    o.layout = { padding: { right: 12 } };
    o.plugins.tooltip.callbacks.title = function (items) { return items.length ? periodText(items[0].label) : ''; };
    if (spec.unit === 'pct') delete sc.y.max;  // ACoS theo ngày có thể > 100%
    cfg.plugins = (cfg.plugins || []).concat([matrixSync]);
  }
  var matrixSync = {
    id: 'matrixSync',
    afterEvent: function (chart, args) {
      var e = args.event, group = state.matrixCharts || [];
      if (group.indexOf(chart) < 0) return;
      if (e.type === 'mouseout') { syncIndex(null, chart); args.changed = true; return; }
      if (e.type !== 'mousemove') return;
      var x = chart.scales.x, n = chart.data.labels.length;
      var idx = e.x < x.left || e.x > x.right ? null : Math.max(0, Math.min(n - 1, Math.round(x.getValueForPixel(e.x))));
      if (syncIndex(idx, chart)) args.changed = true;
    },
    afterDatasetsDraw: function (chart) {
      var idx = state.matrixIdx;
      if (idx === null || idx === undefined || (state.matrixCharts || []).indexOf(chart) < 0) return;
      var x = chart.scales.x.getPixelForValue(idx), a = chart.chartArea, ctx = chart.ctx;
      ctx.save();
      ctx.strokeStyle = cssVar('--muted') || '#667085'; ctx.globalAlpha = 0.6; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke();
      ctx.restore();
    }
  };
  function syncIndex(idx, src) {
    if (state.matrixIdx === idx) return false;
    state.matrixIdx = idx;
    (state.matrixCharts || []).forEach(function (c) {
      if (c === src) return;  // đồ thị đang rê chuột tự vẽ tooltip của nó
      var els = idx === null ? [] : c.data.datasets.map(function (d, i) { return { datasetIndex: i, index: idx }; })
        .filter(function (el) { return c.isDatasetVisible(el.datasetIndex) && c.getDatasetMeta(el.datasetIndex).data[idx]; });
      c.setActiveElements(els);
      c.tooltip.setActiveElements(els, { x: idx === null ? 0 : c.scales.x.getPixelForValue(idx), y: c.chartArea.top });
      c.update('none');
    });
    return true;
  }

  // ---------- Matrix Chart: đồ thị chính + đồ thị phụ, mỗi đồ thị người dùng tự chọn chỉ số ----------
  // cấu hình lưu theo trình duyệt (matrix.v2): { charts: [{ metrics: [{id, style: bar|line}], mode, stack, preset }] }
  // chế độ: value = giá trị thật (tối đa 2 đơn vị: trục trái + trục phải), index = kỳ đầu = 100, change = % so với kỳ trước
  var MX_MODES = [['value', 'Giá trị thật'], ['index', 'Chỉ số hóa (kỳ đầu = 100)'], ['change', '% so với kỳ trước']];
  var MX_UNIT_NAME = { money: 'tiền', pct: 'tỷ lệ %', int: 'số lượng' };
  function mxMetric(id) {
    var ms = state.matrixCat.metrics;
    for (var i = 0; i < ms.length; i++) if (ms[i].id === id) return ms[i];
    return null;
  }
  function mxName(meta) { return meta.group + ' · ' + meta.label; }
  function mxFromPreset(p) {
    return { metrics: p.metrics.map(function (m) { return { id: m.id, style: m.style }; }), mode: p.mode, stack: !!p.stack, preset: p.name };
  }
  function mxConfig() {
    var cat = state.matrixCat, cfg = store('matrix.v2');
    if (!cfg || !Array.isArray(cfg.charts) || !cfg.charts.length) {
      cfg = { charts: cat.default.map(function (i) { return mxFromPreset(cat.presets[i]); }) };
    }
    cfg.charts = cfg.charts.slice(0, 2).map(function (c) {
      return {
        metrics: (c.metrics || []).filter(function (m) { return m && mxMetric(m.id); }).slice(0, cat.max_metrics)
          .map(function (m) { return { id: m.id, style: m.style === 'bar' ? 'bar' : 'line' }; }),
        mode: ['value', 'index', 'change'].indexOf(c.mode) >= 0 ? c.mode : 'value',
        stack: !!c.stack, preset: c.preset || ''
      };
    });
    return cfg;
  }
  function mxSave(cfg) { store('matrix.v2', cfg); mxDraw(); }
  function mxCustomPresets() { var p = store('matrix.presets'); return Array.isArray(p) ? p : []; }

  // đổi giá trị theo chế độ; giữ giá trị thật để tooltip ghi kèm
  function mxTransform(values, mode) {
    if (mode === 'index') {
      var base = null;
      values.forEach(function (v) { if (base === null && typeof v === 'number' && v !== 0) base = v; });
      return values.map(function (v) { return typeof v === 'number' && base ? v / base * 100 : null; });
    }
    if (mode === 'change') {
      return values.map(function (v, i) {
        var prev = i ? values[i - 1] : null;
        return typeof v === 'number' && typeof prev === 'number' && prev !== 0 ? v / prev - 1 : null;
      });
    }
    return values.slice();
  }
  function mxFmt(v, unit) {
    if (v === null || v === undefined) return '–';
    if (unit === 'index') return (Math.round(v * 10) / 10).toLocaleString('en-US');
    if (unit === 'chg') return (v >= 0 ? '+' : '−') + Math.abs(v * 100).toFixed(1) + '%';
    return fmtUnit(v, unit);
  }
  function mxTick(v, unit) {
    if (unit === 'index') return String(Math.round(v));
    if (unit === 'chg') return (v > 0 ? '+' : '') + Math.round(v * 100) + '%';
    return compact(v, unit);
  }
  // series sẽ vẽ của một đồ thị: chế độ giá trị thật chỉ giữ 2 đơn vị đầu (trục trái, trục phải), còn lại ẩn
  function mxSeries(chartCfg, d) {
    var units = [], series = [], hidden = [];
    chartCfg.metrics.forEach(function (m, i) {
      var meta = mxMetric(m.id), data = d && d.byId[m.id];
      if (!meta) return;
      var unit = chartCfg.mode === 'value' ? meta.unit : chartCfg.mode === 'index' ? 'index' : 'chg';
      if (units.indexOf(unit) < 0) {
        if (units.length >= 2) { hidden.push(meta); return; }
        units.push(unit);
      }
      series.push({ m: m, meta: meta, unit: unit, axis: units.indexOf(unit) ? 'y1' : 'y', color: 'c' + (i + 1),
                    raw: data ? data.values : [], values: data ? mxTransform(data.values, chartCfg.mode) : [],
                    total: data ? data.total : null });
    });
    return { units: units, series: series, hidden: hidden };
  }
  function mxTotalText(s) {
    if (s.total === null || s.total === undefined) return '';
    return s.meta.unit === 'pct' ? 'cả kỳ ' + sumFmt(s.total, 'pct') : sumFmt(s.total, s.meta.unit);
  }

  function mxDrawChart(card, chartCfg, d, ci, rightPad) {
    var base = chartBase(), plan = mxSeries(chartCfg, d), labels = d.labels;
    var wrap = el('div', { class: 'viz-canvas' }), canvas = el('canvas', { role: 'img',
      'aria-label': (ci ? 'Đồ thị phụ: ' : 'Đồ thị chính: ') + plan.series.map(function (s) { return mxName(s.meta); }).join(', ') });
    wrap.style.height = (ci ? 280 : 360) + 'px';
    wrap.appendChild(canvas);
    card.slot.appendChild(wrap);
    if (!plan.series.length) { wrap.style.height = 'auto'; wrap.textContent = 'Chưa chọn chỉ số nào. Chọn ở ô "+ Thêm chỉ số".'; return null; }
    var bars = plan.series.filter(function (s) { return s.m.style === 'bar'; }).length;
    var stacked = chartCfg.stack && bars > 1;
    var many = labels.length > 45;
    var datasets = plan.series.map(function (s, i) {
      var c = roleColor(s.color), label = mxName(s.meta);
      var common = { label: label, data: s.values, rawv: s.raw, unit: s.unit, metaUnit: s.meta.unit, yAxisID: s.axis };
      if (s.m.style === 'bar') {
        return Object.assign(common, { type: 'bar', order: 2, stack: stacked ? 'bars' : 'b' + i, backgroundColor: c,
          borderColor: base.surface, borderWidth: stacked ? 1 : 0, borderRadius: 3, borderSkipped: false, maxBarThickness: 28 });
      }
      return Object.assign(common, { type: 'line', order: 1, stack: 'l' + i, borderColor: c, backgroundColor: c, borderWidth: 2,
        pointRadius: many ? 0 : 2, pointHoverRadius: 4, pointBackgroundColor: base.surface, tension: 0.2, spanGaps: true });
    });
    var scales = { x: catAxis(base, { stacked: stacked, offset: true, ticks: { color: base.text, autoSkip: true, maxTicksLimit: 12,
      maxRotation: 0, callback: function (v) { return periodText(labels[v], true); } } }) };
    scales.x.afterFit = function (s) { s.paddingLeft = s.paddingRight = 0; };
    plan.units.forEach(function (u, k) {
      var ax = axisCfg(base, u, { position: k ? 'right' : 'left', stacked: stacked, beginAtZero: chartCfg.mode !== 'index' });
      ax.ticks.callback = function (v) { return mxTick(v, u); };
      ax.afterFit = function (s) { s.width = MATRIX_AXIS_W; };
      if (k) ax.grid = { drawOnChartArea: false, drawTicks: false };
      scales[k ? 'y1' : 'y'] = ax;
    });
    var two = plan.units.length > 1;
    // các đồ thị cùng bề rộng vùng vẽ (thẳng hàng theo kỳ): đồ thị không có trục phải chừa chỗ bằng bề rộng trục phải
    var cfg = {
      type: 'bar',
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: 'index', intersect: false },
        layout: { padding: { right: 12 + (rightPad && !two ? MATRIX_AXIS_W : 0) } },
        scales: scales,
        plugins: {
          legend: { position: 'bottom', labels: { color: base.text, usePointStyle: true, boxWidth: 10, padding: 14,
            sort: function (a, b) { return a.datasetIndex - b.datasetIndex; },  // theo thứ tự chọn, không theo lớp vẽ
            generateLabels: function (chart) {
              var items = Chart.defaults.plugins.legend.labels.generateLabels(chart);
              items.forEach(function (it) {
                var s = plan.series[it.datasetIndex];
                it.pointStyle = s.m.style === 'bar' ? 'rectRounded' : 'line';
                if (two && s.axis === 'y1') it.text += ' (trục phải)';
                var t = chartCfg.mode === 'value' ? mxTotalText(s) : '';
                if (t) it.text += ': ' + t;
              });
              return items;
            } } },
          tooltip: { itemSort: function (a, b) { return a.datasetIndex - b.datasetIndex; }, callbacks: {
            title: function (items) { return items.length ? periodText(items[0].label) : ''; },
            label: function (ctx) {
              var ds = ctx.dataset, txt = ' ' + ds.label + ': ' + mxFmt(ctx.raw, ds.unit);
              if (ds.unit === 'index' || ds.unit === 'chg') txt += ' (' + fmtUnit(ds.rawv[ctx.dataIndex], ds.metaUnit) + ')';
              return txt;
            } } }
        }
      },
      plugins: [matrixSync]
    };
    var ch = newChart(canvas, cfg);
    if (ch) state.matrixCharts.push(ch);
    return ch;
  }

  function mxSelect(label, options, value, onchange, attrs) {
    var s = el('select', Object.assign({ 'aria-label': label }, attrs || {}));
    options.forEach(function (o) {
      if (o.group) {
        var g = el('optgroup', { label: o.group });
        o.items.forEach(function (it) { g.appendChild(el('option', { value: it[0], text: it[1], disabled: it[2] ? 'disabled' : null })); });
        s.appendChild(g);
      } else s.appendChild(el('option', { value: o[0], text: o[1] }));
    });
    s.value = value;
    s.addEventListener('change', function () { onchange(s.value, s); });
    return s;
  }

  // thẻ một đồ thị: hàng công cụ (bộ chọn sẵn, chế độ, chồng cột), các chỉ số đang chọn, chỗ vẽ, ghi chú
  function mxCard(parent, cfg, ci) {
    var cat = state.matrixCat, c = cfg.charts[ci], custom = mxCustomPresets();
    var box = el('section', { class: 'viz-card mx-card', 'aria-label': ci ? 'Đồ thị phụ' : 'Đồ thị chính' });
    function apply(next) { cfg.charts[ci] = next; mxSave(cfg); }
    function edit(fn) { fn(c); c.preset = ''; mxSave(cfg); }
    var presetOpts = [['', c.preset ? c.preset : 'Bộ chọn sẵn…'], { group: 'Có sẵn', items: cat.presets.map(function (p, i) { return ['b' + i, p.name]; }) }];
    if (custom.length) presetOpts.push({ group: 'Đã lưu', items: custom.map(function (p, i) { return ['u' + i, p.name]; }) });
    var preset = mxSelect('Bộ chọn sẵn', presetOpts, '', function (v) {
      if (!v) return;
      apply(mxFromPreset(v.charAt(0) === 'b' ? cat.presets[+v.slice(1)] : custom[+v.slice(1)]));
    }, { 'data-mxf': 'preset' + ci });
    var mode = mxSelect('Chế độ hiển thị', MX_MODES, c.mode, function (v) { c.mode = v; mxSave(cfg); }, { 'data-mxf': 'mode' + ci });
    var bars = c.metrics.filter(function (m) { return m.style === 'bar'; }).length;
    var stack = el('input', { type: 'checkbox', 'data-mxf': 'stack' + ci, disabled: bars > 1 ? null : 'disabled' });
    stack.checked = c.stack;
    stack.addEventListener('change', function () { c.stack = stack.checked; mxSave(cfg); });
    var tools = [preset, mode,
      el('label', { class: 'mx-check', title: bars > 1 ? '' : 'Cần ít nhất 2 chỉ số vẽ dạng cột' }, [stack, ' Chồng cột']),
      el('button', { type: 'button', class: 'link', text: 'Lưu bộ chọn', 'data-mxf': 'save' + ci, disabled: c.metrics.length ? null : 'disabled',
        onclick: function () {
          var name = window.prompt('Tên bộ chọn (lưu trên trình duyệt này):', c.preset || '');
          if (!name || !name.trim()) return;
          name = name.trim();
          var list = mxCustomPresets().filter(function (p) { return p.name !== name; });
          list.push({ name: name, metrics: c.metrics, mode: c.mode, stack: c.stack });
          store('matrix.presets', list);
          c.preset = name; mxSave(cfg);
          announce('Đã lưu bộ chọn ' + name);
        } })];
    var mine = custom.filter(function (p) { return p.name === c.preset; })[0];
    if (mine) tools.push(el('button', { type: 'button', class: 'link', text: 'Xóa bộ chọn đã lưu', onclick: function () {
      store('matrix.presets', mxCustomPresets().filter(function (p) { return p.name !== mine.name; }));
      c.preset = ''; mxSave(cfg);
    } }));
    if (ci) tools.push(el('button', { type: 'button', class: 'link', text: 'Bỏ đồ thị phụ', onclick: function () {
      cfg.charts.splice(ci, 1); mxSave(cfg);
    } }));
    box.appendChild(el('div', { class: 'mx-head' }, [el('h3', { text: ci ? 'Đồ thị phụ' : 'Đồ thị chính' }),
      el('div', { class: 'mx-tools' }, tools)]));

    // chỉ số đang chọn: màu, tên, đổi cột / đường, bỏ
    var plan = mxSeries(c, null), chips = el('div', { class: 'mx-chips' });
    c.metrics.forEach(function (m, i) {
      var meta = mxMetric(m.id), off = plan.hidden.indexOf(meta) >= 0, bar = m.style === 'bar';
      var sw = el('span', { class: 'mx-swatch' + (bar ? '' : ' line') });
      sw.style.background = roleColor('c' + (i + 1));
      chips.appendChild(el('span', { class: 'mx-chip' + (off ? ' off' : ''), title: off ? 'Không vẽ: chế độ giá trị thật chỉ có 2 trục (2 đơn vị). Chuyển sang chỉ số hóa hoặc % so với kỳ trước để vẽ cùng.' : meta.note }, [
        sw, el('span', { text: mxName(meta) + (off ? ' (ẩn)' : '') }),
        el('button', { type: 'button', class: 'link', text: bar ? 'Cột' : 'Đường', 'data-mxf': 'style' + ci + m.id,
          'aria-label': 'Đổi ' + mxName(meta) + ' sang ' + (bar ? 'đường' : 'cột'), title: 'Đổi sang ' + (bar ? 'đường' : 'cột'),
          onclick: function () { edit(function (x) { x.metrics[i].style = bar ? 'line' : 'bar'; }); } }),
        el('button', { type: 'button', class: 'link', text: '✕', 'aria-label': 'Bỏ ' + mxName(meta),
          onclick: function () { edit(function (x) { x.metrics.splice(i, 1); }); } })
      ]));
    });
    var full = c.metrics.length >= cat.max_metrics, groups = [];
    cat.metrics.forEach(function (m) { if (groups.indexOf(m.group) < 0) groups.push(m.group); });
    var addOpts = [['', full ? 'Đủ ' + cat.max_metrics + ' chỉ số' : '+ Thêm chỉ số']];
    groups.forEach(function (g) {
      addOpts.push({ group: g, items: cat.metrics.filter(function (m) { return m.group === g; }).map(function (m) {
        var taken = c.metrics.some(function (x) { return x.id === m.id; });
        var third = c.mode === 'value' && plan.units.length >= 2 && plan.units.indexOf(m.unit) < 0;
        return [m.id, m.label + ' · ' + MX_UNIT_NAME[m.unit] + (third ? ' (cần chế độ chỉ số hóa)' : ''), taken];
      }) });
    });
    chips.appendChild(mxSelect('Thêm chỉ số', addOpts, '', function (v) {
      if (!v) return;
      var meta = mxMetric(v);
      edit(function (x) { x.metrics.push({ id: v, style: meta.unit === 'pct' ? 'line' : x.metrics.length ? 'line' : 'bar' }); });
    }, { 'data-mxf': 'add' + ci, disabled: full ? 'disabled' : null, class: 'mx-add' }));
    box.appendChild(chips);
    var slot = el('div');
    box.appendChild(slot);
    var notes = [];
    if (plan.hidden.length) notes.push('Đang ẩn ' + plan.hidden.map(mxName).join(', ') + ': giá trị thật chỉ vẽ được 2 đơn vị (trục trái và phải).');
    if (c.mode === 'index') notes.push('Chỉ số hóa: mỗi chỉ số chia cho giá trị kỳ đầu tiên có số × 100, để so độ biến thiên của các chỉ số khác thang đo.');
    if (c.mode === 'change') notes.push('% so với kỳ trước: thay đổi tương đối của từng chỉ số so với kỳ liền trước (tỷ lệ như ACoS cũng tính thay đổi tương đối).');
    var defs = [];
    c.metrics.forEach(function (m) { var n = mxMetric(m.id).note; if (defs.indexOf(n) < 0) defs.push(n); });
    if (defs.length) notes.push(defs.join(' '));
    notes.forEach(function (n) { box.appendChild(el('p', { class: 'muted small', text: n })); });
    parent.appendChild(box);
    return { box: box, slot: slot };
  }

  function mxToolbar(cfg) {
    var gran = mxSelect('Gộp theo', [['', 'Tự động'], ['day', 'Ngày'], ['week', 'Tuần'], ['month', 'Tháng']], store('matrix.gran') || '',
      function (v) { store('matrix.gran', v); mxDraw(); }, { 'data-mxf': 'gran' });
    var kids = [el('label', { class: 'matrix-gran' }, ['Gộp theo ', gran])];
    if (cfg.charts.length < 2) kids.push(el('button', { type: 'button', text: '+ Thêm đồ thị phụ', 'data-mxf': 'addchart', onclick: function () {
      cfg.charts.push(mxFromPreset(state.matrixCat.presets[state.matrixCat.default[1]])); mxSave(cfg);
    } }));
    if (!cfg.charts.length) kids.push(el('button', { type: 'button', text: '+ Thêm đồ thị', onclick: function () { store('matrix.v2', null); mxDraw(); } }));
    kids.push(el('span', { class: 'muted small', text: 'Rê chuột trên một đồ thị để xem cùng kỳ ở đồ thị kia. Tỷ lệ (ACoS, CTR…) tính lại từ tổng của kỳ, không lấy trung bình ngày.' }));
    return el('div', { class: 'matrix-bar' }, kids);
  }

  function renderMatrix(content, current) {
    content.innerHTML = '';
    if (!state.matrixCat || !state.matrixCat.metrics) {
      content.appendChild(el('p', { class: 'muted', text: 'Đang tải danh mục chỉ số…' }));
      api('/api/matrix/catalog').then(function (c) { state.matrixCat = c; if (current()) renderMatrix(content, current); })
        .catch(function (e) { if (current()) renderError(content, currentTab(), e); });
      return;
    }
    state.mxView = { content: content, current: current };
    state.mxData = null;  // Áp dụng bộ lọc / mở tab: luôn tải lại số liệu
    mxDraw();
  }

  function mxDraw() {
    var v = state.mxView;
    if (!v || !v.current()) return;
    var content = v.content, current = v.current, cfg = mxConfig();
    var seq = state.mxSeq = (state.mxSeq || 0) + 1;
    var focusKey = document.activeElement && document.activeElement.getAttribute && document.activeElement.getAttribute('data-mxf');
    (state.matrixCharts || []).forEach(function (c) { c.destroy(); state.charts = state.charts.filter(function (x) { return x !== c; }); });
    state.matrixCharts = []; state.matrixIdx = null;
    content.innerHTML = '';
    var banner = provisionalBanner();
    if (banner) content.appendChild(banner);
    content.appendChild(mxToolbar(cfg));
    var note = el('div');
    content.appendChild(note);
    var area = el('div', { class: 'viz-grid matrix-grid' });
    content.appendChild(area);
    var cards = cfg.charts.map(function (c, ci) { return mxCard(area, cfg, ci); });
    if (focusKey) { var f = content.querySelector('[data-mxf="' + focusKey + '"]'); if (f) f.focus(); }
    var ids = [];
    cfg.charts.forEach(function (c) { c.metrics.forEach(function (m) { if (ids.indexOf(m.id) < 0) ids.push(m.id); }); });
    var rightPad = cfg.charts.some(function (c) { return mxSeries(c, null).units.length > 1; });
    function draw(d) {
      state.matrixGran = d.gran;
      note.innerHTML = '';
      if (d.partial) note.appendChild(el('p', { class: 'muted small', text: 'Gộp theo ' + d.gran_label + ': ' + d.gran_label +
        ' đầu và / hoặc cuối chỉ gồm những ngày trong khoảng đang lọc nên thấp hơn bình thường. Chọn ngày từ đầu đến cuối ' +
        d.gran_label + ' để so sánh đều.' }));
      cfg.charts.forEach(function (c, ci) { cards[ci].slot.innerHTML = ''; mxDrawChart(cards[ci], c, d, ci, rightPad); });
    }
    if (!ids.length) { cards.forEach(function (cd) { cd.slot.appendChild(el('p', { class: 'muted', text: 'Chưa chọn chỉ số nào. Chọn ở ô "+ Thêm chỉ số" hoặc một bộ chọn sẵn.' })); }); return; }
    var p = filterParams();
    p.set('metrics', ids.join(','));
    if (store('matrix.gran')) p.set('gran', store('matrix.gran'));
    var key = p.toString();
    if (state.mxData && state.mxData.key === key) { draw(state.mxData.d); return; }
    cards.forEach(function (cd) { cd.slot.appendChild(el('p', { class: 'muted loading-msg', text: 'Đang tải…' })); });
    content.setAttribute('aria-busy', 'true');
    $('#btn-apply').disabled = true;
    setDirty(false);
    api('/api/matrix?' + key).then(function (d) {
      if (!current() || state.mxSeq !== seq) return;
      d.byId = {};
      d.metrics.forEach(function (m) { d.byId[m.id] = m; });
      state.mxData = { key: key, d: d };
      draw(d);
      announce('Đã tải ' + ids.length + ' chỉ số, gộp theo ' + d.gran_label);
    }).catch(function (e) {
      if (current() && state.mxSeq === seq) cards.forEach(function (cd) { cd.slot.innerHTML = ''; cd.slot.appendChild(el('p', { class: 'error', text: e.message })); });
    }).then(function () { if (current()) { $('#btn-apply').disabled = false; content.removeAttribute('aria-busy'); } });
  }

  // ma trận sản phẩm: x = ACoS, y = doanh số QC, kích thước = Spend, màu theo nhóm (series); vạch dọc = ACoS mục tiêu
  function bubbleChart(parent, spec) {
    var base = chartBase(), card = vizCard(parent, spec, 360);
    newChart(card.canvas, {
      type: 'bubble',
      data: { datasets: spec.series.map(function (s) {
        var c = roleColor(s.color);
        return { label: s.name, data: s.values, backgroundColor: c + '99', borderColor: c, borderWidth: 1.5,
                 pointStyle: function (ctx) { return (ctx.raw && ctx.raw.pt) || 'circle'; } };
      }) },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        scales: { x: axisCfg(base, spec.x_unit || 'pct', { beginAtZero: true, title: { display: true, text: 'ACoS', color: base.text } }),
                  y: axisCfg(base, spec.unit, { beginAtZero: true }) },
        plugins: {
          legend: { position: 'bottom', labels: { color: base.text, usePointStyle: true, pointStyle: 'circle', padding: 14 } },
          tooltip: { callbacks: {
            title: function (items) { return items.length ? items[0].raw.label : ''; },
            label: function (ctx) {
              var p = ctx.raw;
              return [' Doanh số QC: ' + fmtUnit(p.y, spec.unit), ' Spend: ' + fmt(p.spend, 'money'), ' ACoS: ' + fmt(p.acos, 'pct'),
                      ' ACoS hòa vốn: ' + (p.be === null || p.be === undefined ? 'chưa có giá vốn' : fmt(p.be, 'pct')), ' Tồn kho: ' + ctx.dataset.label];
            } } },
          refLines: { lines: spec.refs || [], axis: 'x', color: base.text }
        }
      },
      plugins: [refLinePlugin]
    });
  }

  function lineChart(parent, spec, opts) {
    opts = opts || {};
    var base = chartBase(), card = vizCard(parent, spec, opts.matrix ? 240 : 280), p = provisionalFrom();
    // trục ngày: đoạn đi vào ngày tạm tính vẽ nét đứt, chấm rỗng
    // (chỉ số liệu thực tế; đường mục tiêu nét đứt (s.dash) không có ngày tạm tính)
    var prov = spec.labels.map(function (l) { return !!p && /^\d{4}-\d{2}-\d{2}$/.test(l) && l >= p; });
    var hasProv = spec.series.some(function (s) {
      return !s.dash && s.values.some(function (v, i) { return prov[i] && v !== null && v !== undefined; });
    });
    if (hasProv) {
      card.box.insertBefore(el('p', { class: 'muted small', text: 'Nét đứt: ngày ' + dayMonth(p) + ' trở đi chưa nạp đủ dữ liệu (tạm tính).' }), card.wrap);
    }
    var cfg = {
      type: 'line',
      data: { labels: spec.labels, datasets: spec.series.map(function (s) {
        return { label: s.name, data: s.values, borderColor: roleColor(s.color), backgroundColor: roleColor(s.color),
                 borderWidth: s.dash ? 1.5 : 2, borderDash: s.dash ? [6, 4] : undefined, tension: 0.2, spanGaps: true,
                 pointRadius: s.dash ? 0 : prov.map(function (x) { return x ? 3 : 0; }), pointHoverRadius: 4,
                 pointBackgroundColor: base.surface,
                 segment: { borderDash: function (ctx) { return !s.dash && prov[ctx.p1DataIndex] ? [5, 4] : undefined; } } };
      }) },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: 'index', intersect: false },
        scales: { x: catAxis(base, { ticks: { color: base.text, maxTicksLimit: 8, maxRotation: 0,
                    callback: function (v) { var l = spec.labels[v]; return isIsoDate(l) ? dayMonth(l) : l; } } }),
                  y: axisCfg(base, spec.unit, { beginAtZero: true }) },
        plugins: {
          legend: legendCfg(base, spec, seriesSums(spec), 'line', true),
          tooltip: { callbacks: { title: function (items) { return items.length ? dmy(items[0].label) : ''; },
                                  label: function (ctx) { return ' ' + ctx.dataset.label + ': ' + fmtUnit(ctx.raw, spec.unit); } } }
        }
      }
    };
    if (opts.matrix) matrixCfg(cfg, spec);
    return newChart(card.canvas, cfg);
  }

  function dayLabel(asOf, n) {
    var d = new Date(asOf + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + Math.round(n));
    return ('0' + d.getUTCDate()).slice(-2) + '/' + ('0' + (d.getUTCMonth() + 1)).slice(-2);
  }

  // lịch đứt hàng: mỗi SKU một hàng; xanh = còn đủ bán, đỏ = đứt hàng tới lô kế (◆)
  function ganttChart(parent, spec, tables) {
    var rows = spec.rows || [], base = chartBase();
    if (!rows.length) {
      var empty = vizCard(parent, spec, 60);
      empty.wrap.textContent = 'Không có SKU nào dự kiến đứt hàng trong 90 ngày tới với bộ lọc hiện tại.';
      return;
    }
    var card = vizCard(parent, spec, Math.min(rows.length * 26 + 80, 600));
    var labels = rows.map(function (r) { return r.label; });
    var selected = state.invSku;
    function rowOf(item) { return rows[item.dataIndex]; }
    var cont = spec.qty_unit === 'cont';
    function qtyText(v, rate) { return cont ? fmt(v, rate ? 'num2' : 'num2') + ' cont' : fmt(v, rate ? 'num2' : 'int') + ' unit'; }
    var ink = cssVar('--text') || '#1d2330';
    // ◆ = ngày lô hàng kế tiếp về (vẽ trực tiếp, không thêm dataset)
    var diamonds = {
      id: 'arrivalDiamonds',
      afterDatasetsDraw: function (chart) {
        var ctx = chart.ctx, xs = chart.scales.x, ys = chart.scales.y;
        ctx.save();
        rows.forEach(function (r, i) {
          if (r.arrival_day === null) return;
          var x = xs.getPixelForValue(r.arrival_day), y = ys.getPixelForValue(i), h = 6;
          ctx.beginPath(); ctx.moveTo(x, y - h); ctx.lineTo(x + h, y); ctx.lineTo(x, y + h); ctx.lineTo(x - h, y); ctx.closePath();
          ctx.fillStyle = ink; ctx.strokeStyle = base.surface; ctx.lineWidth = 2; ctx.fill(); ctx.stroke();
        });
        ctx.restore();
      }
    };
    newChart(card.canvas, {
      type: 'bar',
      data: { labels: labels, datasets: [
        { label: 'Còn đủ bán', data: rows.map(function (r) { return [0, r.stock_days]; }), backgroundColor: roleColor('st:OK'),
          borderColor: base.surface, borderWidth: 1, borderSkipped: false, borderRadius: 3, maxBarThickness: 16, grouped: false },
        { label: 'Đứt hàng', data: rows.map(function (r) { return [r.stock_days, r.gap_end]; }), backgroundColor: stripes(roleColor('st:OOS')),
          borderColor: base.surface, borderWidth: 1, borderSkipped: false, borderRadius: 3, maxBarThickness: 16, grouped: false },
      ] },
      options: {
        indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: 'nearest', axis: 'y', intersect: false },
        scales: {
          x: { type: 'linear', min: 0, max: spec.horizon, grid: { color: base.grid }, border: { display: false },
               ticks: { color: base.text, stepSize: 7, callback: function (v) { return dayLabel(spec.as_of, v); } } },
          y: { type: 'category', labels: labels, grid: { display: false }, border: { color: base.grid },
               ticks: { color: function (ctx) { var r = rows[ctx.index]; return r && selected && r.product_id === selected.product_id && r.node_id === selected.node_id ? (cssVar('--accent') || '#2f6fde') : base.text; },
                        font: { size: 11 } } }
        },
        plugins: {
          legend: { position: 'bottom', labels: { color: base.text, usePointStyle: true, boxWidth: 10, padding: 14 } },
          tooltip: { callbacks: {
            title: function (items) { var r = rowOf(items[0]); return r.product_sku + ' · ' + r.node; },
            label: function (ctx) {
              var r = rowOf(ctx);
              if (ctx.datasetIndex === 0) return ' Còn đủ bán tới ' + dayLabel(spec.as_of, r.stock_days) + ' (' + r.stock_days + ' ngày)';
              return ' Đứt hàng ' + (r.gap_end - r.stock_days) + ' ngày · thiếu ~' + qtyText(r.lost_units) + ' · mất ~' +
                fmt(r.lost_sales, 'money') + (r.arrival_day !== null ? ' · lô kế về ' + dayLabel(spec.as_of, r.arrival_day) : '');
            },
            footer: function (items) { var r = rowOf(items[0]); return 'Tồn khả dụng ' + qtyText(r.available) + ' · bán ' + qtyText(r.velocity, true) + '/ngày'; }
          } }
        },
        onHover: function (evt, els) { evt.native.target.style.cursor = els.length ? 'pointer' : 'default'; },
        onClick: function (evt, els) {
          if (!els.length) return;
          var r = rows[els[0].index];
          state.invSku = { node_id: r.node_id, product_id: r.product_id, label: r.label };
          var spec2 = { tables: spec.tables, series: [],
                        label_filters: [{ opts: { status: '' }, cols: { product_sku: [r.product_sku], node: [r.node] } }] };
          vizClick(spec2, 0, -1, tables);
        }
      },
      plugins: [diamonds]
    });
  }

  // đường tồn một SKU: 60 ngày qua (thực tế) + 120 ngày tới (dự kiến), hàng về ▲
  function skuLineChart(parent, spec) {
    var pick = state.invSku || spec.initial;
    var card = vizCard(parent, spec, 300);
    if (!pick) { card.wrap.textContent = 'Chọn một SKU ở lịch đứt hàng hoặc trong bảng.'; return; }
    var head = card.box.querySelector('h3');
    head.textContent = 'Đường tồn dự kiến · ' + pick.label;
    var seq = state.loadSeq;
    api('/api/inv/series?node_id=' + encodeURIComponent(pick.node_id) + '&product_id=' + pick.product_id + '&qty_unit=' + qtyUnit()).then(function (d) {
      var cont = d.qty_unit === 'cont', qf = cont ? 'num2' : 'int', qs = cont ? ' cont' : '';
      if (seq !== state.loadSeq) return;
      var base = chartBase(), labels = [], hist = [], proj = [], arr = [];
      d.history.forEach(function (h) { labels.push(h.date); hist.push(h.on_hand); proj.push(null); arr.push(null); });
      var todayIdx = labels.length;
      var rnd = function (v) { return cont ? Math.round(v * 1000) / 1000 : Math.round(v * 10) / 10; };
      d.projection.forEach(function (p) {
        labels.push(p.date); hist.push(null); proj.push(rnd(p.stock)); arr.push(p.arrived > 0 ? rnd(p.stock) : null);
      });
      if (d.history.length) proj[todayIdx - 1] = hist[todayIdx - 1];  // nối đoạn thực tế với đoạn dự kiến
      var events = {};
      d.events.forEach(function (e) { (events[e.date] = events[e.date] || []).push(e); });
      card.box.querySelector('p') || card.box.insertBefore(el('p', { class: 'muted small' }), card.wrap);
      card.box.querySelector('p').textContent = (d.no_volume ? 'SKU chưa có thể tích nên không quy ra container được. ' : '') +
        'Tồn khả dụng ' + fmt(d.available, qf) + qs + ' · bán ' + fmt(d.velocity, cont ? 'num2' : 'num2') + qs +
        '/ngày · ' + d.events.length + ' lô hàng về trong dự báo. Đường liền = tồn thực tế (on hand), nét đứt = dự kiến.';
      newChart(card.canvas, {
        type: 'line',
        data: { labels: labels, datasets: [
          { label: 'Tồn thực tế', data: hist, borderColor: roleColor('n1'), backgroundColor: roleColor('n1'), borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, stepped: true },
          { label: 'Tồn dự kiến', data: proj, borderColor: roleColor('c1'), backgroundColor: roleColor('c1'), borderWidth: 2, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 4 },
          { label: 'Hàng về', data: arr, showLine: false, pointStyle: 'triangle', radius: 7, hoverRadius: 9,
            backgroundColor: roleColor('c2'), borderColor: base.surface, borderWidth: 2 }
        ] },
        options: {
          responsive: true, maintainAspectRatio: false, animation: false,
          interaction: { mode: 'index', intersect: false },
          scales: { x: catAxis(base, { ticks: { color: base.text, maxTicksLimit: 9, maxRotation: 0,
                      callback: function (v) { return String(labels[v]).slice(8, 10) + '/' + String(labels[v]).slice(5, 7); } } }),
                    y: axisCfg(base, cont ? 'cont' : 'int', { beginAtZero: true }) },
          plugins: {
            legend: { position: 'bottom', labels: { color: base.text, usePointStyle: true, padding: 14 } },
            tooltip: { callbacks: {
              label: function (ctx) { return ctx.raw === null ? null : ' ' + ctx.dataset.label + ': ' + fmt(ctx.raw, qf) + qs; },
              afterBody: function (items) {
                var ev = events[labels[items[0].dataIndex]];
                return ev ? ev.map(function (e) { return 'Về +' + fmt(e.qty, qf) + qs + ' · ' + e.stage + (e.eta && e.eta < d.as_of ? ' (quá ETA)' : ''); }) : [];
              }
            } },
            refLines: { lines: [{ value: todayIdx - 0.5, label: 'Hôm nay' }], axis: 'x', color: base.text }
          }
        },
        plugins: [refLinePlugin]
      });
    }).catch(function (e) { card.wrap.textContent = e.message; });
  }

  // ---------- bản đồ Mỹ theo bang (kind 'us_map'): labels = mã bang, series[0] = giá trị, details = các kho trong bang ----------
  // Hình bang lấy từ us-atlas (đã chiếu Albers, khung 975×610), tải một lần khi cần. Màu tuần tự một hue: nhạt -> đậm.
  var US_FIPS = { '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC',
    '12': 'FL', '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN', '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA',
    '23': 'ME', '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS', '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV',
    '33': 'NH', '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND', '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA',
    '44': 'RI', '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT', '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV',
    '55': 'WI', '56': 'WY' };
  // bang nhỏ ở bờ Đông: nhãn đặt ra lề phải kèm đường dẫn
  var US_SMALL = { CT: 1, DE: 1, DC: 1, MA: 1, MD: 1, NH: 1, NJ: 1, RI: 1, VT: 1 };
  var usAtlas = null;
  function loadUsAtlas() {
    if (usAtlas) return usAtlas;
    usAtlas = new Promise(function (resolve, reject) {
      if (window.topojson) return resolve();
      var s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js';
      s.onload = resolve;
      s.onerror = function () { reject(new Error('Không tải được thư viện bản đồ')); };
      document.head.appendChild(s);
    }).then(function () {
      return fetch('https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-albers-10m.json');
    }).then(function (r) {
      if (!r.ok) throw new Error('Không tải được bản đồ Mỹ');
      return r.json();
    }).then(function (topo) {
      return window.topojson.feature(topo, topo.objects.states).features.map(function (f) {
        var polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates, d = '', best = null, bestA = -1;
        polys.forEach(function (poly) {
          poly.forEach(function (ring) {
            d += 'M' + ring.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join('L') + 'Z';
          });
          // tâm nhãn = trọng tâm vòng ngoài lớn nhất
          var ring = poly[0], a = 0, cx = 0, cy = 0;
          for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
            var k = ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1];
            a += k; cx += (ring[j][0] + ring[i][0]) * k; cy += (ring[j][1] + ring[i][1]) * k;
          }
          if (Math.abs(a) > bestA) { bestA = Math.abs(a); best = [cx / (3 * a), cy / (3 * a)]; }
        });
        return { code: US_FIPS[f.id], name: f.properties.name, d: d, c: best };
      }).filter(function (s) { return s.code; });
    });
    usAtlas.catch(function () { usAtlas = null; });  // lỗi mạng: lần sau thử lại
    return usAtlas;
  }

  function mixHex(a, b, t) {
    var pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16), out = '#';
    [16, 8, 0].forEach(function (sh) {
      var x = Math.round(((pa >> sh) & 255) + (((pb >> sh) & 255) - ((pa >> sh) & 255)) * t);
      out += ('0' + x.toString(16)).slice(-2);
    });
    return out;
  }

  function usMapChart(parent, spec, tables) {
    var card = vizCard(parent, spec, 0), wrap = card.wrap;
    card.box.classList.add('viz-wide');
    wrap.style.height = '';
    wrap.textContent = 'Đang tải bản đồ…';
    var dark = isDark();
    var lo = dark ? '#1f3550' : '#d3e4f8', hi = dark ? '#8dbcf7' : '#174f94', empty = dark ? '#2a2f3a' : '#eceef2';
    var vals = {}, max = 0;
    spec.labels.forEach(function (code, i) { vals[code] = spec.series[0].values[i] || 0; max = Math.max(max, vals[code]); });
    function fill(v) { return v > 0 && max > 0 ? mixHex(lo, hi, v / max) : empty; }
    function pick(code) { var i = spec.labels.indexOf(code); if (i >= 0) vizClick(spec, i, 0, tables); }
    var tip = el('div', { class: 'map-tip', role: 'status' });
    function showTip(code, name, evt) {
      var rows = (spec.details || {})[code] || [];
      tip.innerHTML = '';
      tip.appendChild(el('strong', { text: name + ': ' + fmtUnit(vals[code] || 0, spec.unit) }));
      rows.forEach(function (r) { tip.appendChild(el('div', { text: r[0] + ': ' + fmtUnit(r[1], spec.unit) })); });
      if (!rows.length) tip.appendChild(el('div', { class: 'muted', text: 'Không có kho CastleGate' }));
      var box = wrap.getBoundingClientRect(), x = evt.clientX - box.left, y = evt.clientY - box.top;
      if (evt.clientX === undefined) { var r0 = evt.target.getBoundingClientRect(); x = r0.left - box.left + r0.width / 2; y = r0.top - box.top; }
      tip.style.left = Math.min(x + 12, box.width - 220) + 'px';
      tip.style.top = (y + 12) + 'px';
      tip.style.display = 'block';
    }
    function hideTip() { tip.style.display = 'none'; }

    loadUsAtlas().then(function (states) {
      wrap.textContent = '';
      var NS = 'http://www.w3.org/2000/svg';
      function s(tag, attrs) {
        var n = document.createElementNS(NS, tag);
        Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
        return n;
      }
      var known = {};
      var svg = s('svg', { viewBox: '0 0 1010 610', class: 'us-map', role: 'img',
        'aria-label': spec.title + '. ' + spec.labels.map(function (c) { return c + ' ' + fmtUnit(vals[c], spec.unit); }).join(', ') });
      var gStates = s('g', {}), gLabels = s('g', { 'pointer-events': 'none' });
      var smallY = 150;
      states.forEach(function (st) {
        known[st.code] = 1;
        var v = vals[st.code] || 0;
        var p = s('path', { d: st.d, fill: fill(v), class: v > 0 ? 'st has' : 'st' });
        if (v > 0) {
          p.setAttribute('tabindex', '0');
          p.setAttribute('aria-label', st.name + ': ' + fmtUnit(v, spec.unit));
          p.addEventListener('click', function () { pick(st.code); });
          p.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(st.code); } });
          p.addEventListener('focus', function (e) { showTip(st.code, st.name, e); });
          p.addEventListener('blur', hideTip);
        }
        p.addEventListener('mousemove', function (e) { showTip(st.code, st.name, e); });
        p.addEventListener('mouseleave', hideTip);
        gStates.appendChild(p);
        if (!(v > 0) || !st.c) return;
        // nhãn chữ dùng màu chữ, có viền nền để đọc được trên mọi độ đậm
        var lx = st.c[0], ly = st.c[1], anchor = 'middle';
        if (US_SMALL[st.code]) {
          lx = 940; ly = smallY; smallY += 34; anchor = 'start';
          gLabels.appendChild(s('line', { x1: st.c[0], y1: st.c[1], x2: lx - 4, y2: ly - 4, class: 'lead' }));
        }
        var t = s('text', { x: lx, y: ly, 'text-anchor': anchor, class: 'st-label' });
        t.appendChild(s('tspan', { x: lx, dy: '-0.2em', class: 'code' })).textContent = st.code;
        t.appendChild(s('tspan', { x: lx, dy: '1.15em' })).textContent = compact(v, spec.unit === 'cont' ? 'cont' : 'int');
        gLabels.appendChild(t);
      });
      svg.appendChild(gStates);
      svg.appendChild(gLabels);
      wrap.appendChild(svg);
      wrap.appendChild(tip);

      // thang màu + các kho ngoài Mỹ (vd Canada) cùng thang
      var foot = el('div', { class: 'map-foot' });
      foot.appendChild(el('span', { class: 'map-scale' }, [
        el('span', { class: 'muted small', text: '0' }),
        el('span', { class: 'map-ramp', style: 'background: linear-gradient(90deg, ' + lo + ', ' + hi + ')' }),
        el('span', { class: 'muted small', text: fmtUnit(max, spec.unit) })
      ]));
      spec.labels.filter(function (c) { return !known[c]; }).forEach(function (code) {
        var rows = (spec.details || {})[code] || [], name = code === 'CAN' ? 'Canada' : code;
        foot.appendChild(el('button', { type: 'button', class: 'map-out',
          title: rows.map(function (r) { return r[0] + ': ' + fmtUnit(r[1], spec.unit); }).join('\n'),
          onclick: function () { pick(code); } }, [
          el('span', { class: 'swatch', style: 'background:' + fill(vals[code]) }),
          'Ngoài Mỹ – ' + name + ' (' + rows.map(function (r) { return r[0].split(' - ').slice(1).join(' - '); }).join(', ') + '): ' + fmtUnit(vals[code], spec.unit)
        ]));
      });
      card.box.appendChild(foot);
    }).catch(function (e) { wrap.textContent = e.message; });
  }

  // ---------- bản đồ phân bổ theo nước (kind 'geo_map'): màu = tỷ trọng nhu cầu, vòng tròn = tồn kho nội bộ / CastleGate ----------
  // Mỹ dùng us-atlas (đã chiếu, như us_map); Canada / Úc lấy ranh giới tỉnh, bang từ Natural Earth 1:50m (public domain),
  // chiếu phẳng có hiệu chỉnh vĩ độ rồi co vào khung 900 px. Tải một lần, dùng lại.
  var NE_URL = 'https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@v5.1.2/geojson/ne_50m_admin_1_states_provinces.geojson';
  var neGeo = null, geoCache = {};
  function loadNe() {
    if (neGeo) return neGeo;
    neGeo = fetch(NE_URL).then(function (r) {
      if (!r.ok) throw new Error('Không tải được bản đồ tỉnh / bang');
      return r.json();
    });
    neGeo.catch(function () { neGeo = null; });
    return neGeo;
  }
  function projectNe(features, lat0, W) {
    var k = Math.cos(lat0 * Math.PI / 180), minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    function xy(p) { return [p[0] * k, -p[1]]; }
    features.forEach(function (f) {
      f.polys.forEach(function (poly) { poly[0].forEach(function (p) {
        var q = xy(p); minX = Math.min(minX, q[0]); maxX = Math.max(maxX, q[0]); minY = Math.min(minY, q[1]); maxY = Math.max(maxY, q[1]);
      }); });
    });
    var s = W / (maxX - minX), H = Math.round((maxY - minY) * s);
    var shapes = features.map(function (f) {
      var d = '', best = null, bestA = -1;
      f.polys.forEach(function (poly) {
        poly.forEach(function (ring) {
          d += 'M' + ring.map(function (p) { var q = xy(p); return ((q[0] - minX) * s).toFixed(1) + ',' + ((q[1] - minY) * s).toFixed(1); }).join('L') + 'Z';
        });
        var ring = poly[0].map(function (p) { var q = xy(p); return [(q[0] - minX) * s, (q[1] - minY) * s]; }), a = 0, cx = 0, cy = 0;
        for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
          var c = ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1];
          a += c; cx += (ring[j][0] + ring[i][0]) * c; cy += (ring[j][1] + ring[i][1]) * c;
        }
        if (Math.abs(a) > bestA && a !== 0) { bestA = Math.abs(a); best = [cx / (3 * a), cy / (3 * a)]; }
      });
      return { code: f.code, name: f.name, d: d, c: best };
    });
    return { shapes: shapes, w: W, h: H };
  }
  function loadGeo(cc) {
    if (geoCache[cc]) return geoCache[cc];
    var p;
    if (cc === 'US') {
      p = loadUsAtlas().then(function (states) { return { shapes: states, w: 975, h: 610 }; });
    } else {
      var a3 = cc === 'CA' ? 'CAN' : 'AUS';
      p = loadNe().then(function (geo) {
        var feats = geo.features.filter(function (f) { return f.properties.adm0_a3 === a3 && f.geometry; }).map(function (f) {
          var polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
          // Úc: bỏ đảo xa ngoài khung lục địa + Tasmania (vd Macquarie, đảo biển Coral)
          if (cc === 'AU') polys = polys.filter(function (poly) { return poly[0].every(function (pt) { return pt[0] > 112 && pt[0] < 155 && pt[1] > -44.5; }); });
          // mã vùng = phần sau "AU-" / "CA-" của ISO 3166-2 (postal của Úc là NS, QL... không khớp NSW, QLD)
          var code = String((f.properties.iso_3166_2 || '').split('-')[1] || f.properties.postal || '').toUpperCase();
          return { code: code, name: f.properties.name, polys: polys };
        }).filter(function (f) { return f.polys.length && /^[A-Z]{2,3}$/.test(f.code); });  // bỏ Jervis Bay (AU-X02~)
        return projectNe(feats, cc === 'CA' ? 58 : -27, 900);
      });
    }
    geoCache[cc] = p;
    p.catch(function () { delete geoCache[cc]; });
    return p;
  }

  function geoMapChart(parent, spec) {
    var card = vizCard(parent, spec, 0), wrap = card.wrap;
    card.box.classList.add('viz-wide');
    wrap.style.height = '';
    wrap.textContent = 'Đang tải bản đồ…';
    var dark = isDark(), unit = spec.unit === 'cont' ? 'cont' : 'int';
    var lo = dark ? '#2a303b' : '#eef0f4', hi = dark ? '#a9b4c9' : '#5b6578', empty = dark ? '#22262e' : '#f6f7f9';
    var cLocal = roleColor('c1'), cCg = roleColor('c2');
    var regions = spec.regions || {}, maxShare = 0, maxStock = 0;
    Object.keys(regions).forEach(function (k) {
      maxShare = Math.max(maxShare, regions[k].demand_share || 0);
      maxStock = Math.max(maxStock, regions[k].local || 0, regions[k].cg || 0);
    });
    function fill(sh) { return sh > 0 && maxShare > 0 ? mixHex(lo, hi, Math.sqrt(sh / maxShare)) : empty; }
    function pct(x) { return (x * 100).toFixed(x >= 0.1 ? 0 : 1) + '%'; }
    var tip = el('div', { class: 'map-tip', role: 'status' });
    function showTip(code, name, evt) {
      var r = regions[code] || { demand: 0, orders: 0, demand_share: 0, local: 0, cg: 0, stock_share: 0, whs: [] };
      tip.innerHTML = '';
      tip.appendChild(el('strong', { text: name + ' (' + code + ')' }));
      tip.appendChild(el('div', { text: 'Nhu cầu 90 ngày: ' + fmtUnit(r.demand, spec.unit) + ' · ' + pct(r.demand_share) + ' cả nước (' + r.orders + ' đơn)' }));
      if ((r.channels || []).length) tip.appendChild(el('div', { class: 'muted', text: r.channels.map(function (c) { return c[0] + ' ' + fmtUnit(c[1], spec.unit); }).join(' · ') }));
      tip.appendChild(el('div', { text: 'Tồn trong bang: ' + fmtUnit(r.local + r.cg, spec.unit) + ' · ' + pct(r.stock_share) + ' tồn cả nước' }));
      r.whs.forEach(function (w) { tip.appendChild(el('div', { class: 'muted', text: '• ' + w[0] + ': ' + fmtUnit(w[2], spec.unit) })); });
      var box = wrap.getBoundingClientRect(), x = evt.clientX - box.left, y = evt.clientY - box.top;
      if (evt.clientX === undefined) { var r0 = evt.target.getBoundingClientRect(); x = r0.left - box.left + r0.width / 2; y = r0.top - box.top; }
      tip.style.left = Math.max(0, Math.min(x + 12, box.width - 260)) + 'px';
      tip.style.top = (y + 12) + 'px';
      tip.style.display = 'block';
    }
    function hideTip() { tip.style.display = 'none'; }

    loadGeo(spec.country).then(function (g) {
      wrap.textContent = '';
      var NS = 'http://www.w3.org/2000/svg';
      function s(tag, attrs) {
        var n = document.createElementNS(NS, tag);
        Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
        return n;
      }
      var R = Math.max(10, g.w / 34);  // bán kính lớn nhất
      function rad(v) { return v > 0 && maxStock > 0 ? Math.max(3, R * Math.sqrt(v / maxStock)) : 0; }
      var svg = s('svg', { viewBox: '0 0 ' + g.w + ' ' + g.h, class: 'us-map geo-map', role: 'img',
        style: '--lbl:' + Math.round(Math.max(g.w, g.h) / 52) + 'px',
        'aria-label': spec.title + '. ' + Object.keys(regions).map(function (c) {
          return c + ': nhu cầu ' + pct(regions[c].demand_share) + ', tồn ' + pct(regions[c].stock_share); }).join('; ') });
      var gS = s('g', {}), gB = s('g', { 'pointer-events': 'none' }), gL = s('g', { 'pointer-events': 'none' });
      var seen = {};
      g.shapes.forEach(function (st) {
        seen[st.code] = 1;
        var r = regions[st.code], sh = r ? r.demand_share : 0;
        var p = s('path', { d: st.d, fill: fill(sh), class: 'st has', tabindex: '0', 'aria-label': st.name });
        p.addEventListener('mousemove', function (e) { showTip(st.code, st.name, e); });
        p.addEventListener('mouseleave', hideTip);
        p.addEventListener('focus', function (e) { showTip(st.code, st.name, e); });
        p.addEventListener('blur', hideTip);
        gS.appendChild(p);
        if (!r || !st.c) return;
        var rl = rad(r.local), rc = rad(r.cg), x = st.c[0], y = st.c[1];
        if (rl && rc) {  // cả hai loại kho: đặt cạnh nhau
          gB.appendChild(s('circle', { cx: x - rc * 0.6, cy: y, r: rl, fill: cLocal, 'fill-opacity': 0.8, class: 'bub' }));
          gB.appendChild(s('circle', { cx: x + rl * 0.6, cy: y, r: rc, fill: cCg, 'fill-opacity': 0.8, class: 'bub' }));
        } else if (rl || rc) {
          gB.appendChild(s('circle', { cx: x, cy: y, r: rl || rc, fill: rl ? cLocal : cCg, 'fill-opacity': 0.8, class: 'bub' }));
        }
        if (sh >= 0.03 || rl || rc) {  // nhãn cho bang có nhu cầu đáng kể hoặc có kho
          var t = s('text', { x: x, y: y - Math.max(rl, rc) - 4, 'text-anchor': 'middle', class: 'st-label' });
          t.textContent = st.code + ' ' + pct(sh);
          gL.appendChild(t);
        }
      });
      svg.appendChild(gS); svg.appendChild(gB); svg.appendChild(gL);
      wrap.style.position = 'relative';
      wrap.appendChild(svg);
      wrap.appendChild(tip);

      var foot = el('div', { class: 'map-foot' });
      foot.appendChild(el('span', { class: 'map-scale' }, [
        el('span', { class: 'muted small', text: 'Nhu cầu: ít' }),
        el('span', { class: 'map-ramp', style: 'background: linear-gradient(90deg, ' + lo + ', ' + hi + ')' }),
        el('span', { class: 'muted small', text: 'nhiều (' + pct(maxShare) + ')' })
      ]));
      function dot(color, text) {
        return el('span', { class: 'map-scale' }, [el('span', { class: 'swatch', style: 'width:12px;height:12px;border-radius:50%;display:inline-block;background:' + color }),
          el('span', { class: 'small', text: text })]);
      }
      var tl = 0, tc = 0;
      Object.keys(regions).forEach(function (k) { tl += regions[k].local || 0; tc += regions[k].cg || 0; });
      if (tl) foot.appendChild(dot(cLocal, 'Kho nội bộ: ' + fmtUnit(tl, spec.unit)));
      if (tc) foot.appendChild(dot(cCg, 'CastleGate: ' + fmtUnit(tc, spec.unit)));
      if (spec.show_fba) foot.appendChild(el('span', { class: 'small muted', text: 'FBA (chưa rõ trung tâm, không vẽ): ' + fmtUnit(spec.fba || 0, spec.unit) }));
      (spec.unmapped || []).forEach(function (w) {
        foot.appendChild(el('span', { class: 'small muted', text: 'Chưa rõ bang – ' + w[0] + ': ' + fmtUnit(w[2], spec.unit) }));
      });
      var off = Object.keys(regions).filter(function (k) { return !seen[k] && regions[k].demand > 0; });
      if (off.length) foot.appendChild(el('span', { class: 'small muted', text: 'Ngoài bản đồ: ' + off.map(function (k) {
        return k + ' ' + pct(regions[k].demand_share); }).join(', ') }));
      card.box.appendChild(foot);
    }).catch(function (e) { wrap.textContent = e.message; });
  }

  function renderViz(content, data) {
    var grid = el('div', { class: 'viz-grid' });
    content.appendChild(grid);
    (data.viz || []).forEach(function (spec) {
      if (spec.kind === 'gantt') ganttChart(grid, spec, data.tables);
      else if (spec.kind === 'us_map') usMapChart(grid, spec, data.tables);
      else if (spec.kind === 'geo_map') geoMapChart(grid, spec);
      else if (spec.kind === 'sku_line') skuLineChart(grid, spec);
      else if (spec.kind === 'line') lineChart(grid, spec);
      else if (spec.kind === 'scatter') bubbleChart(grid, spec);
      else if (spec.labels && spec.labels.length) categoryChart(grid, spec, data.tables);
    });
  }

  // Mặc định chỉ tính những ngày đủ dữ liệu của mọi nguồn trong sàn đang xem (với Tổng hợp: khoảng chung của các
  // kênh), để tổng kỳ và % so kỳ trước không lệch. Ngày kết thúc chọn quá ngày đó bị lùi lại; người dùng bấm "Xem cả
  // ngày tạm tính" để giữ nguyên (tới lần đổi ngày tiếp theo).
  function trimProvisional() {
    state.trimmedFrom = null;
    if (state.withProvisional || !provisionalFrom() || !datedTab()) return;
    var back = iso(lastComplete()), end = $('#f-end').value;
    if (!end || end <= back) return;
    state.trimmedFrom = end;
    $('#f-end').value = back;
    if ($('#f-start').value > back) $('#f-start').value = back;
    syncUrl();
  }

  // khoảng ngày đang xem có chứa ngày tạm tính (hoặc vừa bị lùi lại) -> báo và cho đổi
  function provisionalBanner() {
    var p = provisionalFrom(), end = $('#f-end').value;
    if (!p || !datedTab()) return null;
    var f = (state.meta || {}).freshness || {}, l = channel().freshLabels || ['Dữ liệu QC đến ', 'Doanh số đến '];
    var src = channel().fresh.map(function (k, i) { return l[i] + dayMonth(f[k] || '–'); }).join(', ');
    if (state.trimmedFrom) {
      var asked = state.trimmedFrom;
      return el('div', { class: 'warn-box', role: 'note' }, [
        'Đang xem đến ' + dayMonth(end) + ': ngày cuối đủ dữ liệu của mọi nguồn (' + src + '; ngày mới nhất thường chưa nạp đủ). '
          + 'Bạn chọn đến ' + dayMonth(asked) + ', các ngày sau ' + dayMonth(end) + ' chưa tính để tổng kỳ và so sánh kỳ trước không bị lệch. ',
        el('button', { type: 'button', text: 'Xem cả ngày tạm tính (đến ' + dayMonth(asked) + ')', onclick: function () {
          state.withProvisional = true;
          $('#f-end').value = asked;
          $('#f-preset').value = '';
          load();
        } })
      ]);
    }
    if (end < p) return null;
    var back = iso(lastComplete());
    return el('div', { class: 'warn-box', role: 'note' }, [
      'Khoảng ngày có ' + (end > p ? 'các ngày từ ' : 'ngày ') + dayMonth(p) + ' chưa nạp đủ dữ liệu (tạm tính; ' + src + '): tổng kỳ, đồ thị và so sánh kỳ trước có thể lệch. ',
      el('button', { type: 'button', text: 'Chỉ xem đến ' + dayMonth(back), onclick: function () {
        state.withProvisional = false;
        $('#f-end').value = back;
        if ($('#f-start').value > back) $('#f-start').value = back;
        $('#f-preset').value = '';
        load();
      } })
    ]);
  }

  function renderReport(content, data) {
    content.innerHTML = '';
    var banner = provisionalBanner();
    if (banner) content.appendChild(banner);
    if (data.note) content.appendChild(el('p', { class: 'note', text: data.note }));
    if (data.kpis) content.appendChild(renderKpis(data.kpis));
    (data.card_groups || []).forEach(function (g) {
      if (g.title) content.appendChild(el('h3', { class: 'cards-title', text: g.title }));
      content.appendChild(renderCards(g.cards));
    });
    if (data.cards && data.cards_title) content.appendChild(el('h3', { class: 'cards-title', text: data.cards_title }));
    if (data.cards) content.appendChild(renderCards(data.cards));
    if (data.viz && data.viz.length) {
      // tab có đồ thị: đồ thị ở trên, các bảng thu gọn bên dưới (mở lại khi bấm đồ thị để lọc)
      renderViz(content, data);
      var n = (data.tables || []).length;
      if (!n) return;
      var box = el('details', { class: 'tables-box' }), tab = state.tab;
      box.open = !!store('open.' + tab);
      box.addEventListener('toggle', function () { store('open.' + tab, box.open); });
      var filtered = (data.tables || []).filter(function (t) { return t.filter_text && t.filter_text.length; }).length;
      box.appendChild(el('summary', { text: 'Bảng chi tiết (' + n + ' bảng' + (filtered ? ', ' + filtered + ' bảng đang lọc' : '') + ')' }));
      (data.tables || []).forEach(function (t) { box.appendChild(renderTable(t)); });
      content.appendChild(box);
      return;
    }
    var charts = data.charts || {};
    if (charts.trend && charts.trend.length) {
      var row = el('div', { class: 'charts' });
      content.appendChild(row);
      var salesLabel = state.channel === 'wayfair' ? 'DS QC (giá sỉ)' : 'Ad Sales';
      addChart(row, {
        data: { labels: charts.trend.map(function (r) { return r.date; }), datasets: [
          { type: 'bar', label: 'Spend', data: charts.trend.map(function (r) { return r.spend; }), yAxisID: 'y', backgroundColor: mc('spend') },
          { type: 'bar', label: salesLabel, data: charts.trend.map(function (r) { return r.sales; }), yAxisID: 'y', backgroundColor: mc('sales') },
          { type: 'line', label: 'ACoS', data: charts.trend.map(function (r) { return r.acos; }), yAxisID: 'y1', borderColor: mc('acos'), backgroundColor: mc('acos') },
          { type: 'line', label: 'TACoS', data: charts.trend.map(function (r) { return r.tacos; }), yAxisID: 'y1', borderColor: mc('tacos'), backgroundColor: mc('tacos') }
        ] },
        options: { plugins: { title: { display: true, text: 'Spend, ' + salesLabel + ', ACoS, TACoS theo ngày' } }, scales: { y: { position: 'left' }, y1: pctAxis } }
      });
      addChart(row, {
        type: 'line',
        data: { labels: charts.trend.map(function (r) { return r.date; }), datasets: [
          { label: 'CTR', data: charts.trend.map(function (r) { return r.ctr; }), borderColor: mc('ctr'), backgroundColor: mc('ctr') },
          { label: 'CVR', data: charts.trend.map(function (r) { return r.cvr; }), borderColor: mc('sales'), backgroundColor: mc('sales') }
        ] },
        options: { plugins: { title: { display: true, text: 'CTR và CVR theo ngày' } },
          scales: { y: { ticks: { callback: function (v) { return (v * 100).toFixed(1) + '%'; } } } } }
      });
    }
    if (charts.by_length && charts.by_length.length) {
      var kr = el('div', { class: 'charts' });
      content.appendChild(kr);
      comboChart(kr, 'Hiệu suất theo số từ', charts.by_length, 'length_bucket');
      comboChart(kr, 'Hiệu suất theo phân nhóm', charts.by_class, 'term_class_label');
    }
    (data.tables || []).forEach(function (t) { content.appendChild(renderTable(t)); });
  }

  function acosTarget() {
    var inp = $('[data-opt=max_acos]');
    return inp ? Number(inp.value) : 0.3;
  }

  // ---------- bộ lọc trong từng bảng (lọc ở server, xem app/table_filters.py) ----------
  var OPS = [['gte', '≥'], ['lte', '≤'], ['gt', '>'], ['lt', '<'], ['eq', '='], ['ne', '≠']];
  var PRESETS = [
    { label: 'Tiêu tiền, 0 đơn', cond: [['spend', 'gte', 10], ['orders', 'eq', 0]] },
    { label: 'Nhiều click, 0 đơn', cond: [['clicks', 'gte', 15], ['orders', 'eq', 0]] },
    { label: 'ACoS cao (> 50%)', cond: [['spend', 'gte', 5], ['acos', 'gt', 0.5]] },
    { label: 'Hiệu quả tốt', cond: [['orders', 'gte', 2], ['acos', 'lte', 0.25]] },
    { label: 'CTR thấp', cond: [['impressions', 'gte', 1000], ['ctr', 'lt', 0.002]] }
  ];
  state.tf = {};

  function tabFilters() {
    return state.tf[state.tab] || (state.tf[state.tab] = store('tf.' + state.tab) || {});
  }

  // bộ lọc của một bảng trong tab hiện tại; truyền value để ghi
  function tableSpec(key, value) {
    var all = tabFilters();
    if (value !== undefined) {
      if (value.cond.length || Object.keys(value.cols).length) all[key] = value; else delete all[key];
      store('tf.' + state.tab, all);
    }
    var s = all[key] || {};
    return { cond: (s.cond || []).slice(), cols: Object.assign({}, s.cols || {}) };
  }

  function tfParam() {
    var all = tabFilters();
    return Object.keys(all).length ? JSON.stringify(all) : '';
  }

  // tỷ lệ nhập theo %, lưu dạng phân số
  function toInput(v, kind) { return kind === 'pct' ? +(v * 100).toFixed(4) : v; }
  function fromInput(v, kind) { var n = Number(v); return kind === 'pct' ? n / 100 : n; }

  function conditionPanel(t, spec) {
    var numeric = t.columns.filter(function (c) { return c.fmt !== 'text'; });
    var byKey = {};
    numeric.forEach(function (c) { byKey[c.key] = c; });
    var panel = el('div', { class: 'cond-panel' + (spec.cond.length ? ' open' : '') }), list = el('div');
    if (!numeric.length) return panel;
    function addRow(c) {
      var colSel = el('select', { 'aria-label': 'Chỉ số' }, numeric.map(function (n) {
        return el('option', { value: n.key, text: n.label + (n.fmt === 'pct' ? ' (%)' : n.fmt === 'money' ? ' ($)' : '') });
      }));
      var opSel = el('select', { 'aria-label': 'Phép so sánh' }, OPS.map(function (o) { return el('option', { value: o[0], text: o[1] }); }));
      var val = el('input', { type: 'number', step: 'any', placeholder: 'Giá trị', 'aria-label': 'Giá trị' });
      if (c) { colSel.value = c.k; opSel.value = c.op; val.value = toInput(c.v, (byKey[c.k] || {}).fmt); }
      var row = el('div', { class: 'cond' }, [colSel, opSel, val,
        el('button', { type: 'button', class: 'x', title: 'Bỏ điều kiện', text: '✕', onclick: function () { row.remove(); } })]);
      val.addEventListener('keydown', function (e) { if (e.key === 'Enter') apply(); });
      list.appendChild(row);
    }
    function apply() {
      var cond = [];
      $$('.cond', list).forEach(function (row) {
        var f = $$('select, input', row), k = f[0].value, v = f[2].value;
        if (v !== '') cond.push({ k: k, op: f[1].value, v: fromInput(v, byKey[k].fmt) });
      });
      spec.cond = cond;
      tableSpec(t.key, spec);
      load();
    }
    spec.cond.filter(function (c) { return byKey[c.k]; }).forEach(addRow);
    if (!list.children.length) addRow();
    var presets = PRESETS.filter(function (p) { return p.cond.every(function (c) { return byKey[c[0]]; }); });
    if (presets.length) {
      panel.appendChild(el('div', { class: 'presets' }, [el('span', { class: 'muted small', text: 'Mẫu nhanh:' })].concat(
        presets.map(function (p) {
          return el('button', { type: 'button', text: p.label, onclick: function () {
            list.innerHTML = '';
            p.cond.forEach(function (c) { addRow({ k: c[0], op: c[1], v: c[2] }); });
          } });
        }))));
    }
    panel.appendChild(list);
    panel.appendChild(el('div', { class: 'cond-actions' }, [
      el('button', { type: 'button', text: '+ Thêm điều kiện', onclick: function () { addRow(); } }),
      el('button', { type: 'button', class: 'primary', text: 'Áp dụng', onclick: apply }),
      el('span', { class: 'muted small', text: 'Các điều kiện kết hợp bằng VÀ. Ô trống (vd ACoS khi chưa có doanh số) không thỏa điều kiện nào.' })
    ]));
    return panel;
  }

  // ---------- ẩn / hiện cột (lưu trong trình duyệt theo tab + bảng; áp cả cho file HTML xuất ra) ----------
  function hiddenCols(key, value) {
    var all = store('hc.' + state.tab) || {};
    if (value !== undefined) {
      if (value.length) all[key] = value; else delete all[key];
      store('hc.' + state.tab, all);
    }
    return all[key] || [];
  }

  function hcParam() {
    var all = store('hc.' + state.tab) || {};
    return Object.keys(all).length ? JSON.stringify(all) : '';
  }

  function columnPanel(t, rerender) {
    var hidden = hiddenCols(t.key), boxes = [];
    var list = el('div', { class: 'col-list' });
    t.columns.forEach(function (c) {
      var cb = el('input', { type: 'checkbox', value: c.key });
      cb.checked = hidden.indexOf(c.key) < 0;
      boxes.push(cb);
      list.appendChild(el('label', { title: c.label }, [cb, c.label]));
    });
    function setAll(on) { boxes.forEach(function (b) { b.checked = on; }); }
    function apply() {
      var off = boxes.filter(function (b) { return !b.checked; }).map(function (b) { return b.value; });
      if (off.length === boxes.length) { alert('Cần giữ ít nhất một cột.'); return; }
      hiddenCols(t.key, off);
      rerender();
    }
    return el('div', { class: 'cond-panel col-panel' }, [
      el('div', { class: 'tools' }, [
        el('button', { type: 'button', class: 'link', text: 'Chọn hết', onclick: function () { setAll(true); } }),
        el('button', { type: 'button', class: 'link', text: 'Bỏ chọn', onclick: function () { setAll(false); } }),
        el('span', { class: 'muted small', text: 'Bỏ tick để ẩn cột. Lựa chọn được nhớ cho bảng này và áp cả khi Xuất HTML.' })
      ]),
      list,
      el('div', { class: 'cond-actions' }, [
        el('button', { type: 'button', class: 'primary', text: 'Áp dụng', onclick: apply }),
        el('button', { type: 'button', text: 'Mặc định (hiện tất cả)', onclick: function () { hiddenCols(t.key, []); rerender(); } })
      ])
    ]);
  }

  function columnFilterRow(cols, t, spec) {
    var tr = el('tr', { class: 'fr' });
    cols.forEach(function (c, i) {
      var th = el('th', { class: cellClass(c, i) });
      if (c.fmt === 'text') th.appendChild(columnFilter(t, spec, c));
      tr.appendChild(th);
    });
    return tr;
  }

  function columnFilter(t, spec, c) {
    // cột có bộ lọc mặc định (vd Trạng thái = Đang chạy, xem default_cols): bỏ lọc thì lưu null để server không áp lại
    var def = (t.default_cols || {})[c.key];
    var cur = c.key in spec.cols ? spec.cols[c.key] : def, values = (t.facets || {})[c.key];
    function save(v) {
      if (v === null && !def) delete spec.cols[c.key]; else spec.cols[c.key] = v;
      tableSpec(t.key, spec);
      load();
    }
    if (!values || typeof cur === 'string') {  // quá nhiều giá trị: lọc "chứa…"
      var inp = el('input', { type: 'search', class: 'cf-text' + (cur ? ' on' : ''), placeholder: 'chứa… ↵',
                              'aria-label': 'Lọc cột ' + c.label + ' (chứa…, Enter để áp dụng)' });
      inp.value = typeof cur === 'string' ? cur : '';
      inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') save(inp.value.trim() || null); });
      inp.addEventListener('search', function () { if (!inp.value && cur) save(null); });
      return inp;
    }
    var chosen = Array.isArray(cur) ? cur : null;
    return el('button', { type: 'button', class: 'cf-btn' + (chosen ? ' on' : ''), 'aria-haspopup': 'true',
      'aria-label': 'Lọc cột ' + c.label + (chosen ? ': ' + chosen.length + ' / ' + values.length + ' giá trị' : ': tất cả'),
      text: chosen ? chosen.length + ' / ' + values.length + ' ▾' : 'Tất cả ▾',
      onclick: function (e) { e.stopPropagation(); openValuePicker(e.currentTarget, values, chosen, save, c); } });
  }

  // danh sách chọn giá trị kiểu Excel; gắn vào body để khung cuộn của bảng không che mất
  function openValuePicker(anchor, values, chosen, save, c) {
    closePickers();
    var picked = {};
    values.forEach(function (v) { picked[v] = !chosen || chosen.indexOf(v) >= 0; });
    var find = el('input', { type: 'search', placeholder: 'Tìm giá trị…', 'aria-label': 'Tìm giá trị' }), list = el('div', { class: 'cf-list' });
    function matches(v) { var q = find.value.trim().toLowerCase(); return !q || v.toLowerCase().indexOf(q) >= 0; }
    function draw() {
      list.innerHTML = '';
      values.filter(matches).forEach(function (v) {
        var cb = el('input', { type: 'checkbox' });
        cb.checked = picked[v];
        cb.addEventListener('change', function () { picked[v] = cb.checked; });
        list.appendChild(el('label', { title: v }, [cb, v === '' ? '(trống)' : (c && c.key === 'state' && STATE_LABEL[v]) || v]));
      });
    }
    function setVisible(on) { values.filter(matches).forEach(function (v) { picked[v] = on; }); draw(); }
    var box = el('div', { class: 'cf-picker' }, [find,
      el('div', { class: 'tools' }, [el('button', { type: 'button', class: 'link', text: 'Chọn hết', onclick: function () { setVisible(true); } }),
                                     el('button', { type: 'button', class: 'link', text: 'Bỏ chọn', onclick: function () { setVisible(false); } })]),
      list,
      el('div', { class: 'cond-actions' }, [
        el('button', { type: 'button', class: 'primary', text: 'Áp dụng', onclick: function () {
          var sel = values.filter(function (v) { return picked[v]; });
          closePickers();
          save(sel.length === values.length ? null : sel);
        } }),
        el('button', { type: 'button', text: 'Bỏ lọc cột', onclick: function () { closePickers(); save(null); } })
      ])]);
    box.addEventListener('click', function (e) { e.stopPropagation(); });
    find.addEventListener('input', draw);
    draw();
    document.body.appendChild(box);
    var r = anchor.getBoundingClientRect();
    box.style.top = Math.min(r.bottom + 4, window.innerHeight - box.offsetHeight - 8) + 'px';
    box.style.left = Math.max(8, Math.min(r.left, window.innerWidth - box.offsetWidth - 8)) + 'px';
    find.focus();
  }
  function closePickers() { $$('.cf-picker').forEach(function (b) { b.remove(); }); }
  document.addEventListener('click', closePickers);
  window.addEventListener('resize', closePickers);

  // cột định danh chính (search term, keyword, campaign, SKU…) ghim bên trái khi cuộn ngang. Bảng hiệu suất QC đưa
  // Spend / Ad Sales / ACoS lên ngay sau cột đó để không bị đẩy khỏi màn hình. Thứ tự cột khi xuất file giữ như cũ.
  var PIN_KEYS = ['term', 'ngram', 'keyword', 'targeting', 'adgroup_name', 'campaign_name', 'wayfair_sku', 'product_sku', 'asin', 'purchased_asin'];
  var LEAD_KEYS = ['spend', 'sales', 'acos'];
  function arrangeColumns(columns) {
    var keys = columns.map(function (c) { return c.key; });
    var pin = PIN_KEYS.filter(function (k) { return keys.indexOf(k) >= 0; })[0] || keys[0];
    var lead = [pin].concat(keys.indexOf('spend') >= 0 ? LEAD_KEYS.filter(function (k) { return keys.indexOf(k) >= 0; }) : []);
    return lead.map(function (k) { return columns[keys.indexOf(k)]; })
      .concat(columns.filter(function (c) { return lead.indexOf(c.key) < 0; }));
  }
  // CSV: số để nguyên (không $, %, dấu phẩy) cho Excel tính được; có BOM để Excel đọc đúng tiếng Việt
  function downloadCsv(t, cols, rows) {
    function q(v) { v = v === null || v === undefined ? '' : String(v); return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
    var DEC = { money: 2, num2: 2, pct: 4 };
    function raw(c, v) {
      if (c.key === 'state' && STATE_LABEL[v]) return STATE_LABEL[v];
      return typeof v === 'number' && DEC[c.fmt] !== undefined ? +v.toFixed(DEC[c.fmt]) : v;
    }
    var lines = [cols.map(function (c) { return q(c.label); }).join(',')];
    rows.forEach(function (r) { lines.push(cols.map(function (c) { return q(raw(c, r[c.key])); }).join(',')); });
    if (t.totals) lines.push(cols.map(function (c, i) { return q(i === 0 && !(c.key in t.totals) ? 'Tổng' : raw(c, t.totals[c.key])); }).join(','));
    var blob = new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    var a = el('a', { href: URL.createObjectURL(blob), download: state.channel + '_' + t.key + '_' + $('#f-start').value + '_' + $('#f-end').value + '.csv' });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }
  function cellClass(c, i) { return (c.fmt === 'text' ? 't' : '') + (i === 0 ? ' pin' : ''); }

  function renderTable(t) {
    if (!t.keep_order) t.columns = arrangeColumns(t.columns);  // keep_order: bảng tự xếp cột (vd trang Tổng hợp)
    var section = el('section');
    var hidden = hiddenCols(t.key);
    var cols = t.columns.filter(function (c) { return hidden.indexOf(c.key) < 0; });
    if (!cols.length) cols = t.columns;
    var nHidden = t.columns.length - cols.length;
    var loaded = t.rows_before_filter !== undefined ? t.rows_before_filter : t.rows.length;
    var truncated = (t.total_rows || 0) > loaded;
    var count = fmt(t.rows.length, 'int') + (t.rows_before_filter !== undefined ? ' / ' + fmt(t.rows_before_filter, 'int') : '') +
      (truncated ? ' trong ' + fmt(t.total_rows, 'int') : '') + ' dòng';
    section.appendChild(el('h2', {}, [t.title + ' ', el('span', { class: 'muted', text: '(' + count + ')' })]));
    if (truncated) {
      // báo cáo chỉ trả các dòng đầu theo thứ tự sắp xếp; dòng Tổng vẫn tính trên mọi dòng (server)
      var more = loaded < 5000 ? el('button', { type: 'button', class: 'link', text: 'Tải tối đa 5,000 dòng', onclick: function () {
        state.rowLimit[state.tab] = 5000; load(); } }) : null;
      var noteText = t.rows_before_filter !== undefined
        ? 'Bộ lọc chạy trên ' + fmt(loaded, 'int') + ' dòng đầu (theo thứ tự sắp xếp) trong ' + fmt(t.total_rows, 'int') +
          ' dòng. Dòng Tổng tính theo các dòng thỏa bộ lọc. '
        : 'Đang hiện ' + fmt(loaded, 'int') + ' dòng đầu trong ' + fmt(t.total_rows, 'int') +
          ' dòng. Dòng Tổng tính trên cả ' + fmt(t.total_rows, 'int') + ' dòng. ';
      section.appendChild(el('p', { class: 'note' }, [noteText, more]));
    }
    var search = el('input', { type: 'search', placeholder: 'Tìm trong bảng…', 'aria-label': 'Tìm trong bảng ' + t.title });
    var spec = tableSpec(t.key), nCond = spec.cond.length, nCols = Object.keys(spec.cols).length;
    var condPanel = conditionPanel(t, spec);
    var colPanel = columnPanel(t, function () {
      var fresh = renderTable(t);
      fresh.querySelector('.col-panel').classList.add('open');
      section.replaceWith(fresh);
    });
    var tools = el('div', { class: 'table-tools' }, [search,
      el('button', { type: 'button', class: nCond ? 'on' : '', text: 'Lọc theo chỉ số' + (nCond ? ' (' + nCond + ')' : '') + ' ▾',
        onclick: function () { condPanel.classList.toggle('open'); colPanel.classList.remove('open'); } }),
      el('button', { type: 'button', class: nHidden ? 'on' : '',
        text: 'Cột' + (nHidden ? ' (' + cols.length + '/' + t.columns.length + ')' : '') + ' ▾',
        onclick: function () { colPanel.classList.toggle('open'); condPanel.classList.remove('open'); } })]);
    if (nCond || nCols) {
      tools.appendChild(el('button', { type: 'button', class: 'link', text: 'Xóa mọi bộ lọc của bảng', onclick: function () {
        tableSpec(t.key, { cond: [], cols: {} }); load(); } }));
    }
    if (t.filter_text && t.filter_text.length) {
      tools.appendChild(el('span', { class: 'muted small', text: 'Đang lọc: ' + t.filter_text.join(' · ') + ' · Tổng tính theo dòng đã lọc' }));
    }
    section.appendChild(tools);
    section.appendChild(condPanel);
    section.appendChild(colPanel);
    var wrap = el('div', { class: 'wrap' }), table = el('table'), thead = el('thead'), tbody = el('tbody');
    var sort = { key: null, asc: false }, target = acosTarget();
    var headRow = el('tr');
    cols.forEach(function (c, i) {
      var th = el('th', { class: cellClass(c, i), text: c.label, tabindex: '0', 'aria-sort': 'none',
                          title: 'Bấm (hoặc Enter) để sắp xếp theo ' + c.label });
      function sortBy() {
        sort.asc = sort.key === c.key ? !sort.asc : c.fmt === 'text';
        sort.key = c.key;
        $$('th', headRow).forEach(function (h) { h.classList.remove('sorted', 'asc'); h.setAttribute('aria-sort', 'none'); });
        th.classList.add('sorted');
        if (sort.asc) th.classList.add('asc');
        th.setAttribute('aria-sort', sort.asc ? 'ascending' : 'descending');
        draw();
      }
      th.addEventListener('click', sortBy);
      th.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); sortBy(); } });
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    thead.appendChild(columnFilterRow(cols, t, spec));
    function visibleRows() {
      var q = search.value.trim().toLowerCase();
      var rows = t.rows.filter(function (r) {
        if (!q) return true;
        return cols.some(function (c) { return c.fmt === 'text' && String(r[c.key] || '').toLowerCase().indexOf(q) >= 0; });
      });
      if (sort.key) {
        rows = rows.slice().sort(function (a, b) {
          var x = a[sort.key], y = b[sort.key];
          if (x === null || x === undefined) return 1;
          if (y === null || y === undefined) return -1;
          var r = (typeof x === 'number' && typeof y === 'number') ? x - y : String(x).localeCompare(String(y));
          return sort.asc ? r : -r;
        });
      }
      return rows;
    }
    function draw() {
      var rows = visibleRows();
      tbody.innerHTML = '';
      var frag = document.createDocumentFragment();
      rows.slice(0, 3000).forEach(function (r) {
        var tr = el('tr');
        if (t.key === 'projection' && r.node_id) {  // chọn SKU để xem đường tồn dự kiến
          tr.className = 'pick';
          tr.title = 'Bấm để xem đường tồn dự kiến';
          tr.addEventListener('click', function () {
            state.invSku = { node_id: r.node_id, product_id: r.product_id, label: r.product_sku + ' · ' + r.node };
            window.scrollTo({ top: 0, behavior: 'smooth' });
            load();
          });
        }
        cols.forEach(function (c, i) {
          var cls = cellClass(c, i);
          if (c.key === 'acos' && r.acos !== null && r.acos !== undefined) cls += r.acos <= target ? ' acos-good' : (r.acos > target * 2 ? ' acos-bad' : '');
          if (c.key === 'status_label' && STATUS_CLASS[r.status]) cls += ' ' + STATUS_CLASS[r.status];
          var td = el('td', { class: cls, text: cellText(c, r[c.key]) });
          if (c.fmt === 'text' && r[c.key]) td.title = r[c.key];
          tr.appendChild(td);
        });
        frag.appendChild(tr);
      });
      tbody.appendChild(frag);
    }
    search.addEventListener('input', draw);
    tools.insertBefore(el('button', { type: 'button', text: 'Tải CSV', title: 'Tải các dòng đang hiện (theo tìm kiếm, bộ lọc và sắp xếp hiện tại) để mở bằng Excel',
      onclick: function () { downloadCsv(t, cols, visibleRows()); } }), tools.children[3] || null);
    table.appendChild(thead);
    table.appendChild(tbody);
    if (t.totals) {
      var tf = el('tfoot'), tr = el('tr');
      cols.forEach(function (c, i) {
        tr.appendChild(el('td', { class: cellClass(c, i), text: i === 0 && !(c.key in t.totals) ? 'Tổng' : (c.key in t.totals ? fmt(t.totals[c.key], c.fmt) : '') }));
      });
      tf.appendChild(tr);
      table.appendChild(tf);
    }
    draw();
    wrap.appendChild(table);
    section.appendChild(wrap);
    return section;
  }

  // ---------- gửi tin PIC (Google Chat) ----------
  function renderNotify(content) {
    content.innerHTML = '';
    var status = el('p', { class: 'note' }), preview = el('pre', { class: 'preview', text: 'Bấm "Xem trước" ở một PIC để xem nội dung tin nhắn.' });
    content.appendChild(status);
    content.appendChild(el('details', { class: 'note' }, [
      el('summary', { text: 'Cách lấy webhook cho một PIC' }),
      el('ol', {}, [
        el('li', { text: 'Trong Google Chat, tạo một space riêng cho PIC (chỉ PIC, có thể thêm quản lý). Webhook chỉ gửi vào space, không nhắn riêng được.' }),
        el('li', { text: 'Mở tên space → Apps & integrations → Webhooks → Add webhook, đặt tên "SaleSappV2", rồi sao chép URL.' }),
        el('li', { text: 'Dán URL vào ô Webhook của PIC, bấm Lưu, rồi "Gửi thử" để kiểm tra. Tick "Nhận tin" để đưa PIC vào lịch gửi hằng ngày.' })
      ])
    ]));
    var wrap = el('div', { class: 'wrap' }), logBox = el('div');
    content.appendChild(wrap);
    content.appendChild(el('h2', { text: 'Nội dung xem trước' }));
    content.appendChild(preview);
    content.appendChild(el('h2', { text: 'Lịch sử gửi' }));
    content.appendChild(logBox);

    api('/api/notify/status').then(function (s) {
      status.textContent = (s.enabled ? 'Lịch gửi hằng ngày: ĐANG BẬT (sau ETL 20:30).' : 'Lịch gửi hằng ngày: đang TẮT (NOTIFY_ENABLED=false trong .env). "Gửi thử" vẫn dùng được.') +
        ' Mỗi tin gồm phần Amazon và phần Wayfair cho các nhóm SP của PIC; kỳ báo cáo của từng kênh bỏ ' + s.lag_days +
        ' ngày gần nhất vì đơn về trễ. ACoS mục tiêu mặc định ' + (s.acos_target * 100) + '% (áp cho cả hai kênh; ACoS Wayfair tính theo giá sỉ).';
    });

    function loadPics() {
      api('/api/notify/pics').then(function (rows) {
        var table = el('table'), body = el('tbody');
        table.appendChild(el('thead', {}, [el('tr', {}, ['PIC', 'Nhóm SP', 'Webhook (space Google Chat)', 'ACoS mục tiêu (%)', 'Nhận tin', '', 'Lần gửi cuối']
          .map(function (h, i) { return el('th', { class: i < 3 ? 't' : '', text: h }); }))]));
        rows.forEach(function (r) { body.appendChild(picRow(r)); });
        if (!rows.length) body.appendChild(el('tr', {}, [el('td', { class: 't', colspan: 7, text: 'Chưa có PIC. Chạy ETL để nạp phân công nhóm sản phẩm.' })]));
        table.appendChild(body);
        wrap.innerHTML = '';
        wrap.appendChild(table);
      }).catch(function (e) { wrap.innerHTML = ''; wrap.appendChild(el('div', { class: 'error', text: e.message })); });
    }

    function picRow(r) {
      var who = r.name || r.user_id;
      var url = el('input', { type: 'text', class: 'webhook', 'aria-label': 'Webhook Google Chat của ' + who, placeholder: r.space ? 'Dán URL mới nếu muốn thay webhook' : 'Dán URL https://chat.googleapis.com/v1/spaces/…' });
      // URL đã lưu không gửi về trình duyệt (chứa key/token), chỉ hiện mã space để biết đã lưu
      var saved = r.space
        ? el('div', { class: 'saved' }, ['✓ Đã lưu webhook · space ' + r.space + ' ',
            el('button', { type: 'button', class: 'link', text: 'Xóa', onclick: function () {
              if (!confirm('Xóa webhook của ' + (r.name || r.user_id) + '? PIC này sẽ không nhận tin nữa.')) return;
              api('/api/notify/pics/' + r.user_id, { method: 'PUT', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ webhook_url: '', enabled: false, acos_target: r.acos_target }) }).then(loadPics)
                .catch(function (e) { msg.textContent = e.message; });
            } })])
        : el('div', { class: 'muted small', text: 'Chưa có webhook' });
      var acos = el('input', { type: 'number', min: 0, step: 1, class: 'num', placeholder: 'mặc định', 'aria-label': 'ACoS mục tiêu (%) của ' + who });
      if (r.acos_target !== null && r.acos_target !== undefined) acos.value = +(r.acos_target * 100).toFixed(2);
      var on = el('input', { type: 'checkbox', 'aria-label': 'Nhận tin hằng ngày: ' + who });
      on.checked = !!r.enabled;
      var msg = el('span', { class: 'muted small' });
      function save() {
        var body = { enabled: on.checked, acos_target: acos.value === '' ? null : Number(acos.value) / 100 };
        if (url.value.trim()) body.webhook_url = url.value.trim();
        return api('/api/notify/pics/' + r.user_id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      }
      var actions = el('td', { class: 't' }, [
        el('button', { type: 'button', text: 'Lưu', onclick: function () {
          msg.textContent = 'Đang lưu…';
          save().then(function () { msg.textContent = 'Đã lưu'; setTimeout(loadPics, 800); }).catch(function (e) { msg.textContent = e.message; });
        } }),
        el('button', { type: 'button', text: 'Xem trước', onclick: function () {
          preview.textContent = 'Đang dựng nội dung cho ' + (r.name || r.user_id) + '…';
          api('/api/notify/preview/' + r.user_id).then(function (d) { preview.textContent = d.text; })
            .catch(function (e) { preview.textContent = e.message; });
        } }),
        el('button', { type: 'button', text: 'Gửi thử', onclick: function () {
          if (!confirm('Gửi bản tóm tắt hiện tại vào space Google Chat ' + r.space + ' của ' + (r.name || r.user_id) + '?')) return;
          msg.textContent = 'Đang gửi…';
          api('/api/notify/send/' + r.user_id, { method: 'POST' }).then(function () { msg.textContent = 'Đã gửi'; loadPics(); loadLog(); })
            .catch(function (e) { msg.textContent = e.message; loadLog(); });
        } }),
        msg
      ]);
      if (!r.space) actions.children[2].disabled = true;
      return el('tr', {}, [
        el('td', { class: 't' }, [(r.name || '(chưa có tên)') + ' ', el('span', { class: 'muted small', text: (r.code || '') + (r.active ? '' : ' · nghỉ') })]),
        el('td', { class: 't', title: r.group_names || '', text: r.n_groups + ' nhóm' }),
        el('td', { class: 't' }, [url, saved]),
        el('td', {}, [acos]),
        el('td', {}, [on]),
        actions,
        el('td', { class: 't', text: r.last_sent || '–' })
      ]);
    }

    function loadLog() {
      api('/api/notify/log?limit=30').then(function (rows) {
        logBox.innerHTML = '';
        if (!rows.length) { logBox.appendChild(el('p', { class: 'muted', text: 'Chưa gửi tin nào.' })); return; }
        var t = el('table'), b = el('tbody');
        t.appendChild(el('thead', {}, [el('tr', {}, ['Thời điểm', 'PIC', 'Loại', 'Kết quả', 'Lỗi']
          .map(function (h) { return el('th', { class: 't', text: h }); }))]));
        rows.forEach(function (l) {
          b.appendChild(el('tr', {}, [l.sent_at.replace('T', ' ').slice(0, 16), l.name || l.user_id, l.kind === 'test' ? 'Gửi thử' : 'Hằng ngày',
            l.status, l.error || ''].map(function (v) { return el('td', { class: 't', text: String(v) }); })));
        });
        t.appendChild(b);
        var w = el('div', { class: 'wrap' });
        w.appendChild(t);
        logBox.appendChild(w);
      }).catch(function (e) { logBox.textContent = e.message; });
    }

    loadPics();
    loadLog();
  }

  // ---------- từ điển ----------
  var DICTS = [
    { kind: 'brand', title: 'Brand', desc: 'Brand của mình (OWN) và đối thủ (COMPETITOR). Search term chứa brand được xếp Branded / Competitor.',
      extra: { type: 'select', options: [['OWN', 'Của mình'], ['COMPETITOR', 'Đối thủ']] } },
    { kind: 'attribute', title: 'Thuộc tính', desc: 'Chất liệu, kích thước, màu, đối tượng, công dụng… Search term chứa thuộc tính → Mục tiêu.',
      extra: { type: 'text', placeholder: 'Nhóm (vd material)' } },
    { kind: 'product_term', title: 'Từ loại sản phẩm', desc: 'Tên loại sản phẩm (hammock, office chair…). Search term chỉ gồm các từ này → Chung.',
      extra: { type: 'text', placeholder: 'group_id (tùy chọn)' } },
    { kind: 'stopword', title: 'Stop-word', desc: 'Từ bị bỏ qua khi đếm số từ và tách n-gram (for, with, the…).' },
    { kind: 'override', title: 'Ghi đè phân nhóm', desc: 'Gán thẳng phân nhóm cho một search term cụ thể.',
      extra: { type: 'select', options: [['GENERIC', 'Chung'], ['TARGETED', 'Mục tiêu'], ['BRANDED', 'Brand mình'], ['COMPETITOR', 'Brand đối thủ']] } }
  ];

  function renderDict(content) {
    content.innerHTML = '';
    var status = el('span', { class: 'muted' });
    var btn = el('button', { class: 'primary', text: 'Phân loại lại toàn bộ từ khóa', onclick: function () {
      btn.disabled = true;
      api('/api/dict/reclassify/run', { method: 'POST' }).then(function (r) { status.textContent = r.message; poll(); })
        .catch(function (e) { status.textContent = e.message; btn.disabled = false; });
    } });
    function poll() {
      api('/api/dict/reclassify/status').then(function (s) {
        if (s.running) { status.textContent = 'Đang phân loại lại…'; setTimeout(poll, 3000); return; }
        btn.disabled = false;
        if (s.last) status.textContent = s.last.status === 'OK' ? 'Xong: ' + s.last.terms + ' từ khóa (' + s.last.finished + ')' : 'Lỗi: ' + s.last.error;
      });
    }
    content.appendChild(el('h2', { text: 'Từ điển từ khóa' }));
    content.appendChild(el('p', { class: 'note', text: 'Sửa từ điển xong, bấm "Phân loại lại" để áp dụng cho dữ liệu đã có. Lần chạy ETL hằng ngày chỉ phân loại từ khóa mới.' }));
    content.appendChild(el('div', { class: 'table-tools' }, [btn, status]));
    var grid = el('div', { class: 'dict' });
    content.appendChild(grid);
    DICTS.forEach(function (d) { grid.appendChild(dictCard(d)); });
    poll();
  }

  function dictCard(d) {
    var card = el('div', { class: 'card' }), list = el('ul'), count = el('span', { class: 'muted' });
    var term = el('input', { name: 'term', placeholder: 'Thêm từ…', required: 'required', 'aria-label': 'Thêm từ vào ' + d.title }), extra = null;
    if (d.extra && d.extra.type === 'select') extra = el('select', { 'aria-label': 'Loại' }, d.extra.options.map(function (o) { return el('option', { value: o[0], text: o[1] }); }));
    else if (d.extra) extra = el('input', { placeholder: d.extra.placeholder, 'aria-label': d.extra.placeholder });
    var form = el('form', {}, [term, extra, el('button', { type: 'submit', text: 'Thêm' })]);
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      api('/api/dict/' + d.kind, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ term: term.value, extra: extra ? extra.value : null }) })
        .then(function () { term.value = ''; refresh(); }).catch(function (err) { alert(err.message); });
    });
    function refresh() {
      api('/api/dict/' + d.kind).then(function (items) {
        list.innerHTML = '';
        count.textContent = ' (' + items.length + ')';
        items.forEach(function (it) {
          list.appendChild(el('li', {}, [
            el('span', {}, [it.term, ' ', el('span', { class: 'tag', text: it.extra ? '· ' + it.extra : '' })]),
            el('button', { type: 'button', class: 'x', title: 'Xóa "' + it.term + '"', 'aria-label': 'Xóa "' + it.term + '" khỏi ' + d.title,
              text: '✕', onclick: function () {
                if (!confirm('Xóa "' + it.term + '" khỏi từ điển ' + d.title + '?\nSau khi bấm "Phân loại lại", các search term liên quan sẽ đổi phân nhóm.')) return;
                api('/api/dict/' + d.kind + '/' + it.id, { method: 'DELETE' }).then(refresh).catch(function (err) { alert(err.message); });
              } })
          ]));
        });
      }).catch(function (e) { list.innerHTML = ''; list.appendChild(el('li', { class: 'error', text: e.message })); });
    }
    card.appendChild(el('h3', {}, [d.title, count]));
    card.appendChild(el('p', { text: d.desc }));
    card.appendChild(form);
    card.appendChild(list);
    refresh();
    return card;
  }

  // ---------- audit từ khóa: upload file bulk → duyệt đề xuất → xuất file bulk để upload lại Amazon ----------
  var AUDIT_ACTIONS = { bid: 'Đổi bid', pause: 'Pause', add_keyword: 'Thêm keyword Exact', add_target: 'Thêm target ASIN',
                        negative: 'Negative exact', negative_target: 'Negative ASIN', warn: 'Cảnh báo',
                        remove: 'Gỡ keyword', listing_off: 'Tắt listing', budget: 'Tăng daily cap' };
  var AUDIT_STATUS = { QUEUED: 'Đang chờ', PARSING: 'Đang đọc file…', AUDITING: 'Đang audit…', READY: 'Xong', FAILED: 'Lỗi' };
  // Cột Keyword / Target và Search term của một đề xuất:
  //  - đổi bid / pause: keyword hoặc target đang đặt giá thầu, không có search term
  //  - harvest / negative: search term khách gõ + keyword / target đã khớp nó (source); thêm Exact thì keyword mới = search term
  //  - xung đột: negative đang chặn + các search term từng ra đơn bị chặn (source)
  var TERM_RULES = { harvest: 1, negative: 1 };
  function auditKeyword(p) {
    var mt = p.match_type ? p.match_type.toLowerCase() : '';
    if (p.action === 'add_keyword' || p.action === 'add_target')
      return { text: p.text + ' · ' + (mt || 'exact'), note: p.source ? 'nguồn: ' + p.source : '', title: 'Keyword mới; nguồn: ' + (p.source || '') };
    if (TERM_RULES[p.rule]) return { text: p.source || '', note: mt ? mt.replace(/_/g, ' ') : '', title: p.source || '' };
    return { text: p.text || '', note: mt === 'targeting' ? 'product target' : mt, title: p.text || '' };
  }
  function auditTerm(p) {
    if (TERM_RULES[p.rule]) return p.text;
    if (p.rule === 'conflict') return p.source;
    return '';
  }
  function renderAudit(content, ch) {
    content.innerHTML = '';
    var wf = ch === 'wayfair', chq = wf ? '?channel=wayfair' : '';
    var timer = null, runData = null, selected = {}, page = 0, PAGE = 100, ruleFilter = '', query = '';
    var file = el('input', { type: 'file', accept: '.xlsx', 'aria-label': 'Chọn file bulk .xlsx' });
    var upMsg = el('span', { class: 'muted small' });
    var upBtn = el('button', { type: 'button', class: 'primary', text: 'Upload & audit' });
    var listBox = el('div'), runBox = el('div');
    content.appendChild(el('h2', { text: 'Audit từ khóa' + (wf ? ' Wayfair' : '') }));
    content.appendChild(el('details', { class: 'note' }, [
      el('summary', { text: 'Cách dùng' }),
      el('ol', {}, wf ? [
        el('li', { text: 'WSP → Campaigns → Bulk Campaign Edits → Step 1: tải template của tài khoản cần audit (.xlsx, có sẵn campaign, listing, keyword, negative).' }),
        el('li', { text: 'Upload file ở đây. Hệ thống tự nhận tài khoản theo Campaign ID, lấy số liệu (ACoS theo giá sỉ) từ dữ liệu quảng cáo Wayfair rồi chạy các quy tắc ở tab "Quy tắc audit" của Wayfair. Campaign AI Bidding (TROAS) không bị chỉnh bid.' }),
        el('li', { text: 'Duyệt đề xuất: bỏ tick dòng không muốn đổi. Hạ về sàn, gỡ keyword, tắt listing và các dòng thiếu campaign đích mặc định không tick. Giảm bid listing chỉ để xem (hạ tay trên WSP) trừ khi bật trong quy tắc. Cảnh báo chỉ để xem.' }),
        el('li', { text: 'Bấm "Xuất file bulk": file giữ đúng template Wayfair, mỗi sheet chỉ còn dòng có thay đổi (ghi ở cột New …), keyword / negative mới ở sheet Add …. Import file đó ở Bulk Campaign Edits → Step 2 rồi xem kết quả ở Bulk Edits History.' })
      ] : [
        el('li', { text: 'Ads Console → Sponsored ads → Bulk operations → tạo và tải file Sponsored Products của tài khoản cần audit (.xlsx).' }),
        el('li', { text: 'Upload file ở đây. Hệ thống tự nhận tài khoản theo Campaign ID, lấy số liệu từ dữ liệu quảng cáo đã có rồi chạy các quy tắc ở tab "Quy tắc audit".' }),
        el('li', { text: 'Duyệt đề xuất: bỏ tick dòng không muốn đổi. Pause và các dòng thiếu ad group đích mặc định không tick. Cảnh báo chỉ để xem.' }),
        el('li', { text: 'Bấm "Xuất file bulk", rồi upload file đó vào Ads Console → Bulk operations. Dòng đã xuất được ghi nhớ để lần audit sau không đề xuất lại trong thời gian chờ.' })
      ])
    ]));
    content.appendChild(el('div', { class: 'table-tools' }, [file, upBtn, upMsg]));
    content.appendChild(el('h3', { text: 'Các lần upload' }));
    content.appendChild(listBox);
    content.appendChild(runBox);

    upBtn.addEventListener('click', function () {
      var f = file.files[0];
      if (!f) { upMsg.textContent = 'Chọn file .xlsx trước.'; return; }
      upBtn.disabled = true;
      upMsg.textContent = 'Đang tải lên ' + f.name + ' (' + (f.size / 1048576).toFixed(1) + ' MB)…';
      api('/api/audit/upload', { method: 'POST', headers: { 'Content-Type': 'application/octet-stream', 'X-File-Name': encodeURIComponent(f.name),
        'X-Channel': wf ? 'wayfair' : 'amazon' }, body: f })
        .then(function () { upMsg.textContent = 'Đã nhận file. Đang đọc và audit (khoảng 1–2 phút)…'; file.value = ''; loadList(); })
        .catch(function (e) { upMsg.textContent = e.message; })
        .then(function () { upBtn.disabled = false; });
    });

    function loadList() {
      clearTimeout(timer);
      if (!document.body.contains(listBox)) return;  // đã rời tab
      api('/api/audit/uploads' + chq).then(function (rows) {
        listBox.innerHTML = '';
        if (!rows.length) { listBox.appendChild(el('p', { class: 'muted', text: 'Chưa có file nào.' })); return; }
        var tb = el('tbody');
        rows.forEach(function (u) {
          var busy = ['QUEUED', 'PARSING', 'AUDITING'].indexOf(u.status) >= 0;
          var st = AUDIT_STATUS[u.status] || u.status;
          if (u.status === 'FAILED') st += ': ' + (u.message || u.run_message || '');
          tb.appendChild(el('tr', {}, [
            el('td', { class: 't', text: (u.uploaded_at || '').replace('T', ' ').slice(0, 16) }),
            el('td', { class: 't', text: u.account_label || '–' }),
            el('td', { class: 't', title: u.file_name, text: (u.file_name || '').slice(0, 40) }),
            el('td', { class: 't' + (u.status === 'FAILED' ? ' error' : ''), text: st }),
            el('td', { class: 't', text: u.data_end ? dmy(u.data_start) + ' → ' + dmy(u.data_end) : '–' }),
            el('td', { text: u.n_proposals === null ? '–' : fmt(u.n_proposals, 'int') }),
            el('td', { text: u.n_exported ? fmt(u.n_exported, 'int') : '–' }),
            el('td', { class: 't' }, [
              el('button', { type: 'button', text: 'Xem', disabled: u.run_id && !busy ? null : 'disabled', onclick: function () { openRun(u.run_id); } }),
              el('button', { type: 'button', text: 'Chạy lại', title: 'Audit lại file này với quy tắc hiện tại', disabled: busy ? 'disabled' : null, onclick: function () {
                api('/api/audit/uploads/' + u.id + '/rerun', { method: 'POST' }).then(loadList).catch(function (e) { alert(e.message); });
              } })
            ])
          ]));
        });
        listBox.appendChild(el('div', { class: 'wrap' }, [el('table', {}, [
          el('thead', {}, [el('tr', {}, ['Upload lúc', 'Tài khoản', 'File', 'Trạng thái', 'Số liệu', 'Đề xuất', 'Đã xuất', ''].map(function (h, i) {
            return el('th', { class: i < 5 || i === 7 ? 't' : '', text: h }); }))]), tb])]));
        if (rows.some(function (u) { return ['QUEUED', 'PARSING', 'AUDITING'].indexOf(u.status) >= 0; })) timer = setTimeout(loadList, 4000);
        else if (!runData && rows[0].run_id && rows[0].status === 'READY') openRun(rows[0].run_id);
      }).catch(function (e) { listBox.textContent = e.message; });
    }

    function openRun(runId) {
      runBox.innerHTML = '';
      runBox.appendChild(el('p', { class: 'muted', text: 'Đang tải đề xuất…' }));
      api('/api/audit/runs/' + runId + '/proposals').then(function (d) {
        runData = d;
        selected = {};
        d.proposals.forEach(function (p) { if (p.default_on && p.exportable && p.status !== 'exported') selected[p.id] = true; });
        page = 0; ruleFilter = ''; query = '';
        renderRun();
      }).catch(function (e) { runBox.textContent = e.message; });
    }

    function visible() {
      var q = query.toLowerCase();
      return runData.proposals.filter(function (p) {
        return (!ruleFilter || p.rule === ruleFilter) &&
          (!q || [p.text, p.source, p.campaign_name, p.ad_group_name].some(function (v) { return v && v.toLowerCase().indexOf(q) >= 0; }));
      });
    }
    function nSelected() { return Object.keys(selected).length; }

    function renderRun() {
      var run = runData.run, cur = run.currency_code || '';
      runBox.innerHTML = '';
      runBox.appendChild(el('h3', { text: 'Đề xuất · ' + (run.account_label || run.profile_id) + ' · số liệu ' + dmy(run.data_start) + ' → ' + dmy(run.data_end) +
        ' · tiền ' + cur }));
      // thẻ theo quy tắc: số đề xuất, số đang chọn, chọn / bỏ cả nhóm
      var chips = el('div', { class: 'cost-chan audit-chips' });
      [{ id: '', label: 'Tất cả' }].concat(runData.rules).forEach(function (r) {
        var rows = runData.proposals.filter(function (p) { return !r.id || p.rule === r.id; });
        if (r.id && !rows.length) return;
        var sel = rows.filter(function (p) { return selected[p.id]; }).length;
        var card = el('div', { class: 'card' + (ruleFilter === r.id ? ' active' : '') }, [
          el('button', { type: 'button', class: 'link', text: r.label + ' (' + fmt(rows.length, 'int') + ')', 'aria-pressed': String(ruleFilter === r.id),
            onclick: function () { ruleFilter = r.id; page = 0; renderRun(); } }),
          el('span', { class: 'muted small', text: 'chọn ' + fmt(sel, 'int') })
        ]);
        if (r.id && rows.some(function (p) { return p.exportable && p.status !== 'exported'; })) {
          card.appendChild(el('button', { type: 'button', class: 'link small', text: sel ? 'Bỏ hết' : 'Chọn hết', onclick: function () {
            rows.forEach(function (p) { if (sel) delete selected[p.id]; else if (p.exportable && p.status !== 'exported') selected[p.id] = true; });
            renderRun();
          } }));
        }
        chips.appendChild(card);
      });
      runBox.appendChild(chips);

      var search = el('input', { type: 'search', placeholder: 'Tìm campaign / ad group / keyword / search term…', 'aria-label': 'Tìm trong đề xuất', value: query });
      search.addEventListener('change', function () { query = search.value.trim(); page = 0; renderRun(); });
      var expMsg = el('span', { class: 'muted small' });
      var expBtn = el('button', { type: 'button', class: 'primary', text: 'Xuất file bulk (' + fmt(nSelected(), 'int') + ' dòng)', onclick: function () {
        var ids = Object.keys(selected).map(Number);
        if (!ids.length) { expMsg.textContent = 'Chưa chọn dòng nào.'; return; }
        if (!confirm('Xuất ' + ids.length + ' thay đổi ra file bulk? Các dòng này sẽ được đánh dấu "đã xuất".')) return;
        expBtn.disabled = true;
        expMsg.textContent = 'Đang dựng file…';
        fetch('/api/audit/runs/' + run.id + '/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids: ids }) })
          .then(function (r) {
            if (!r.ok) return r.text().then(function (t) {  // lỗi 500 của server trả text thuần, không phải JSON
              var detail = null;
              try { detail = JSON.parse(t).detail; } catch (e) { /* giữ null */ }
              throw new Error(detail || ('Lỗi server (HTTP ' + r.status + '). Thử khởi động lại server rồi xuất lại.'));
            });
            var name = ((r.headers.get('content-disposition') || '').match(/filename="?([^";]+)/) || [])[1] || 'audit_bulk.xlsx';
            return r.blob().then(function (blob) {
              var a = el('a', { href: URL.createObjectURL(blob), download: name });
              document.body.appendChild(a); a.click(); a.remove();
              expMsg.textContent = 'Đã xuất ' + name + '. ' + (wf ? 'Import file này ở WSP → Bulk Campaign Edits → Step 2.' : 'Upload file này vào Ads Console → Bulk operations.');
              loadList();
              openRun(run.id);
            });
          })
          .catch(function (e) { expMsg.textContent = e.message; expBtn.disabled = false; });
      } });
      runBox.appendChild(el('div', { class: 'table-tools' }, [search, expBtn, expMsg]));

      var rows = visible(), shown = rows.slice(page * PAGE, (page + 1) * PAGE);
      var tb = el('tbody');
      shown.forEach(function (p) {
        var cb = el('input', { type: 'checkbox', 'aria-label': 'Chọn: ' + (AUDIT_ACTIONS[p.action] || p.action) + ' ' + (p.text || '') });
        cb.checked = !!selected[p.id];
        if (!p.exportable || p.status === 'exported') cb.disabled = true;
        cb.addEventListener('change', function () {
          if (cb.checked) selected[p.id] = true; else delete selected[p.id];
          expBtn.textContent = 'Xuất file bulk (' + fmt(nSelected(), 'int') + ' dòng)';
        });
        var acos = p.sales ? p.spend / p.sales : null, kw = auditKeyword(p), term = auditTerm(p);
        var bid = p.action === 'bid' || p.action === 'budget' ? fmt(p.current_bid, 'num2') + ' → ' + fmt(p.new_bid, 'num2')
          : (p.new_bid ? fmt(p.new_bid, 'num2') : (p.current_bid ? fmt(p.current_bid, 'num2') : ''));
        if (wf && bid && p.currency_code && run.currency_code !== p.currency_code) bid += ' ' + p.currency_code;
        tb.appendChild(el('tr', { class: p.status === 'exported' ? 'muted' : '' }, [
          el('td', {}, [cb]),
          el('td', { class: 't', text: AUDIT_ACTIONS[p.action] || p.action }),
          el('td', { class: 't clip', title: p.campaign_name || '', text: p.campaign_name || '–' }),
          el('td', { class: 't clip', title: p.ad_group_name || '', text: p.ad_group_name || '–' }),
          el('td', { class: 't clip', title: kw.title }, [kw.text || '–', kw.note ? el('div', { class: 'muted small', text: kw.note }) : null]),
          el('td', { class: 't clip', title: term || '', text: term || '–' }),
          el('td', { text: fmt(p.clicks, 'int') }),
          el('td', { text: fmt(p.spend, 'num2') }),
          el('td', { text: fmt(p.orders, 'int') }),
          el('td', { text: acos === null ? '–' : fmt(acos, 'pct') }),
          el('td', { text: bid }),
          el('td', { class: 't small', text: p.reason + (p.status === 'exported' ? ' · đã xuất ' + (p.exported_at || '').replace('T', ' ').slice(0, 16) : '') })
        ]));
      });
      if (!shown.length) tb.appendChild(el('tr', {}, [el('td', { class: 't muted', colspan: 12, text: 'Không có đề xuất.' })]));
      runBox.appendChild(el('div', { class: 'wrap' }, [el('table', {}, [
        el('thead', {}, [el('tr', {}, ['', 'Hành động', 'Campaign', wf ? 'Sản phẩm (listing)' : 'Ad group', wf ? 'Keyword / Listing' : 'Keyword / Target',
          'Search term', 'Click', 'Spend (' + cur + ')', 'Đơn', wf ? 'ACoS (giá sỉ)' : 'ACoS', (wf ? 'Bid / cap (' : 'Bid (') + cur + ')', 'Lý do'].map(function (h, i) { return el('th', { class: i < 6 || i === 11 ? 't' : '', text: h }); }))]), tb])]));
      var pages = Math.ceil(rows.length / PAGE);
      if (pages > 1) {
        runBox.appendChild(el('div', { class: 'table-tools' }, [
          el('button', { type: 'button', text: '‹ Trước', disabled: page ? null : 'disabled', onclick: function () { page--; renderRun(); } }),
          el('span', { class: 'muted', text: 'Trang ' + (page + 1) + ' / ' + pages + ' · ' + fmt(rows.length, 'int') + ' dòng' }),
          el('button', { type: 'button', text: 'Sau ›', disabled: page < pages - 1 ? null : 'disabled', onclick: function () { page++; renderRun(); } })
        ]));
      }
    }

    loadList();
  }

  // ---------- quy tắc audit từ khóa (mặc định chung + ghi đè theo tài khoản) ----------
  // Tỉ lệ lưu dạng 0.2, nhập / hiện dạng 20. Ô trống ở một tài khoản = theo mặc định chung.
  var AUDIT_SOURCE = { default: 'mặc định', global: 'chung', account: 'riêng TK' };
  function renderAuditRules(content, ch) {
    content.innerHTML = '';
    // Wayfair: bộ quy tắc riêng, phạm vi "wf:*" (chung) / "wf:<account_id>"; Amazon: "*" / profile_id
    var wf = ch === 'wayfair', G = wf ? 'wf:*' : '*', storeKey = wf ? 'audit.scope.wf' : 'audit.scope';
    var scope = store(storeKey) || G, accounts = [], data = null, dirty = {};
    var picker = el('select', { 'aria-label': 'Phạm vi cấu hình' });
    var saveBtn = el('button', { type: 'button', class: 'primary', text: 'Lưu quy tắc', disabled: 'disabled' });
    var status = el('p', { class: 'note' }), body = el('div', { class: 'dict audit' }), extra = el('div');
    content.appendChild(el('h2', { text: 'Quy tắc audit từ khóa' + (wf ? ' Wayfair' : '') }));
    content.appendChild(el('p', { class: 'note', text: 'Chọn "Mặc định chung" để đặt quy tắc cho mọi tài khoản, hoặc chọn một tài khoản để ghi đè riêng. Ở một tài khoản, ô để trống nghĩa là dùng giá trị chung (hiện mờ trong ô). Bộ máy audit đọc trực tiếp cấu hình này mỗi lần chạy, nên sửa xong là có hiệu lực từ lần audit sau.' +
      (wf ? ' Quy tắc Wayfair tách riêng Amazon; ACoS tính trên doanh số giá sỉ.' : '') }));
    content.appendChild(el('div', { class: 'table-tools' }, [el('label', { class: 'muted' }, ['Phạm vi ', picker]), saveBtn]));
    content.appendChild(status);
    content.appendChild(body);
    content.appendChild(extra);

    function shown(p, v) { return v === null || v === undefined ? '' : String(+(p.unit === 'pct' ? v * 100 : v).toFixed(4)); }
    function parsed(p, raw) {
      raw = String(raw).trim().replace(/[%$\s]/g, '').replace(',', '.');
      if (raw === '') return null;
      var n = Number(raw);
      return isNaN(n) ? NaN : (p.unit === 'pct' ? n / 100 : n);
    }
    function unitText(p) {
      var cur = data.account ? data.account.currency_code : 'tiền TK';
      return { pct: '%', days: 'ngày', money: cur, num: '' }[p.unit] || '';
    }
    function markDirty(key, value) {
      dirty[key] = value;
      saveBtn.disabled = false;
      status.textContent = Object.keys(dirty).length + ' thay đổi chưa lưu.';
    }

    function paramRow(p) {
      var own = scope === G ? p.global : p.account;  // giá trị đặt ở chính phạm vi đang xem
      var inherited = scope === G ? p.default : (p.global !== null ? p.global : p.default);
      var src = el('span', { class: 'tag', text: AUDIT_SOURCE[p.source] });
      var reset = el('button', { type: 'button', class: 'x', text: '↺', title: 'Bỏ giá trị riêng, dùng giá trị ' + (scope === G ? 'mặc định' : 'chung'),
        'aria-label': 'Bỏ giá trị riêng của ' + p.label, onclick: function () { markDirty(p.key, null); input.value = ''; if (p.unit === 'bool') input.checked = !!inherited; reset.style.visibility = 'hidden'; } });
      reset.style.visibility = own !== null ? '' : 'hidden';
      var input;
      if (p.unit === 'bool') {
        input = el('input', { type: 'checkbox', 'aria-label': p.label + ' — ' + p.rule });
        input.checked = !!p.value;
        input.addEventListener('change', function () { markDirty(p.key, input.checked ? 1 : 0); reset.style.visibility = ''; });
      } else {
        input = el('input', { type: 'text', inputmode: 'decimal', class: 'num', 'aria-label': p.label,
          placeholder: shown(p, inherited) + (scope === G ? '' : ' (chung)') });
        input.value = shown(p, own);
        input.addEventListener('input', function () {
          var v = parsed(p, input.value);
          input.classList.toggle('bad', v !== null && isNaN(v));
          markDirty(p.key, v);
          reset.style.visibility = v === null ? 'hidden' : '';
        });
      }
      return el('li', { title: p.help || '' }, [
        el('span', {}, [p.label, p.help ? el('span', { class: 'tag', text: ' ⓘ' }) : null]),
        el('span', { class: 'audit-val' }, [input, el('span', { class: 'muted small', text: ' ' + unitText(p) + ' ' }), src, reset])
      ]);
    }

    function render() {
      body.innerHTML = '';
      dirty = {};
      saveBtn.disabled = true;
      var acc = data.account;
      status.textContent = (acc ? 'Đang xem: ' + acc.account_label + ' (' + acc.currency_code + ').' : 'Đang xem: mặc định chung cho mọi tài khoản.') +
        (data.updated_at ? ' Sửa lần cuối ' + data.updated_at.replace('T', ' ').slice(0, 16) + '.' : '');
      data.rules.forEach(function (r) {
        var list = el('ul');
        data.params.filter(function (p) { return p.rule === r.id; }).forEach(function (p) { list.appendChild(paramRow(p)); });
        body.appendChild(el('div', { class: 'card' }, [el('h3', { text: r.label }), el('p', { text: r.desc }), list]));
      });
      renderExtra();
    }

    function renderExtra() {
      extra.innerHTML = '';
      if (scope === G) return;
      // chép cấu hình sang tài khoản khác
      var others = accounts.filter(function (a) { return a.profile_id !== scope; });
      var boxes = others.map(function (a) {
        var cb = el('input', { type: 'checkbox', value: a.profile_id });
        return { cb: cb, label: el('label', { class: 'muted' }, [cb, ' ' + a.account_label + ' (' + a.currency_code + ')' + (a.n_overrides ? ' · đang có ' + a.n_overrides + ' ghi đè' : '')]) };
      });
      var copyMsg = el('span', { class: 'muted small' });
      extra.appendChild(el('h2', { text: 'Áp cho tài khoản khác' }));
      extra.appendChild(el('p', { class: 'note', text: 'Chép toàn bộ giá trị riêng của tài khoản này sang các tài khoản được chọn (thay các giá trị riêng cũ của chúng). Lưu ý bid sàn tính theo tiền của từng tài khoản.' }));
      extra.appendChild(el('div', { class: 'cost-chan' }, boxes.map(function (b) { return b.label; })));
      extra.appendChild(el('div', { class: 'table-tools' }, [
        el('button', { type: 'button', text: 'Chép sang tài khoản đã chọn', onclick: function () {
          var targets = boxes.filter(function (b) { return b.cb.checked; }).map(function (b) { return b.cb.value; });
          if (!targets.length) { copyMsg.textContent = 'Chưa chọn tài khoản nào.'; return; }
          if (!confirm('Thay các giá trị riêng của ' + targets.length + ' tài khoản bằng cấu hình của ' + data.account.account_label + '?')) return;
          api('/api/audit/rules/copy', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source: scope, targets: targets }) })
            .then(function (r) { copyMsg.textContent = 'Đã chép ' + r.params + ' giá trị sang ' + r.targets + ' tài khoản.'; loadAccounts(); })
            .catch(function (e) { copyMsg.textContent = e.message; });
        } }),
        el('button', { type: 'button', text: 'Đưa tài khoản này về mặc định chung', onclick: function () {
          if (!confirm('Xoá mọi giá trị riêng của ' + data.account.account_label + '?')) return;
          api('/api/audit/rules/copy', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source: G, targets: [scope] }) }).then(function () { loadAccounts(); load(); })
            .catch(function (e) { copyMsg.textContent = e.message; });
        } }),
        copyMsg
      ]));
      renderAcos();
    }

    function renderAcos() {
      var box = el('div'), acosMsg = el('span', { class: 'muted small' }), changed = {};
      var acosBtn = el('button', { type: 'button', class: 'primary', text: 'Lưu ACoS mục tiêu', disabled: 'disabled' });
      extra.appendChild(el('h2', { text: 'ACoS mục tiêu riêng' }));
      extra.appendChild(el('p', { class: 'note', text: wf
        ? 'Thứ tự ưu tiên: nhóm SP → ACoS mục tiêu mặc định ở trên. Mục tiêu nhóm SP của Wayfair (giá sỉ) dùng chung cho mọi tài khoản Wayfair, tách riêng mục tiêu Amazon. Để trống = không đặt riêng.'
        : 'Thứ tự ưu tiên: portfolio → nhóm SP → ACoS mục tiêu mặc định ở trên. Mục tiêu của nhóm SP dùng chung cho mọi tài khoản; mục tiêu portfolio chỉ thuộc tài khoản này. Để trống = không đặt riêng.' }));
      extra.appendChild(el('div', { class: 'table-tools' }, [acosBtn, acosMsg]));
      extra.appendChild(box);
      function table(title, rows, type, cols) {
        var tb = el('tbody');
        rows.forEach(function (r) {
          var inp = el('input', { type: 'text', inputmode: 'decimal', class: 'num', 'aria-label': 'ACoS mục tiêu % của ' + r.name });
          if (r.acos_target !== null) inp.value = +(r.acos_target * 100).toFixed(2);
          inp.addEventListener('input', function () {
            var v = inp.value.trim() === '' ? null : Number(inp.value.replace(',', '.')) / 100;
            changed[type + ':' + r.scope_id] = { scope_type: type, scope_id: String(r.scope_id), acos_target: v };
            acosBtn.disabled = false;
          });
          tb.appendChild(el('tr', {}, [el('td', { class: 't', text: r.name || r.scope_id })].concat(cols(r)).concat([el('td', {}, [inp])])));
        });
        if (!rows.length) tb.appendChild(el('tr', {}, [el('td', { class: 't muted', colspan: 3, text: 'Không có.' })]));
        return el('div', { class: 'card' }, [el('h3', { text: title }), el('div', { class: 'wrap' }, [el('table', {}, [tb])])]);
      }
      function loadAcos() {
        api('/api/audit/acos?profile_id=' + encodeURIComponent(scope)).then(function (d) {
          box.innerHTML = '';
          changed = {};
          acosBtn.disabled = true;
          var grid = el('div', { class: 'dict' });
          if (d.portfolios) grid.appendChild(table('Portfolio', d.portfolios, 'PORTFOLIO', function (r) { return [el('td', { class: 'muted small', text: r.state || '' })]; }));
          grid.appendChild(table('Nhóm SP (có chạy QC 60 ngày ở tài khoản này)', d.groups, d.group_scope || 'GROUP', function (r) {
            return [el('td', { class: 'muted small', text: r.spend ? 'spend ' + fmt(r.spend, 'int') + ' ' + data.account.currency_code : '' })]; }));
          box.appendChild(grid);
        }).catch(function (e) { box.textContent = e.message; });
      }
      acosBtn.addEventListener('click', function () {
        var items = Object.keys(changed).map(function (k) { return changed[k]; });
        if (items.some(function (i) { return i.acos_target !== null && (isNaN(i.acos_target) || i.acos_target <= 0); })) { acosMsg.textContent = 'Có ô không phải số dương.'; return; }
        api('/api/audit/acos', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(items) })
          .then(function () { acosMsg.textContent = 'Đã lưu ' + items.length + ' mục tiêu.'; loadAcos(); })
          .catch(function (e) { acosMsg.textContent = e.message; });
      });
      loadAcos();
    }

    function load() {
      body.innerHTML = '';
      body.appendChild(el('p', { class: 'muted', text: 'Đang tải…' }));
      api('/api/audit/rules' + (scope === G ? (wf ? '?channel=wayfair' : '') : '?profile_id=' + encodeURIComponent(scope)))
        .then(function (d) { data = d; render(); })
        .catch(function (e) { body.innerHTML = ''; body.appendChild(el('div', { class: 'error', text: e.message })); });
    }
    function loadAccounts() {
      return api('/api/audit/accounts' + (wf ? '?channel=wayfair' : '')).then(function (rows) {
        accounts = rows;
        picker.innerHTML = '';
        picker.appendChild(el('option', { value: G, text: 'Mặc định chung (mọi tài khoản)' }));
        rows.forEach(function (a) {
          picker.appendChild(el('option', { value: a.profile_id, text: a.account_label + ' · ' + a.currency_code + (a.n_overrides ? ' · ' + a.n_overrides + ' ghi đè' : '') }));
        });
        if (scope !== G && !rows.some(function (a) { return a.profile_id === scope; })) scope = G;
        picker.value = scope;
      });
    }

    picker.addEventListener('change', function () {
      if (Object.keys(dirty).length && !confirm('Bỏ các thay đổi chưa lưu?')) { picker.value = scope; return; }
      scope = picker.value;
      store(storeKey, scope);
      load();
    });
    saveBtn.addEventListener('click', function () {
      var bad = Object.keys(dirty).filter(function (k) { return dirty[k] !== null && isNaN(dirty[k]); });
      if (bad.length) { status.textContent = 'Có ô không phải số, sửa lại trước khi lưu.'; return; }
      saveBtn.disabled = true;
      api('/api/audit/rules', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scope: scope, values: dirty }) })
        .then(function (r) { loadAccounts(); load(); announce('Đã lưu ' + (r.saved + r.reset) + ' thay đổi'); })
        .catch(function (e) { status.textContent = e.message; saveBtn.disabled = false; });
    });
    loadAccounts().then(load).catch(function (e) { body.textContent = e.message; });
  }

  // ---------- giá vốn & phí theo SKU (dùng chung Amazon + Wayfair) ----------
  // % lưu dạng tỉ lệ (0.15) nhưng nhập / hiện dạng phần trăm (15)
  var COST_COLS = [
    { key: 'landed_cost', label: 'Giá vốn / đv ($)', title: 'Giá vốn về kho mỗi đơn vị: FOB + cước + thuế + vận chuyển nội địa' },
    { key: 'amz_fee_unit', label: 'Phí Amazon / đv ($)', title: 'Phí FBA hoặc phí giao hàng công ty chịu cho mỗi đơn vị bán trên Amazon' },
    { key: 'wf_fee_unit', label: 'Phí Wayfair / đv ($)', title: 'Phí CastleGate hoặc phí giao hàng công ty chịu cho mỗi đơn vị bán trên Wayfair' },
    { key: 'amz_referral_pct', label: 'Phí sàn Amazon %', pct: true, title: 'Để trống = dùng mặc định của kênh' },
    { key: 'return_pct', label: 'Hoàn trả %', pct: true, title: 'Dự phòng hoàn trả, tính trên giá bán. Để trống = mặc định của kênh' }
  ];
  function numOrNull(v, pct) {
    v = String(v === undefined || v === null ? '' : v).trim().replace(/[$%\s]/g, '');
    if (v === '') return null;
    var n = Number(v);
    return isNaN(n) ? NaN : (pct ? n / 100 : n);
  }
  function shownValue(v, pct) { return v === null || v === undefined ? '' : String(+(pct ? v * 100 : v).toFixed(4)); }

  function renderCosts(content) {
    content.innerHTML = '';
    var dirty = {}, data = null, onlyMissing = false;
    var status = el('p', { class: 'note' }), tbody = el('tbody'), search = el('input', { type: 'search', placeholder: 'Tìm SKU / tên…', 'aria-label': 'Tìm SKU' });
    var saveBtn = el('button', { type: 'button', class: 'primary', text: 'Lưu thay đổi', disabled: 'disabled' });
    content.appendChild(el('h2', { text: 'Giá vốn & phí theo SKU' }));
    content.appendChild(el('p', { class: 'note', text: 'Dùng để tính ACoS hòa vốn và Lãi sau QC ở tab Tổng quan và Sản phẩm. Lãi mỗi đơn vị trước QC = giá bán bình quân × (1 − phí sàn − hoàn trả) − giá vốn − phí giao hàng; ACoS hòa vốn = lãi trước QC ÷ giá bán. Amazon dùng giá sau khuyến mãi, Wayfair dùng giá sỉ (Wayfair đã trừ hoa hồng nên phí sàn mặc định 0%). Giá vốn nhập tay được ưu tiên; SKU để trống giá vốn thì dùng giá vốn chuẩn của BOD (Google Sheet, ETL nạp mỗi lần chạy): theo nước bán, đơn FBA / CastleGate dùng cột FBA / CG, đơn giao từ kho dùng cột WH, quy USD theo tỷ giá mới nhất.' }));
    var chanBox = el('div', { class: 'cost-chan' });
    content.appendChild(chanBox);
    content.appendChild(status);

    var paste = el('textarea', { rows: 6, class: 'csv-paste', 'aria-label': 'Dán CSV giá vốn',
      placeholder: 'product_sku,landed_cost,amz_fee_unit,wf_fee_unit,amz_referral_pct,return_pct\nQT9B,120,45,,,3' });
    var pasteBox = el('div', { class: 'cond-panel' }, [
      el('p', { class: 'note', text: 'Dán từ Excel hoặc CSV, mỗi dòng một SKU, cột theo thứ tự: SKU, giá vốn, phí Amazon, phí Wayfair, phí sàn Amazon %, hoàn trả %. Mỗi dòng ghi đè toàn bộ thông tin của SKU đó: ô trống = dùng mặc định của kênh, giá vốn trống = SKU chưa có giá vốn. Phần trăm ghi số 15 cho 15%. Dòng tiêu đề được bỏ qua.' }),
      paste,
      el('div', { class: 'cond-actions' }, [el('button', { type: 'button', class: 'primary', text: 'Nhập', onclick: importCsv })])
    ]);
    content.appendChild(el('div', { class: 'table-tools' }, [search,
      el('label', { class: 'muted small' }, [el('input', { type: 'checkbox', onchange: function (e) { onlyMissing = e.target.checked; draw(); } }), ' Chỉ SKU chưa có giá vốn']),
      saveBtn,
      el('button', { type: 'button', text: 'Dán CSV…', onclick: function () { pasteBox.classList.toggle('open'); } }),
      el('button', { type: 'button', text: 'Tải CSV', onclick: exportCsv })]));
    content.appendChild(pasteBox);
    var head = el('tr', {}, ['SKU', 'Sản phẩm', 'Spend 30 ngày Amazon', 'Spend 30 ngày Wayfair', 'Giá vốn chuẩn (BOD)'].map(function (h, i) {
      return el('th', { class: i < 2 ? 't' + (i === 0 ? ' pin' : '') : '', text: h });
    }).concat(COST_COLS.map(function (c) { return el('th', { text: c.label, title: c.title }); })));
    content.appendChild(el('div', { class: 'wrap' }, [el('table', { class: 'cost-table' }, [el('thead', {}, [head]), tbody])]));
    search.addEventListener('input', draw);
    saveBtn.addEventListener('click', function () {
      var rows = Object.keys(dirty).map(function (pid) { return dirty[pid]; });
      if (rows.some(function (r) { return COST_COLS.some(function (c) { return typeof r[c.key] === 'number' && isNaN(r[c.key]); }); })) {
        alert('Có ô không phải số. Sửa các ô viền đỏ rồi lưu lại.'); return;
      }
      saveBtn.disabled = true;
      api('/api/costs', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rows: rows }) })
        .then(function (res) { announce('Đã lưu ' + res.saved + ' SKU'); refresh('Đã lưu ' + res.saved + ' SKU' + (res.deleted ? ', xóa ' + res.deleted : '') + '.'); })
        .catch(function (e) { saveBtn.disabled = false; alert(e.message); });
    });

    function markDirty(r) {
      dirty[r.product_id] = { product_id: r.product_id };
      COST_COLS.forEach(function (c) { dirty[r.product_id][c.key] = r[c.key]; });
      saveBtn.disabled = false;
      saveBtn.textContent = 'Lưu thay đổi (' + Object.keys(dirty).length + ')';
    }
    function draw() {
      var q = search.value.trim().toLowerCase();
      tbody.innerHTML = '';
      (data ? data.rows : []).filter(function (r) {
        if (onlyMissing && ((r.landed_cost !== null && r.landed_cost !== undefined) || r.std)) return false;
        return !q || (String(r.product_sku || '') + ' ' + String(r.title || '')).toLowerCase().indexOf(q) >= 0;
      }).forEach(function (r) {
        var tr = el('tr', {}, [el('td', { class: 't pin', text: r.product_sku || r.product_id }),
          el('td', { class: 't', text: r.title || '', title: r.title || '' }),
          el('td', { text: r.amz_spend ? fmt(r.amz_spend, 'money') : '–' }), el('td', { text: r.wf_spend ? fmt(r.wf_spend, 'money') : '–' }),
          stdCell(r.std)]);
        COST_COLS.forEach(function (c) {
          var inp = el('input', { type: 'text', inputmode: 'decimal', class: 'num', 'aria-label': c.label + ' của ' + (r.product_sku || r.product_id),
                                  placeholder: c.pct || c.key !== 'landed_cost' ? 'mặc định' : '' });
          inp.value = shownValue(r[c.key], c.pct);
          inp.addEventListener('change', function () {
            var v = numOrNull(inp.value, c.pct);
            inp.classList.toggle('bad', typeof v === 'number' && (isNaN(v) || v < 0));
            r[c.key] = v;
            markDirty(r);
          });
          tr.appendChild(el('td', {}, [inp]));
        });
        tbody.appendChild(tr);
      });
    }
    function drawChannels() {
      chanBox.innerHTML = '';
      [['amazon', 'Amazon'], ['wayfair', 'Wayfair'], ['shopify', 'Shopify'], ['other', 'kênh khác']].forEach(function (ch) {
        var cur = (data.channels || {})[ch[0]] || {};
        var ref = el('input', { type: 'number', min: 0, max: 99, step: 0.5, class: 'num', 'aria-label': 'Phí sàn mặc định ' + ch[1] + ' (%)' });
        var ret = el('input', { type: 'number', min: 0, max: 99, step: 0.5, class: 'num', 'aria-label': 'Hoàn trả mặc định ' + ch[1] + ' (%)' });
        ref.value = shownValue(cur.referral_pct || 0, true);
        ret.value = shownValue(cur.return_pct || 0, true);
        chanBox.appendChild(el('div', { class: 'card' }, [el('strong', { text: 'Mặc định ' + ch[1] }),
          el('label', {}, ['Phí sàn ', ref, ' %']), el('label', {}, ['Hoàn trả ', ret, ' %']),
          el('button', { type: 'button', text: 'Lưu', onclick: function () {
            api('/api/costs/channels/' + ch[0], { method: 'PUT', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ referral_pct: Number(ref.value || 0) / 100, return_pct: Number(ret.value || 0) / 100 }) })
              .then(function () { announce('Đã lưu mặc định ' + ch[1]); refresh('Đã lưu mặc định ' + ch[1] + '.'); }).catch(function (e) { alert(e.message); });
          } })]));
      });
    }
    function refresh(msg) {
      dirty = {};
      saveBtn.disabled = true;
      saveBtn.textContent = 'Lưu thay đổi';
      api('/api/costs').then(function (d) {
        data = d;
        var cv = d.coverage || {};
        status.textContent = (msg ? msg + ' ' : '') + d.rows.length + ' SKU có chạy QC từ ' + dmy(d.window.start) + ' đến ' + dmy(d.window.end) +
          ' hoặc đã có giá vốn. ' + stdText(d.std_cogs) + ' Có giá vốn (nhập tay hoặc chuẩn) cho ' + (cv.amazon === null || cv.amazon === undefined ? '–' : fmt(cv.amazon, 'pct')) + ' Spend Amazon SP và ' +
          (cv.wayfair === null || cv.wayfair === undefined ? '–' : fmt(cv.wayfair, 'pct')) + ' Spend Wayfair.';
        drawChannels();
        draw();
      }).catch(function (e) { status.textContent = e.message; });
    }
    function stdCell(std) {
      if (!std) return el('td', { class: 'muted', text: '–' });
      var cur = { US: 'USD', CA: 'CAD', AU: 'AUD' }, lines = [];
      ['US', 'CA', 'AU'].forEach(function (m) {
        if (!std[m]) return;
        lines.push(m + ' ' + ['WH', 'FBA', 'CG'].filter(function (b) { return std[m][b]; })
          .map(function (b) { return b + ' ' + (+std[m][b]).toFixed(2); }).join(' · ') + ' ' + cur[m]);
      });
      return el('td', { class: 't small', text: lines[0] || '–', title: lines.join('\n') });
    }
    function stdText(info) {
      if (!info || !info.loaded_at) return 'Chưa nạp giá vốn chuẩn từ Google Sheet (chạy ETL).';
      var miss = info.unmatched || [];
      return 'Giá vốn chuẩn: ' + info.skus + ' SKU, nạp lúc ' + dmy(String(info.loaded_at).slice(0, 10)) + ' ' + String(info.loaded_at).slice(11, 16) +
        (miss.length ? ' (' + miss.length + ' SKU không có trong danh mục sản phẩm: ' + miss.slice(0, 8).join(', ') + (miss.length > 8 ? '…' : '') + ').' : '.');
    }
    function importCsv() {
      var lines = paste.value.split(/\r?\n/).filter(function (l) { return l.trim(); });
      if (!lines.length) return;
      var delim = lines[0].indexOf('\t') >= 0 ? '\t' : (lines[0].indexOf(';') >= 0 ? ';' : ',');
      var rows = [], bad = [];
      lines.forEach(function (line, i) {
        var cells = line.split(delim).map(function (x) { x = x.trim().replace(/^"|"$/g, ''); return delim === ';' ? x.replace(',', '.') : x; });
        if (i === 0 && isNaN(Number(cells[1])) && cells[1] !== '') return;  // dòng tiêu đề
        var r = { product_sku: cells[0] };
        COST_COLS.forEach(function (c, j) { r[c.key] = numOrNull(cells[j + 1], c.pct); });
        if (!r.product_sku || COST_COLS.some(function (c) { return typeof r[c.key] === 'number' && (isNaN(r[c.key]) || r[c.key] < 0); })) bad.push(i + 1);
        else rows.push(r);
      });
      if (bad.length) { alert('Dòng ' + bad.join(', ') + ' có SKU trống hoặc số không hợp lệ. Chưa nhập gì.'); return; }
      api('/api/costs', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rows: rows }) })
        .then(function (res) {
          paste.value = '';
          pasteBox.classList.remove('open');
          refresh('Đã nhập ' + res.saved + ' SKU.' + (res.unknown.length ? ' Không tìm thấy SKU: ' + res.unknown.join(', ') + '.' : ''));
        }).catch(function (e) { alert(e.message); });
    }
    function exportCsv() {
      var out = ['product_sku,landed_cost,amz_fee_unit,wf_fee_unit,amz_referral_pct,return_pct,amz_spend_30d,wf_spend_30d,title'];
      (data ? data.rows : []).forEach(function (r) {
        out.push([r.product_sku].concat(COST_COLS.map(function (c) { return shownValue(r[c.key], c.pct); }))
          .concat([(+r.amz_spend).toFixed(2), (+r.wf_spend).toFixed(2), '"' + String(r.title || '').replace(/"/g, '""') + '"']).join(','));
      });
      var a = el('a', { href: URL.createObjectURL(new Blob(['﻿' + out.join('\r\n')], { type: 'text/csv;charset=utf-8' })), download: 'gia_von_phi.csv' });
      document.body.appendChild(a); a.click(); a.remove();
    }
    refresh();
  }

  // ---------- mục tiêu tháng theo kênh / tài khoản ----------
  function renderTargets(content) {
    content.innerHTML = '';
    var wf = state.channel === 'wayfair';
    var FIELDS = [['total_sales', wf ? 'Tổng DS sỉ' : 'Tổng DS', 'money'], ['ad_sales', wf ? 'DS QC (giá sỉ)' : 'Ad Sales', 'money'],
                  ['spend', 'Spend', 'money'], ['tacos', 'TACoS', 'pct']];
    var month = el('input', { type: 'month', 'aria-label': 'Tháng' });
    month.value = ($('#f-end').value || iso(today())).slice(0, 7);
    var status = el('p', { class: 'note' }), tbody = el('tbody'), data = null;
    var saveBtn = el('button', { type: 'button', class: 'primary', text: 'Lưu mục tiêu' });
    content.appendChild(el('h2', { text: 'Mục tiêu tháng · ' + channel().brand }));
    content.appendChild(el('p', { class: 'note', text: 'Nhập mục tiêu cho cả kênh và / hoặc từng tài khoản. Tab Tổng quan so tiến độ tháng của ngày "Đến" với mục tiêu: không lọc tài khoản thì dùng dòng Cả kênh (để trống thì cộng các tài khoản); lọc tài khoản thì cộng mục tiêu của các tài khoản đó. Khi lọc thêm nhóm SP, brand, loại QC, portfolio hoặc campaign thì không so với mục tiêu.' }));
    content.appendChild(el('div', { class: 'table-tools' }, [el('label', { class: 'muted' }, ['Tháng ', month]), saveBtn]));
    content.appendChild(status);
    var head1 = el('tr', {}, [el('th', { class: 't pin', rowspan: 2, text: 'Tài khoản' }),
      el('th', { colspan: 4, text: 'Thực tế từ đầu tháng' }), el('th', { colspan: 4, text: 'Mục tiêu cả tháng' })]);
    var head2 = el('tr', {}, FIELDS.map(function (f) { return el('th', { text: f[1] }); }).concat(FIELDS.map(function (f) {
      return el('th', { text: f[1] + (f[2] === 'pct' ? ' %' : ' ($)') }); })));
    content.appendChild(el('div', { class: 'wrap' }, [el('table', {}, [el('thead', { class: 'two-row' }, [head1, head2]), tbody])]));

    function draw() {
      tbody.innerHTML = '';
      data.rows.forEach(function (r) {
        var ts = r.actual_total_sales, tr = el('tr', { class: r.account_key ? '' : 'sum-row' }, [el('td', { class: 't pin', text: r.label })]);
        tr.appendChild(el('td', { text: fmt(ts, 'money') }));
        tr.appendChild(el('td', { text: fmt(r.actual_sales, 'money') }));
        tr.appendChild(el('td', { text: fmt(r.actual_spend, 'money') }));
        tr.appendChild(el('td', { text: ts ? fmt(r.actual_spend / ts, 'pct') : '–' }));
        FIELDS.forEach(function (f) {
          var inp = el('input', { type: 'text', inputmode: 'decimal', class: 'num', 'aria-label': f[1] + ' mục tiêu của ' + r.label });
          inp.value = shownValue(r[f[0]], f[2] === 'pct');
          inp.addEventListener('change', function () {
            var v = numOrNull(inp.value, f[2] === 'pct');
            inp.classList.toggle('bad', typeof v === 'number' && (isNaN(v) || v < 0));
            r[f[0]] = v;
            r._dirty = true;
          });
          tr.appendChild(el('td', {}, [inp]));
        });
        tbody.appendChild(tr);
      });
    }
    function refresh(msg) {
      api('/api/targets/' + state.channel + '?month=' + month.value).then(function (d) {
        data = d;
        status.textContent = (msg ? msg + ' ' : '') + (d.actual_end ? 'Số thực tế tính tới ' + dmy(d.actual_end) + '.' : 'Tháng này chưa có số thực tế.');
        draw();
      }).catch(function (e) { status.textContent = e.message; });
    }
    saveBtn.addEventListener('click', function () {
      var rows = data.rows.filter(function (r) { return r._dirty; }).map(function (r) {
        var o = { account_key: r.account_key };
        FIELDS.forEach(function (f) { o[f[0]] = r[f[0]]; });
        return o;
      });
      if (!rows.length) { status.textContent = 'Chưa có thay đổi.'; return; }
      if (rows.some(function (r) { return FIELDS.some(function (f) { return typeof r[f[0]] === 'number' && isNaN(r[f[0]]); }); })) { alert('Có ô không phải số.'); return; }
      api('/api/targets/' + state.channel + '?month=' + month.value, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rows: rows }) })
        .then(function () { announce('Đã lưu mục tiêu'); refresh('Đã lưu.'); }).catch(function (e) { alert(e.message); });
    });
    month.addEventListener('change', function () { refresh(); });
    refresh();
  }

  // ---------- chi phí QC Shopify theo tháng (nhập tay) ----------
  function renderShopSpend(content) {
    content.innerHTML = '';
    var month = el('input', { type: 'month', 'aria-label': 'Tháng' });
    month.value = ($('#f-end').value || iso(today())).slice(0, 7);
    var status = el('p', { class: 'note' }), tbody = el('tbody'), tfoot = el('tfoot'), hist = el('div'), data = null;
    var saveBtn = el('button', { type: 'button', class: 'primary', text: 'Lưu chi phí' });
    content.appendChild(el('h2', { text: 'Chi phí quảng cáo Shopify theo tháng' }));
    content.appendChild(el('p', { class: 'note', text: 'Nhập tổng chi phí cả tháng (USD) của từng store theo nền tảng: Google Ads, Meta (Facebook / Instagram), Khác (TikTok, Pinterest, Microsoft…). Tài khoản QC tính bằng CAD / AUD thì đổi sang USD trước khi nhập. Báo cáo chia đều số của tháng cho các ngày trong tháng, nên tháng đang chạy nên nhập số ước cả tháng hoặc cập nhật lại cuối tháng. Số này dùng cho TACoS ở tab Shopify và Spend QC, TACoS chung ở trang Tổng hợp. Xóa ô = chưa nhập.' }));
    content.appendChild(el('div', { class: 'table-tools' }, [el('label', { class: 'muted' }, ['Tháng ', month]), saveBtn]));
    content.appendChild(status);
    content.appendChild(el('div', { class: 'wrap' }, [el('table', {}, [el('thead', {}, [el('tr', {},
      [el('th', { class: 't pin', text: 'Store' }), el('th', { class: 't', text: 'Nước' }), el('th', { text: 'Doanh số tháng' }),
       el('th', { text: 'Google ($)' }), el('th', { text: 'Meta ($)' }), el('th', { text: 'Khác ($)' }),
       el('th', { text: 'Tổng chi phí' }), el('th', { text: 'TACoS' })])]), tbody, tfoot])]));
    content.appendChild(el('h3', { text: '12 tháng gần nhất' }));
    content.appendChild(hist);

    function total(r) {
      var any = false, s = 0;
      data.platforms.forEach(function (p) { if (typeof r[p[0]] === 'number' && !isNaN(r[p[0]])) { any = true; s += r[p[0]]; } });
      return any ? s : null;
    }
    function monthEnd() { return iso(new Date(Date.UTC(+month.value.slice(0, 4), +month.value.slice(5, 7), 0))); }
    function drawFoot() {
      var sumSales = 0, sumSpend = 0, anySpend = false;
      data.stores.forEach(function (r) {
        var t = total(r);
        sumSales += r.sales || 0;
        if (t !== null) { anySpend = true; sumSpend += t; }
      });
      tfoot.innerHTML = '';
      tfoot.appendChild(el('tr', { class: 'sum-row' }, [el('td', { class: 't pin', text: 'Tổng' }), el('td'),
        el('td', { text: fmt(sumSales, 'money') }), el('td'), el('td'), el('td'),
        el('td', { text: anySpend ? fmt(sumSpend, 'money') : '–' }),
        el('td', { text: anySpend && sumSales ? fmt(sumSpend / sumSales, 'pct') : '–' })]));
    }
    function draw() {
      tbody.innerHTML = '';
      data.stores.forEach(function (r) {
        var totCell = el('td'), tacCell = el('td');
        function upd() {
          var t = total(r);
          totCell.textContent = t === null ? '–' : fmt(t, 'money');
          tacCell.textContent = t !== null && r.sales ? fmt(t / r.sales, 'pct') : '–';
        }
        var partial = r.sales && r.last_date && r.last_date < monthEnd() ? ' (đến ' + dmy(r.last_date) + ')' : '';
        var tr = el('tr', {}, [el('td', { class: 't pin', text: r.store }), el('td', { class: 't', text: r.country }),
          el('td', { text: r.sales ? fmt(r.sales, 'money') + partial : '–' })]);
        data.platforms.forEach(function (p) {
          var inp = el('input', { type: 'text', inputmode: 'decimal', class: 'num', 'aria-label': p[1] + ' tháng ' + month.value + ' của ' + r.store });
          inp.value = shownValue(r[p[0]], false);
          inp.addEventListener('change', function () {
            var v = numOrNull(inp.value.replace(/[$,\s]/g, ''), false);
            inp.classList.toggle('bad', typeof v === 'number' && (isNaN(v) || v < 0));
            r[p[0]] = v;
            r._dirty = r._dirty || {};
            r._dirty[p[0]] = true;
            upd();
            drawFoot();
          });
          tr.appendChild(el('td', {}, [inp]));
        });
        tr.appendChild(totCell);
        tr.appendChild(tacCell);
        upd();
        tbody.appendChild(tr);
      });
      drawFoot();
      drawHistory();
    }
    function drawHistory() {
      hist.innerHTML = '';
      var months = [], d = new Date(Date.UTC(+month.value.slice(0, 4), +month.value.slice(5, 7) - 1, 1));
      for (var i = 0; i < 12; i++) { months.push(iso(d)); d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() - 1, 1)); }
      function cell(list, m, id, key) {
        var x = list.filter(function (h) { return h.month === m && h.sales_channel_id === id; })[0];
        return x ? x[key] : null;
      }
      var tb = el('tbody');
      months.forEach(function (m) {
        var tr = el('tr', {}, [el('td', { class: 't pin' }, [el('button', { type: 'button', class: 'link', text: m.slice(0, 7),
          title: 'Mở tháng này để nhập', onclick: function () { month.value = m.slice(0, 7); refresh(); } })])]);
        data.stores.forEach(function (st) {
          var sp = cell(data.history, m, st.sales_channel_id, 'spend'), sa = cell(data.history_sales, m, st.sales_channel_id, 'sales');
          tr.appendChild(el('td', { class: sp === null ? 'muted' : '',
            text: sp === null ? (sa ? 'chưa nhập' : '–') : fmt(sp, 'money') + (sa ? ' · TACoS ' + fmt(sp / sa, 'pct') : '') }));
        });
        tb.appendChild(tr);
      });
      hist.appendChild(el('p', { class: 'note', text: 'Chi phí đã nhập và TACoS của từng store. "chưa nhập" = tháng có doanh số nhưng chưa có chi phí (báo cáo tính là 0). Bấm tên tháng để mở tháng đó.' }));
      hist.appendChild(el('div', { class: 'wrap' }, [el('table', {}, [el('thead', {}, [el('tr', {}, [el('th', { class: 't pin', text: 'Tháng' })]
        .concat(data.stores.map(function (st) { return el('th', { text: st.store + ' (' + st.country + ')' }); })))]), tb])]));
    }
    function refresh(msg) {
      api('/api/shop/ad-spend?month=' + month.value).then(function (d) {
        data = d;
        status.textContent = (msg ? msg + ' ' : '') + (d.updated_at ? 'Cập nhật lần cuối ' + dmy(String(d.updated_at).slice(0, 10)) + '.' : 'Tháng này chưa nhập chi phí.');
        draw();
      }).catch(function (e) { status.textContent = e.message; });
    }
    saveBtn.addEventListener('click', function () {
      var rows = [];
      data.stores.forEach(function (r) {
        Object.keys(r._dirty || {}).forEach(function (p) { rows.push({ sales_channel_id: r.sales_channel_id, platform: p, spend_usd: r[p] }); });
      });
      if (!rows.length) { status.textContent = 'Chưa có thay đổi.'; return; }
      if (rows.some(function (r) { return typeof r.spend_usd === 'number' && (isNaN(r.spend_usd) || r.spend_usd < 0); })) { alert('Có ô không phải số. Sửa các ô viền đỏ rồi lưu lại.'); return; }
      saveBtn.disabled = true;
      api('/api/shop/ad-spend?month=' + month.value, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rows: rows }) })
        .then(function () { saveBtn.disabled = false; announce('Đã lưu chi phí QC Shopify'); refresh('Đã lưu.'); })
        .catch(function (e) { saveBtn.disabled = false; alert(e.message); });
    });
    month.addEventListener('change', function () { refresh(); });
    refresh();
  }

  // ---------- khởi động ----------
  function init() {
    hydrateFromUrl();
    restoreDates();
    window.addEventListener('popstate', function () {
      if (!hydrateFromUrl()) return;
      restoreDates();
      setChannel(store('channel'));
      rebuildFilters();
      renderTabs(); renderControls(); load();
    });
    $('#f-preset').addEventListener('change', function (e) { if (e.target.value) { applyPreset(e.target.value); load(); } });
    // sửa ngày bằng tay = khoảng tùy chọn, không còn theo preset
    $$('#f-start, #f-end').forEach(function (inp) { inp.addEventListener('change', function () { $('#f-preset').value = ''; state.withProvisional = false; }); });
    $('#btn-apply').addEventListener('click', function () { toggleFilters(false); load(); });
    $('#f-campaign').addEventListener('keydown', function (e) { if (e.key === 'Enter') { toggleFilters(false); load(); } });
    $('#f-toggle').addEventListener('click', function () { toggleFilters(!$('#filters').classList.contains('expanded')); });
    // Chọn nhanh và Đơn vị tự tải lại; các bộ lọc khác (ngày tự chọn, ô chọn nhiều, tên campaign) chờ bấm "Xem báo cáo"
    function markDirty(e) {
      if (e.target.closest('#f-preset, #f-qty-unit')) return;
      setDirty(true);
    }
    $('#filters-body').addEventListener('change', markDirty);
    $('#f-campaign').addEventListener('input', markDirty);
    if (store('qty_unit') === 'cont') $('#f-qty-unit').value = 'cont';
    $('#f-qty-unit').addEventListener('change', function () { store('qty_unit', qtyUnit()); load(); });
    $('#btn-export').addEventListener('click', function () {
      var p = filterParams();
      if (hcParam()) p.set('hc', hcParam());
      window.open('/export/' + currentTab().report + '?' + p.toString(), '_blank');
    });
    $$('#channels button').forEach(function (b) {
      b.addEventListener('click', function () {
        if (b.dataset.channel === state.channel) return;
        state.navPush = true;
        setChannel(b.dataset.channel); renderTabs(); renderControls(); load();
      });
    });
    if (!store('tab.amazon') && store('tab')) store('tab.amazon', store('tab'));  // khóa cũ trước khi có Wayfair
    setChannel(store('channel') || 'all');
    renderTabs();
    renderControls();

    api('/api/meta').then(function (m) {
      state.meta = m;
      var lists = state.lists = {
        profile_id: m.accounts.map(function (a) { return { id: a.profile_id, label: a.account_label }; }),
        ad_type: m.ad_types.map(function (a) { return { id: a.id, label: a.label }; }),
        portfolio_id: m.portfolios.map(function (p) { return { id: p.portfolio_id, label: p.portfolio_name + (p.account_label ? ' · ' + p.account_label : '') }; }),
        pic: m.pics || [],
        group_id: m.groups.map(function (g) { return { id: g.group_id, label: g.group_name }; }),
        brand_id: m.brands.map(function (b) { return { id: b.brand_id, label: b.brand_name }; }),
        match_type: m.match_types.map(function (x) { return { id: x, label: x }; }),
        term_class: m.term_classes.map(function (x) { return { id: x.id, label: x.label }; }),
        length_bucket: m.length_buckets.map(function (x) { return { id: x, label: x === 'ASIN' ? 'ASIN' : x + ' từ' }; }),
        wf_account: (m.wf_accounts || []).map(function (a) { return { id: a.id, label: a.label }; }),
        wf_match_type: (m.wf_match_types || []).map(function (x) { return { id: x, label: x }; }),
        market: (m.markets || []).map(function (x) { return { id: x, label: x }; }),
        sales_channel: m.sales_channels || []
      };
      $$('.ms').forEach(function (box) { buildMultiSelect(box, lists[box.dataset.key || box.dataset.param] || []); });
      if ($('#f-preset').value) applyPreset($('#f-preset').value);  // tính lại theo ngày có dữ liệu thật
      showFreshness();
      load();
    }).catch(function (e) {
      $$('.ms').forEach(function (box) { buildMultiSelect(box, []); });
      $('#content').innerHTML = '';
      $('#content').appendChild(el('div', { class: 'error', text: 'Không kết nối được dữ liệu: ' + e.message +
        '. Kiểm tra file .env và đã chạy "python -m etl.run --init" chưa.' }));
    });
  }

  init();
})();
