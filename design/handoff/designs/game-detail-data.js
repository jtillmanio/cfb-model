// Game Detail sample data: #2 Texas vs #4 Oklahoma (sample-data.md §2) + chart geometry.
window.GD = (() => {
  const TEX = { n: 'Texas', abbr: 'TEX', color: '#BF5700', rank: '2', rec: '5-0', ats: '3-2', series: 'var(--chart-1)' };
  const OU = { n: 'Oklahoma', abbr: 'OU', color: '#841617', rank: '4', rec: '4-1', ats: '4-1', series: 'var(--chart-4)' };
  const MU = 1.3, SD = 13.8, MKT = 6.5;
  const fmt = v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(1);
  const r1 = v => Math.round(v * 10) / 10;

  const drivers = [
    { label: 'Texas pass offense vs OU pass defense', short: 'TEX pass O vs OU pass D', v: 3.8 },
    { label: 'OU rush offense vs Texas rush defense', short: 'OU rush O vs TEX rush D', v: -2.4 },
    { label: 'OU pass offense vs Texas pass defense', short: 'OU pass O vs TEX pass D', v: -1.6 },
    { label: 'Texas rush offense vs OU rush defense', short: 'TEX rush O vs OU rush D', v: 0.9 },
    { label: 'Special teams', short: 'Special teams', v: 0.4 },
    { label: 'Pace & other', short: 'Pace & other', v: 0.2 },
    { label: 'Home field (neutral site)', short: 'Home field (neutral)', v: 0 },
  ];
  const DOM = 4.5;
  const pct = v => (v + DOM) / (2 * DOM) * 100;
  const chip = t => t ? { abbr: t.abbr, color: t.color, has: true } : { abbr: 'Even', color: 'transparent', has: false };
  function waterfall(mode) {
    let run = 0;
    const rows = drivers.map((d, i) => {
      const a = mode === 'bars' ? 0 : run, b = r1(a + d.v);
      run = r1(run + d.v);
      const lo = Math.min(a, b), hi = Math.max(a, b);
      const zero = d.v === 0;
      return { ...d, val: fmt(d.v), runTxt: '= ' + fmt(run), side: chip(d.v > 0 ? TEX : d.v < 0 ? OU : null),
        left: (zero ? pct(a) - 0.25 : pct(lo)) + '%', width: (zero ? 0.5 : (hi - lo) / (2 * DOM) * 100) + '%',
        conn: mode !== 'bars' && i > 0, connLeft: pct(a) + '%', valInk: zero ? 'var(--muted-foreground)' : 'var(--foreground)' };
    });
    const total = { left: pct(0) + '%', width: (MU / (2 * DOM) * 100) + '%', connLeft: pct(run) + '%', val: fmt(run) + ' TEX' };
    const ticks = [-4, -2, 0, 2, 4].map(t => ({ left: pct(t) + '%', label: t === 0 ? '0' : fmt(t).replace('.0', ''), zero: t === 0 }));
    return { rows, total, ticks, zeroLeft: pct(0) + '%' };
  }

  // Margin distribution (Texas margin, + = Texas). Normal(MU, SD) for the drawing.
  function dist(W, H) {
    const L = 8, R = 8, top = 34, base = H - 34, X0 = -35, X1 = 35;
    const x = m => L + (m - X0) / (X1 - X0) * (W - L - R);
    const pdf = m => Math.exp(-((m - MU) ** 2) / (2 * SD * SD));
    const y = m => base - pdf(m) * (base - top);
    const pts = [];
    for (let m = X0; m <= X1 + 1e-9; m += 0.5) pts.push([x(m), y(m)]);
    const curve = pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
    const sh = pts.filter(p => p[0] <= x(MKT));
    sh.push([x(MKT), y(MKT)]);
    const shade = [[x(X0), base], ...sh, [x(MKT), base]].map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
    const hatch = [];
    for (let px = x(X0) + 6; px < x(MKT) - 2; px += 7) {
      const m = X0 + (px - L) / (W - L - R) * (X1 - X0);
      hatch.push({ x: px.toFixed(1), y2: y(m).toFixed(1) });
    }
    const ticks = [-30, -20, -10, 0, 10, 20, 30].filter(t => W > 400 || Math.abs(t) !== 30).map(t => ({ x: x(t).toFixed(1), label: t === 0 ? 'Even' : (t < 0 ? (W > 400 ? 'OU by ' : 'OU ') : (W > 400 ? 'TEX by ' : 'TEX ')) + Math.abs(t) }));
    return { W, H, vb: `0 0 ${W} ${H}`, base, top, L, Rx: W - R, curve, shade, hatch, ticks,
      mktX: x(MKT).toFixed(1), modelX: x(MU).toFixed(1), zeroX: x(0).toFixed(1), modelY: y(MU).toFixed(1),
      ouLblX: x(-13).toFixed(1), texLblX: x(19).toFixed(1), lblY: (base - 22).toFixed(1), lblY2: (base - 8).toFixed(1),
      topLbl: top - 18, axisY: base + 18, axisTitleY: H - 2, midX: (W / 2).toFixed(1) };
  }

  // Line movement sparkline (Texas spread). Bigger favorite = higher.
  const moves = [{ d: 'Sun', v: -7, t: 'Opened' }, { d: 'Tue', v: -6.5 }, { d: 'Thu', v: -6 }, { d: 'Sat', v: -6.5, t: 'Now' }];
  function spark(W, H) {
    const L = 12, R = 12, T = 18, B = H - 16;
    const pts = moves.map((m, i) => ({ ...m, x: L + i / (moves.length - 1) * (W - L - R), y: T + (m.v - -7) / (-6 - -7) * (B - T) }));
    return { vb: `0 0 ${W} ${H}`, W, H,
      line: pts.map(p => p.x.toFixed(1) + ',' + p.y.toFixed(1)).join(' '),
      pts: pts.map((p, i) => ({ x: p.x.toFixed(1), y: p.y.toFixed(1), ly: (p.y - 7).toFixed(1), dy: H - 2, d: p.d, v: fmt(p.v).replace('.0', ''), last: i === pts.length - 1, notLast: i !== pts.length - 1 })) };
  }

  // The gap: model vs market on one Texas-margin axis.
  function gap() {
    const D0 = -1, D1 = 9, p = v => (v - D0) / (D1 - D0) * 100;
    return { modelLeft: p(MU) + '%', mktLeft: p(MKT) + '%', zeroLeft: p(0) + '%', edgeLeft: p(MU) + '%', edgeWidth: (MKT - MU) / (D1 - D0) * 100 + '%',
      ticks: [0, 2, 4, 6, 8].map(t => ({ left: p(t) + '%', label: t === 0 ? 'Even' : 'TEX by ' + t })) };
  }

  // Full line history (Texas spread at each line snapshot). Snapshot times are illustrative; the values are sample data.
  // Step chart: we only know the line when the lines job ran, so it holds flat until the next snapshot.
  // mode 'openclose' = a past season, where only the opening and closing lines were stored.
  const SNAPS = [
    { d: 'Sun', t: '7 PM', h: 19, v: -7, tag: 'Opened' }, { d: 'Tue', t: '7 PM', h: 67, v: -6.5 }, { d: 'Wed', t: '7 PM', h: 91, v: -6.5 },
    { d: 'Thu', t: '7 PM', h: 115, v: -6 }, { d: 'Sat', t: '7 AM', h: 151, v: -6.5, tag: 'Latest' },
  ];
  const PAST = [{ d: 'Opened', t: 'Sun', h: 0, v: -3.5, tag: 'Opened' }, { d: 'Closed', t: 'at kickoff', h: 1, v: -2.5, tag: 'Closed' }];
  function history(W, H, mode) {
    const past = mode === 'openclose', S = past ? PAST : SNAPS;
    const L = 46, R = past ? 60 : 18, T = 26, B = H - 40;
    const h0 = S[0].h, hK = past ? 1 : 163.5;
    const mags = S.map(s => Math.abs(s.v)), lo = Math.min(...mags) - 0.25, hi = Math.max(...mags) + 0.25;
    const x = h => L + (h - h0) / (hK - h0) * (W - L - R);
    const y = v => T + (hi - Math.abs(v)) / (hi - lo) * (B - T);
    let d = '', prev = null;
    S.forEach((s, i) => { const px = x(s.h).toFixed(1), py = y(s.v).toFixed(1); d += i === 0 ? `M${px},${py}` : ` H${px} V${py}`; prev = s; });
    const dots = S.map((s, i) => {
      const changed = i === 0 || s.v !== S[i - 1].v, last = i === S.length - 1;
      return { x: x(s.h).toFixed(1), y: y(s.v).toFixed(1), ly: (y(s.v) - 9).toFixed(1), v: fmt(s.v).replace('.0', ''), changed, same: !changed, last, notLast: !last,
        r: last ? 4.5 : changed ? 3.5 : 2.5, fill: last ? 'var(--foreground)' : 'var(--card)', ink: last ? 'var(--foreground)' : 'var(--muted-foreground)', w: last ? '600' : '400',
        d: s.d, t: s.t, dy: B + 18, ty: B + 31 };
    });
    const yt = [];
    for (let m = Math.ceil(lo * 2) / 2; m <= hi + 1e-9; m += 0.5) yt.push({ y: y(-m).toFixed(1), y4: (y(-m) + 4).toFixed(1), lbl: '−' + String(m).replace('.0', '') });
    const lastX = x(S[S.length - 1].h), lastY = y(S[S.length - 1].v);
    return { vb: `0 0 ${W} ${H}`, W, H, L, Rx: W - R, T, B, d, dots, yt, past,
      straight: `${x(S[0].h).toFixed(1)},${y(S[0].v).toFixed(1)} ${lastX.toFixed(1)},${lastY.toFixed(1)}`,
      tailX1: lastX.toFixed(1), tailX2: x(hK).toFixed(1), tailY: lastY.toFixed(1), kickX: x(hK).toFixed(1), kickLblY: T - 12 };
  }

  const units = {
    texBall: [
      { unit: 'Pass', o: { t: TEX, p: 96, note: '0.34 EPA/play' }, d: { t: OU, p: 58 } },
      { unit: 'Rush', o: { t: TEX, p: 74, note: '0.08 EPA/play' }, d: { t: OU, p: 88 } },
    ],
    ouBall: [
      { unit: 'Pass', o: { t: OU, p: 71, note: '0.18 EPA/play' }, d: { t: TEX, p: 83 } },
      { unit: 'Rush', o: { t: OU, p: 90, note: '0.15 EPA/play' }, d: { t: TEX, p: 62 } },
    ],
    offense: [
      { unit: 'Success rate', a: { t: TEX, p: 91, note: '49%' }, b: { t: OU, p: 80, note: '46%' } },
      { unit: 'Explosiveness', a: { t: TEX, p: 88 }, b: { t: OU, p: 69 } },
    ],
  };
  const ord = n => n + (n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th');
  const bar = (s, role) => ({ abbr: s.t.abbr, color: s.t.color, fill: s.t.series, w: s.p + '%', pTxt: ord(s.p), note: s.note || '', hasNote: !!s.note, role });
  const unitRows = {
    texBall: units.texBall.map(u => ({ unit: u.unit, top: bar(u.o, u.unit + ' offense'), bot: bar(u.d, u.unit + ' defense') })),
    ouBall: units.ouBall.map(u => ({ unit: u.unit, top: bar(u.o, u.unit + ' offense'), bot: bar(u.d, u.unit + ' defense') })),
    offense: units.offense.map(u => ({ unit: u.unit, top: bar(u.a, 'Offense'), bot: bar(u.b, 'Offense') })),
  };

  const mark = c => c ? { ok: true, no: false, ink: 'var(--pos)', bd: 'var(--pos)', t: 'Covered' } : { ok: false, no: true, ink: 'var(--neg)', bd: 'var(--neg)', t: 'Missed' };
  const form = [
    { team: TEX, rec: '3-2', marks: [1, 0, 1, 1, 0].map((c, i) => ({ ...mark(c), wk: 'Wk ' + (i + 1) })) },
    { team: OU, rec: '4-1', marks: [1, 1, 0, 1, 1].map((c, i) => ({ ...mark(c), wk: 'Wk ' + (i + 1) })) },
  ];
  const h2h = ['2025', '2024', '2023'];

  return { TEX, OU, MU, SD, MKT, fmt, waterfall, dist, spark, history, gap, unitRows, form, h2h };
})();
