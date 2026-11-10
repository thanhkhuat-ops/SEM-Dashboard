/* SaleSappV2 – vẽ đồ thị data.viz (app/viz.py) trong file HTML xuất (app/templates/export.html).
   Bản chỉ xem của các hàm đồ thị trong app.js: cùng bảng màu, định dạng số và kiểu đồ thị, nhưng không bấm để lọc bảng /
   chuyển tab. Đường tồn SKU (sku_line) dùng số liệu export.py nhúng sẵn vào spec.data thay vì gọi API.
   Sửa cách vẽ một kiểu đồ thị ở app.js thì sửa cả ở đây. */
(function () {
  'use strict';

  var PALETTE = {
    light: { c: ['#2a78d6', '#eb6834', '#16996a', '#b87d00', '#d0517f', '#008300', '#6250d6', '#e34948'], n1: '#8f8d86', n2: '#5f5d57',
             st: { OOS: '#d03b3b', CRITICAL: '#d9622b', LOW: '#a87700', OK: '#0ca30c' } },
    dark: { c: ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'], n1: '#b3b1a9', n2: '#75736d',
            st: { OOS: '#e5534b', CRITICAL: '#f08a5d', LOW: '#f2b33d', OK: '#3fbf3f' } }
  };

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
  function isIsoDate(v) { return typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v); }
  function dmy(s) { return isIsoDate(s) ? s.slice(8, 10) + '/' + s.slice(5, 7) + '/' + s.slice(0, 4) : s; }
  function dayMonth(s) { return isIsoDate(s) ? s.slice(8, 10) + '/' + s.slice(5, 7) : s; }
  function fmt(v, kind) {
    if (v === null || v === undefined || v === '') return '–';
    var n = Number(v);
    if (isNaN(n)) return String(v);
    if (kind === 'int') return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
    if (kind === 'money') return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (kind === 'pct') return (n * 100).toFixed(1) + '%';
    if (kind === 'num2') return n.toFixed(2);
    return String(v);
  }
  function fmtUnit(v, unit) {
    if (v === null || v === undefined) return '–';
    if (unit === 'days') return Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 }) + ' ngày';
    if (unit === 'cont') return fmt(v, 'num2') + ' cont';
    return fmt(v, unit === 'int' ? 'int' : unit);
  }
  function compact(v, unit) {
    if (unit === 'pct') return Math.round(v * 100) + '%';
    if (unit === 'cont') return Math.abs(v) >= 100 ? String(Math.round(v)) : String(Math.round(v * 10) / 10);
    var a = Math.abs(v), s = a >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : a >= 1e3 ? (v / 1e3).toFixed(a >= 1e5 ? 0 : 1) + 'K' : String(Math.round(v * 100) / 100);
    s = s.replace(/\.0([KM])$/, '$1');
    return unit === 'money' ? (v < 0 ? '−$' + s.slice(1) : '$' + s) : s;
  }
  function stripes(color) {
    var c = document.createElement('canvas'), x = c.getContext('2d');
    c.width = c.height = 8;
    x.fillStyle = color; x.fillRect(0, 0, 8, 8);
    x.strokeStyle = 'rgba(255, 255, 255, .6)'; x.lineWidth = 2;
    x.beginPath(); x.moveTo(-2, 10); x.lineTo(10, -2); x.moveTo(-2, 2); x.lineTo(2, -2); x.moveTo(6, 10); x.lineTo(10, 6); x.stroke();
    return x.createPattern(c, 'repeat');
  }
  function base() {
    return { text: cssVar('--muted') || '#667085', grid: cssVar('--line') || '#e4e7ec', surface: cssVar('--card') || '#fff',
             ink: cssVar('--text') || '#1d2330' };
  }
  function axisCfg(b, unit, extra) {
    return Object.assign({ grid: { color: b.grid, drawTicks: false }, border: { display: false },
      ticks: { color: b.text, padding: 6, callback: function (v) { return compact(v, unit); } } }, extra || {});
  }
  function catAxis(b, extra) {
    return Object.assign({ grid: { display: false }, border: { color: b.grid }, ticks: { color: b.text, autoSkip: true } }, extra || {});
  }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  var refLinePlugin = {
    id: 'refLines',
    beforeInit: function (chart, args, opts) {
      if (!opts || !opts.lines || !opts.lines.length || opts.axis === 'y') return;
      var pad = chart.options.layout.padding;
      chart.options.layout.padding = Object.assign({}, typeof pad === 'object' ? pad : {}, { top: 6 + 15 * Math.min(opts.lines.length, 2) });
    },
    afterDatasetsDraw: function (chart, args, opts) {
      if (!opts || !opts.lines || !opts.lines.length) return;
      var scale = chart.scales[opts.axis || 'x'], area = chart.chartArea, ctx = chart.ctx, bg = cssVar('--card') || '#fff', rowEnd = [];
      ctx.save();
      opts.lines.forEach(function (l) {
        var px = scale.getPixelForValue(l.value);
        if (px < (opts.axis === 'y' ? area.top : area.left) || px > (opts.axis === 'y' ? area.bottom : area.right)) return;
        ctx.strokeStyle = opts.color; ctx.lineWidth = 1; ctx.setLineDash([4, 3]);
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
        ctx.fillStyle = bg; ctx.globalAlpha = 0.9; ctx.fillRect(x - 2, y - 10, w + 4, 13);
        ctx.globalAlpha = 1; ctx.fillStyle = opts.color; ctx.fillText(l.label, x, y);
      });
      ctx.restore();
    }
  };

  function card(grid, spec, height) {
    var box = el('div', 'viz-card'), wrap = el('div', 'viz-canvas'), canvas = el('canvas');
    box.appendChild(el('h3', '', spec.title));
    // file xuất không bấm để lọc / chuyển tab được: bỏ các câu hướng dẫn "Bấm …"
    var sub = (spec.subtitle || '').replace(/\s*Bấm[^.]*\./g, '').trim();
    if (sub) box.appendChild(el('p', 'note', sub));
    wrap.style.height = (height || 300) + 'px';
    wrap.appendChild(canvas);
    box.appendChild(wrap);
    grid.appendChild(box);
    return { box: box, wrap: wrap, canvas: canvas };
  }
  function draw(c, config) {
    if (!window.Chart) { c.wrap.textContent = 'Không tải được Chart.js (cần mạng để xem đồ thị).'; return; }
    config.options = Object.assign({ responsive: true, maintainAspectRatio: false, animation: false }, config.options || {});
    new window.Chart(c.canvas, config);
  }
  // tổng hợp số liệu từng series cho chú thích (giống seriesSums trong app.js)
  var SUM_UNITS = { money: 1, int: 1, cont: 1 };
  function sumFmt(v, unit) {
    if (unit === 'money') return (v < 0 ? '−$' : '$') + Math.abs(Math.round(v)).toLocaleString('en-US');
    if (unit === 'pct') return (v * 100).toFixed(1) + '%';
    if (unit === 'cont') return fmt(v, 'num2') + ' cont';
    return Math.round(v).toLocaleString('en-US');
  }
  function seriesSums(spec) {
    if (/waterfall|gantt|scatter|sku_line|us_map/.test(spec.kind) || spec.sum_mode === 'none') return [];
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
        var up = 0, down = 0;
        (s.raw || s.values).forEach(function (v) { if (typeof v === 'number') { if (v > 0) up += v; else down += v; } });
        return 'tăng +' + sumFmt(up, u) + ' · giảm ' + sumFmt(down, u);
      }
      var txt = (u === 'pct' ? 'cả kỳ ' : '') + sumFmt(t, u);
      if (grand && !s.line && SUM_UNITS[u]) txt += ' (' + (t / grand * 100).toFixed(1) + '%)';
      return txt;
    });
  }
  function legend(b, style, sums, show) {
    return { display: show !== false, position: 'bottom',
             labels: { color: b.text, usePointStyle: true, pointStyle: style || 'rectRounded', boxWidth: 10, padding: 14,
                       generateLabels: function (chart) {
                         var items = window.Chart.defaults.plugins.legend.labels.generateLabels(chart);
                         items.forEach(function (it) { if (sums && sums[it.datasetIndex]) it.text += ': ' + sums[it.datasetIndex]; });
                         return items;
                       } } };
  }
  function singleSum(c, spec, sums) {
    if (spec.series.length !== 1 || !sums[0]) return;
    c.box.insertBefore(el('p', 'viz-sum', (spec.signed ? 'Tổng: ' : 'Tổng ' + spec.series[0].name + ': ') + sums[0]), c.wrap);
  }

  // cột / thanh ngang / chồng / thác nước; series line: true vẽ thành đường trên trục phải
  function categoryChart(grid, spec) {
    var horizontal = spec.kind.charAt(0) === 'h', stacked = /stacked/.test(spec.kind), b = base();
    var height = horizontal ? Math.max(stacked && spec.series.length > 3 ? 230 : 160, spec.labels.length * 30 + 70) : 300;
    var c = card(grid, spec, Math.min(height, 520)), lineUnit = null;
    var datasets = spec.series.map(function (s) {
      if (s.line) {
        lineUnit = s.unit || spec.unit;
        return { type: 'line', label: s.name, data: s.values, unit: lineUnit, yAxisID: 'y1', order: 0,
                 borderColor: roleColor(s.color), backgroundColor: roleColor(s.color), borderWidth: 2,
                 pointRadius: 2, tension: 0.25, spanGaps: true };
      }
      return { label: s.name, data: s.values, order: 1, raw: s.raw,
               backgroundColor: s.colors ? s.colors.map(roleColor) : roleColor(s.color),
               borderColor: b.surface, borderWidth: stacked ? 1 : 0, borderRadius: 3, borderSkipped: false, maxBarThickness: 24 };
    });
    var valueAxis = axisCfg(b, spec.unit, stacked ? { stacked: true } : {});
    if (spec.max) valueAxis.max = spec.max;
    if (spec.min !== undefined && spec.min !== null) { valueAxis.min = spec.min; valueAxis.beginAtZero = false; }
    if (spec.unit === 'pct') valueAxis.max = spec.max || 1;
    var waterfall = spec.kind === 'waterfall', signed = waterfall || spec.signed;
    function valueText(raw, i) {
      if (!signed || raw === null || raw === undefined || (waterfall && (i === 0 || i === spec.labels.length - 1))) return fmtUnit(raw, spec.unit);
      return (raw >= 0 ? '+' : '−') + fmtUnit(Math.abs(raw), spec.unit);
    }
    var dates = !horizontal && spec.labels.every(isIsoDate);
    var scales = horizontal ? { x: valueAxis, y: catAxis(b, { stacked: stacked, ticks: { color: b.text, autoSkip: false } }) }
                            : { x: catAxis(b, { stacked: stacked, ticks: { color: b.text, autoSkip: true, maxRotation: 0,
                                  callback: function (v) { var l = spec.labels[v]; return dates ? dayMonth(l) : l; } } }), y: valueAxis };
    if (lineUnit && !horizontal) scales.y1 = axisCfg(b, lineUnit, { position: 'right', beginAtZero: true, grid: { drawOnChartArea: false } });
    var sums = seriesSums(spec);
    singleSum(c, spec, sums);
    draw(c, {
      type: 'bar',
      data: { labels: spec.labels, datasets: datasets },
      options: {
        indexAxis: horizontal ? 'y' : 'x', interaction: { mode: 'nearest', intersect: true }, scales: scales,
        plugins: {
          legend: legend(b, 'rectRounded', sums, spec.series.length > 1),
          tooltip: { callbacks: {
            title: function (items) { return items.length ? (dates ? dmy(items[0].label) : items[0].label) : ''; },
            label: function (ctx) {
              var raw = ctx.dataset.raw ? ctx.dataset.raw[ctx.dataIndex] : ctx.raw;
              if (ctx.dataset.unit) return ' ' + ctx.dataset.label + ': ' + fmtUnit(raw, ctx.dataset.unit);
              return ' ' + (waterfall ? '' : ctx.dataset.label + ': ') + valueText(raw, ctx.dataIndex);
            } } },
          refLines: { lines: spec.refs || [], axis: horizontal ? 'x' : 'y', color: b.text }
        }
      },
      plugins: [refLinePlugin]
    });
  }

  function lineChart(grid, spec) {
    var b = base(), c = card(grid, spec, 280);
    draw(c, {
      type: 'line',
      data: { labels: spec.labels, datasets: spec.series.map(function (s) {
        return { label: s.name, data: s.values, borderColor: roleColor(s.color), backgroundColor: roleColor(s.color),
                 borderWidth: s.dash ? 1.5 : 2, borderDash: s.dash ? [6, 4] : undefined, tension: 0.2, spanGaps: true,
                 pointRadius: 0, pointHoverRadius: 4 };
      }) },
      options: {
        interaction: { mode: 'index', intersect: false },
        scales: { x: catAxis(b, { ticks: { color: b.text, maxTicksLimit: 8, maxRotation: 0,
                    callback: function (v) { return dayMonth(spec.labels[v]); } } }),
                  y: axisCfg(b, spec.unit, { beginAtZero: true }) },
        plugins: {
          legend: legend(b, 'line', seriesSums(spec)),
          tooltip: { callbacks: { title: function (items) { return items.length ? dmy(items[0].label) : ''; },
                                  label: function (ctx) { return ' ' + ctx.dataset.label + ': ' + fmtUnit(ctx.raw, spec.unit); } } }
        }
      }
    });
  }

  // ma trận sản phẩm: x = ACoS, y = doanh số QC, kích thước = Spend
  function bubbleChart(grid, spec) {
    var b = base(), c = card(grid, spec, 360);
    draw(c, {
      type: 'bubble',
      data: { datasets: spec.series.map(function (s) {
        var col = roleColor(s.color);
        return { label: s.name, data: s.values, backgroundColor: col + '99', borderColor: col, borderWidth: 1.5,
                 pointStyle: function (ctx) { return (ctx.raw && ctx.raw.pt) || 'circle'; } };
      }) },
      options: {
        scales: { x: axisCfg(b, spec.x_unit || 'pct', { beginAtZero: true, title: { display: true, text: 'ACoS', color: b.text } }),
                  y: axisCfg(b, spec.unit, { beginAtZero: true }) },
        plugins: {
          legend: legend(b, 'circle'),
          tooltip: { callbacks: {
            title: function (items) { return items.length ? items[0].raw.label : ''; },
            label: function (ctx) {
              var p = ctx.raw;
              return [' Doanh số QC: ' + fmtUnit(p.y, spec.unit), ' Spend: ' + fmt(p.spend, 'money'), ' ACoS: ' + fmt(p.acos, 'pct'),
                      ' ACoS hòa vốn: ' + (p.be === null || p.be === undefined ? 'chưa có giá vốn' : fmt(p.be, 'pct')), ' Tồn kho: ' + ctx.dataset.label];
            } } },
          refLines: { lines: spec.refs || [], axis: 'x', color: b.text }
        }
      },
      plugins: [refLinePlugin]
    });
  }

  function dayLabel(asOf, n) {
    var d = new Date(asOf + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + Math.round(n));
    return ('0' + d.getUTCDate()).slice(-2) + '/' + ('0' + (d.getUTCMonth() + 1)).slice(-2);
  }

  // lịch đứt hàng: xanh = còn đủ bán, sọc đỏ = đứt hàng tới lô kế (◆)
  function ganttChart(grid, spec) {
    var rows = spec.rows || [], b = base();
    if (!rows.length) { card(grid, spec, 40).wrap.textContent = 'Không có SKU nào dự kiến đứt hàng trong 90 ngày tới.'; return; }
    var c = card(grid, spec, Math.min(rows.length * 26 + 80, 600)), cont = spec.qty_unit === 'cont';
    function qtyText(v) { return cont ? fmt(v, 'num2') + ' cont' : fmt(v, 'int') + ' unit'; }
    var diamonds = {
      id: 'arrivalDiamonds',
      afterDatasetsDraw: function (chart) {
        var ctx = chart.ctx, xs = chart.scales.x, ys = chart.scales.y;
        ctx.save();
        rows.forEach(function (r, i) {
          if (r.arrival_day === null || r.arrival_day === undefined) return;
          var x = xs.getPixelForValue(r.arrival_day), y = ys.getPixelForValue(i), h = 6;
          ctx.beginPath(); ctx.moveTo(x, y - h); ctx.lineTo(x + h, y); ctx.lineTo(x, y + h); ctx.lineTo(x - h, y); ctx.closePath();
          ctx.fillStyle = b.ink; ctx.strokeStyle = b.surface; ctx.lineWidth = 2; ctx.fill(); ctx.stroke();
        });
        ctx.restore();
      }
    };
    var labels = rows.map(function (r) { return r.label; });
    draw(c, {
      type: 'bar',
      data: { labels: labels, datasets: [
        { label: 'Còn đủ bán', data: rows.map(function (r) { return [0, r.stock_days]; }), backgroundColor: roleColor('st:OK'),
          borderColor: b.surface, borderWidth: 1, borderSkipped: false, borderRadius: 3, maxBarThickness: 16, grouped: false },
        { label: 'Đứt hàng', data: rows.map(function (r) { return [r.stock_days, r.gap_end]; }), backgroundColor: stripes(roleColor('st:OOS')),
          borderColor: b.surface, borderWidth: 1, borderSkipped: false, borderRadius: 3, maxBarThickness: 16, grouped: false }
      ] },
      options: {
        indexAxis: 'y', interaction: { mode: 'nearest', axis: 'y', intersect: false },
        scales: {
          x: { type: 'linear', min: 0, max: spec.horizon, grid: { color: b.grid }, border: { display: false },
               ticks: { color: b.text, stepSize: 7, callback: function (v) { return dayLabel(spec.as_of, v); } } },
          y: { type: 'category', labels: labels, grid: { display: false }, border: { color: b.grid }, ticks: { color: b.text, font: { size: 11 } } }
        },
        plugins: {
          legend: legend(b, 'rect'),
          tooltip: { callbacks: {
            title: function (items) { var r = rows[items[0].dataIndex]; return r.product_sku + ' · ' + r.node; },
            label: function (ctx) {
              var r = rows[ctx.dataIndex];
              if (ctx.datasetIndex === 0) return ' Còn đủ bán tới ' + dayLabel(spec.as_of, r.stock_days) + ' (' + r.stock_days + ' ngày)';
              return ' Đứt hàng ' + (r.gap_end - r.stock_days) + ' ngày · thiếu ~' + qtyText(r.lost_units) + ' · mất ~' +
                fmt(r.lost_sales, 'money') + (r.arrival_day !== null ? ' · lô kế về ' + dayLabel(spec.as_of, r.arrival_day) : '');
            }
          } }
        }
      },
      plugins: [diamonds]
    });
  }

  // đường tồn một SKU: số liệu nhúng sẵn (spec.data = reports_inv.sku_series)
  function skuLineChart(grid, spec) {
    var d = spec.data, pick = spec.initial;
    var c = card(grid, { title: 'Đường tồn dự kiến' + (pick ? ' · ' + pick.label : ''), subtitle: spec.subtitle }, 300);
    if (!d) { c.wrap.textContent = 'Không có SKU nào để vẽ đường tồn.'; return; }
    var cont = d.qty_unit === 'cont', qf = cont ? 'num2' : 'int', qs = cont ? ' cont' : '', b = base();
    var labels = [], hist = [], proj = [], arr = [];
    d.history.forEach(function (h) { labels.push(h.date); hist.push(h.on_hand); proj.push(null); arr.push(null); });
    var todayIdx = labels.length;
    d.projection.forEach(function (p) { labels.push(p.date); hist.push(null); proj.push(p.stock); arr.push(p.arrived > 0 ? p.stock : null); });
    if (d.history.length) proj[todayIdx - 1] = hist[todayIdx - 1];
    c.box.insertBefore(el('p', 'note', 'Tồn khả dụng ' + fmt(d.available, qf) + qs + ' · bán ' + fmt(d.velocity, 'num2') + qs +
      '/ngày · ' + d.events.length + ' lô hàng về trong dự báo. Đường liền = tồn thực tế (on hand), nét đứt = dự kiến, ▲ = hàng về.'), c.wrap);
    draw(c, {
      type: 'line',
      data: { labels: labels, datasets: [
        { label: 'Tồn thực tế', data: hist, borderColor: roleColor('n1'), backgroundColor: roleColor('n1'), borderWidth: 2, pointRadius: 0, stepped: true },
        { label: 'Tồn dự kiến', data: proj, borderColor: roleColor('c1'), backgroundColor: roleColor('c1'), borderWidth: 2, borderDash: [6, 4], pointRadius: 0 },
        { label: 'Hàng về', data: arr, showLine: false, pointStyle: 'triangle', radius: 7, backgroundColor: roleColor('c2'), borderColor: b.surface, borderWidth: 2 }
      ] },
      options: {
        interaction: { mode: 'index', intersect: false },
        scales: { x: catAxis(b, { ticks: { color: b.text, maxTicksLimit: 9, maxRotation: 0, callback: function (v) { return dayMonth(labels[v]); } } }),
                  y: axisCfg(b, cont ? 'cont' : 'int', { beginAtZero: true }) },
        plugins: {
          legend: legend(b, 'circle'),
          tooltip: { callbacks: { label: function (ctx) { return ctx.raw === null ? null : ' ' + ctx.dataset.label + ': ' + fmt(ctx.raw, qf) + qs; } } },
          refLines: { lines: [{ value: todayIdx - 0.5, label: 'Hôm nay' }], axis: 'x', color: b.text }
        }
      },
      plugins: [refLinePlugin]
    });
  }

  // bản đồ Mỹ theo bang: hình bang tải từ us-atlas (cần mạng), màu tuần tự một hue
  var US_FIPS = { '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC',
    '12': 'FL', '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN', '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA',
    '23': 'ME', '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS', '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV',
    '33': 'NH', '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND', '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA',
    '44': 'RI', '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT', '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV',
    '55': 'WI', '56': 'WY' };
  var US_SMALL = { CT: 1, DE: 1, DC: 1, MA: 1, MD: 1, NH: 1, NJ: 1, RI: 1, VT: 1 };
  function mixHex(a, b2, t) {
    var pa = parseInt(a.slice(1), 16), pb = parseInt(b2.slice(1), 16), out = '#';
    [16, 8, 0].forEach(function (sh) {
      var x = Math.round(((pa >> sh) & 255) + (((pb >> sh) & 255) - ((pa >> sh) & 255)) * t);
      out += ('0' + x.toString(16)).slice(-2);
    });
    return out;
  }
  function usMapChart(grid, spec) {
    var c = card(grid, spec, 0), wrap = c.wrap;
    c.box.classList.add('viz-wide');
    wrap.style.height = '';
    var dark = isDark(), lo = dark ? '#1f3550' : '#d3e4f8', hi = dark ? '#8dbcf7' : '#174f94', empty = dark ? '#2a2f3a' : '#eceef2';
    var vals = {}, max = 0;
    spec.labels.forEach(function (code, i) { vals[code] = spec.series[0].values[i] || 0; max = Math.max(max, vals[code]); });
    function fill(v) { return v > 0 && max > 0 ? mixHex(lo, hi, v / max) : empty; }
    // không có mạng: vẫn hiện danh sách bang
    var list = spec.labels.map(function (code) { return code + ': ' + fmtUnit(vals[code], spec.unit); }).join(' · ');
    wrap.textContent = 'Đang tải bản đồ… ' + list;
    var NS = 'http://www.w3.org/2000/svg';
    function s(tag, attrs) { var n = document.createElementNS(NS, tag); Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); }); return n; }
    new Promise(function (resolve, reject) {
      var sc = document.createElement('script');
      sc.src = 'https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js';
      sc.onload = resolve; sc.onerror = reject;
      document.head.appendChild(sc);
    }).then(function () { return fetch('https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-albers-10m.json'); })
      .then(function (r) { return r.json(); })
      .then(function (topo) {
        wrap.textContent = '';
        var svg = s('svg', { viewBox: '0 0 1010 610', class: 'us-map', role: 'img', 'aria-label': spec.title + '. ' + list });
        var gS = s('g', {}), gL = s('g', {}), smallY = 150, known = {};
        window.topojson.feature(topo, topo.objects.states).features.forEach(function (f) {
          var code = US_FIPS[f.id];
          if (!code) return;
          known[code] = 1;
          var polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates, d = '', best = null, bestA = -1;
          polys.forEach(function (poly) {
            poly.forEach(function (ring) { d += 'M' + ring.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join('L') + 'Z'; });
            var ring = poly[0], a = 0, cx = 0, cy = 0;
            for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
              var k = ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1];
              a += k; cx += (ring[j][0] + ring[i][0]) * k; cy += (ring[j][1] + ring[i][1]) * k;
            }
            if (Math.abs(a) > bestA) { bestA = Math.abs(a); best = [cx / (3 * a), cy / (3 * a)]; }
          });
          var v = vals[code] || 0, path = s('path', { d: d, fill: fill(v), class: 'st' });
          var t0 = s('title', {}); t0.textContent = f.properties.name + ': ' + fmtUnit(v, spec.unit); path.appendChild(t0);
          gS.appendChild(path);
          if (!(v > 0) || !best) return;
          var lx = best[0], ly = best[1], anchor = 'middle';
          if (US_SMALL[code]) {
            lx = 940; ly = smallY; smallY += 34; anchor = 'start';
            gL.appendChild(s('line', { x1: best[0], y1: best[1], x2: lx - 4, y2: ly - 4, class: 'lead' }));
          }
          var t = s('text', { x: lx, y: ly, 'text-anchor': anchor, class: 'st-label' });
          t.appendChild(s('tspan', { x: lx, dy: '-0.2em', class: 'code' })).textContent = code;
          t.appendChild(s('tspan', { x: lx, dy: '1.15em' })).textContent = compact(v, spec.unit === 'cont' ? 'cont' : 'int');
          gL.appendChild(t);
        });
        svg.appendChild(gS); svg.appendChild(gL);
        wrap.appendChild(svg);
        var outside = spec.labels.filter(function (code) { return !known[code]; });
        if (outside.length) {
          wrap.appendChild(el('p', 'note', 'Ngoài Mỹ: ' + outside.map(function (code) {
            return (code === 'CAN' ? 'Canada' : code) + ' ' + fmtUnit(vals[code], spec.unit);
          }).join(' · ')));
        }
      }).catch(function () { wrap.textContent = 'Không tải được bản đồ (cần mạng). ' + list; });
  }

  window.renderExportViz = function (grid, viz) {
    (viz || []).forEach(function (spec) {
      if (spec.kind === 'gantt') ganttChart(grid, spec);
      else if (spec.kind === 'us_map') usMapChart(grid, spec);
      else if (spec.kind === 'sku_line') skuLineChart(grid, spec);
      else if (spec.kind === 'line') lineChart(grid, spec);
      else if (spec.kind === 'scatter') bubbleChart(grid, spec);
      else if (spec.labels && spec.labels.length) categoryChart(grid, spec);
    });
  };
})();
