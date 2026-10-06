// Rankings · Season Outlook · Team page sample data (2026, entering Week 6). Values from sample-data.md §4–6.
// ILLUSTRATIVE (not in sample-data.md): rating trajectories for every team except Ohio State's overall line,
// Ohio State's off/def split per week, non-OSU win distributions (chosen to match their expected wins),
// and Ohio State's unit percentiles.
window.RK = (() => {
  const T = {
    OSU: { n: 'Ohio State', abbr: 'OSU', color: '#BB0000' }, TEX: { n: 'Texas', abbr: 'TEX', color: '#BF5700' },
    ORE: { n: 'Oregon', abbr: 'ORE', color: '#154733' }, OU: { n: 'Oklahoma', abbr: 'OU', color: '#841617' },
    UGA: { n: 'Georgia', abbr: 'UGA', color: '#BA0C2F' }, MISS: { n: 'Ole Miss', abbr: 'MISS', color: '#CE1126' },
    ND: { n: 'Notre Dame', abbr: 'ND', color: '#0C2340' }, PSU: { n: 'Penn State', abbr: 'PSU', color: '#041E42' },
    LSU: { n: 'LSU', abbr: 'LSU', color: '#461D7C' }, UTAH: { n: 'Utah', abbr: 'UTAH', color: '#CC0000' },
    PUR: { n: 'Purdue', abbr: 'PUR', color: '#CEB888' }, UK: { n: 'Kentucky', abbr: 'UK', color: '#0033A0' },
    STAN: { n: 'Stanford', abbr: 'STAN', color: '#8C1515' }, KSU: { n: 'Kansas State', abbr: 'KSU', color: '#512888' },
    AKR: { n: 'Akron', abbr: 'AKR', color: '#041E42' }, OHIO: { n: 'Ohio', abbr: 'OHIO', color: '#00694E' },
    RUTG: { n: 'Rutgers', abbr: 'RUTG', color: '#CC0033' }, MINN: { n: 'Minnesota', abbr: 'MINN', color: '#7A0019' },
    UW: { n: 'Washington', abbr: 'UW', color: '#4B2E83' },
  };
  const rank = { OSU: 1, TEX: 2, ORE: 3, OU: 4, UGA: 5, MISS: 6, ND: 7, PSU: 8, LSU: 9, UTAH: 10 };
  const nx = (ha, opp, line, edge = '', tier = '') => ({ ha, opp, line, edge, tier });
  const power = [
    { t: 'OSU', d: 1, conf: 'Big Ten', rec: '5-0', rating: 27.4, off: 14.1, offRk: 3, def: 13.3, defRk: 1, sos: 34, next: nx('vs', 'PUR', 'OSU −31.2', '+3.7 OSU', 'B'), traj: [24.0, 24.9, 25.6, 26.1, 26.8, 27.4] },
    { t: 'TEX', d: -1, conf: 'SEC', rec: '5-0', rating: 25.9, off: 16.0, offRk: 1, def: 9.9, defRk: 6, sos: 21, next: nx('vs', 'OU', 'TEX −1.3', '+5.2 OU', 'A'), neutral: true, traj: [25.5, 26.2, 26.8, 27.0, 27.1, 25.9] },
    { t: 'ORE', d: 0, conf: 'Big Ten', rec: '5-0', rating: 24.8, off: 15.2, offRk: 2, def: 9.6, defRk: 9, sos: 40, next: null, traj: [22.0, 22.8, 23.5, 24.0, 24.6, 24.8] },
    { t: 'OU', d: 5, conf: 'SEC', rec: '4-1', rating: 24.4, off: 12.6, offRk: 7, def: 11.8, defRk: 3, sos: 12, next: nx('vs', 'TEX', 'TEX −1.3', '+5.2 OU', 'A'), neutral: true, traj: [20.5, 21.0, 21.6, 22.3, 22.5, 24.4] },
    { t: 'UGA', d: 0, conf: 'SEC', rec: '4-1', rating: 23.1, off: 11.0, offRk: 10, def: 12.1, defRk: 2, sos: 8, next: nx('vs', 'UK', 'UGA −19.8'), traj: [24.5, 23.8, 23.4, 23.0, 23.3, 23.1] },
    { t: 'MISS', d: 3, conf: 'SEC', rec: '5-0', rating: 22.0, off: 13.4, offRk: 5, def: 8.6, defRk: 14, sos: 29, next: nx('@', 'LSU', 'MISS −1.4', '+4.9 MISS', 'B'), traj: [19.0, 19.8, 20.4, 21.0, 21.4, 22.0] },
    { t: 'ND', d: -2, conf: 'Ind', rec: '4-1', rating: 21.7, off: 12.0, offRk: 8, def: 9.7, defRk: 8, sos: 18, next: nx('@', 'STAN', 'ND −19.9', '+2.9 ND', 'C'), traj: [22.5, 21.8, 22.6, 22.9, 23.0, 21.7] },
    { t: 'PSU', d: -4, conf: 'Big Ten', rec: '4-1', rating: 21.0, off: 10.2, offRk: 12, def: 10.8, defRk: 4, sos: 25, next: null, traj: [23.0, 23.4, 23.2, 23.6, 23.4, 21.0] },
    { t: 'LSU', d: -1, conf: 'SEC', rec: '4-1', rating: 19.4, off: 11.5, offRk: 9, def: 7.9, defRk: 17, sos: 15, next: nx('vs', 'MISS', 'MISS −1.4', '+4.9 MISS', 'B'), traj: [20.0, 20.4, 21.0, 20.8, 20.6, 19.4] },
    { t: 'UTAH', d: 2, conf: 'Big 12', rec: '5-0', rating: 15.8, off: 6.9, offRk: 28, def: 8.9, defRk: 12, sos: 47, next: nx('vs', 'KSU', 'UTAH −4.6'), traj: [12.5, 13.0, 13.9, 14.6, 15.1, 15.8] },
  ];
  // final wins distribution, buckets [≤8, 9, 10, 11, 12] in %
  const outlook = [
    { t: 'OSU', conf: 'Big Ten', rec: '5-0', proj: '11.2-0.8', projN: 11.2, dist: [1, 3, 15, 41, 40], ptg: 71, pt: 48, pcfp: 89 },
    { t: 'TEX', conf: 'SEC', rec: '5-0', proj: '10.4-1.6', projN: 10.4, dist: [6, 15, 30, 31, 18], ptg: 52, pt: 31, pcfp: 80 },
    { t: 'MISS', conf: 'SEC', rec: '5-0', proj: '10.1-1.9', projN: 10.1, dist: [9, 19, 33, 27, 12], ptg: 44, pt: 21, pcfp: 70 },
    { t: 'UGA', conf: 'SEC', rec: '4-1', proj: '9.6-2.4', projN: 9.6, dist: [13, 32, 38, 17, 0], ptg: 33, pt: 19, pcfp: 61 },
    { t: 'OU', conf: 'SEC', rec: '4-1', proj: '9.3-2.7', projN: 9.3, dist: [19, 38, 31, 12, 0], ptg: 31, pt: 15, pcfp: 52 },
  ];
  const tierColor = { A: ['var(--tier-a)', 'var(--tier-a-foreground)'], B: ['var(--tier-b)', 'var(--tier-b-foreground)'], C: ['var(--tier-c)', 'var(--tier-c-foreground)'] };
  const sgn = v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(1);
  const spark = (pts, w = 64, h = 20, minRange = 3) => {
    const mn0 = Math.min(...pts), mx0 = Math.max(...pts), mid = (mn0 + mx0) / 2, r = Math.max(mx0 - mn0, minRange);
    const mn = mid - r / 2, mx = mid + r / 2;
    const xy = pts.map((v, i) => [2 + i / (pts.length - 1) * (w - 4), 2 + (mx - v) / (mx - mn) * (h - 4)]);
    return { points: xy.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' '), cx: xy[xy.length - 1][0].toFixed(1), cy: xy[xy.length - 1][1].toFixed(1) };
  };
  const delta = d => d > 0 ? { t: '▲' + d, c: 'var(--pos)', aria: 'up ' + d } : d < 0 ? { t: '▼' + -d, c: 'var(--neg)', aria: 'down ' + -d } : { t: '—', c: 'var(--push)', aria: 'no change' };
  const histMax = 41;
  const hist = (dist, h = 20) => dist.map((p, i) => ({ p: p + '%', lab: ['≤8', '9', '10', '11', '12'][i], h: p === 0 ? '1px' : Math.max(2, Math.round(p / histMax * h)) + 'px', bg: p === 0 ? 'var(--border)' : 'var(--chart-1)' }));
  const odds = v => ({ t: v + '%', w: v + '%' });
  const team = k => ({ ...T[k], rank: rank[k] ? String(rank[k]) : '' });
  const powerRows = power.map(r => {
    const sp = spark(r.traj), nt = r.next;
    const tc = nt && nt.tier ? tierColor[nt.tier] : [];
    return {
      ...r, key: r.t, team: team(r.t), rk: String(rank[r.t]), delta: delta(r.d),
      ratingT: sgn(r.rating), offT: sgn(r.off), defT: sgn(r.def), offRkT: String(r.offRk), defRkT: String(r.defRk), sosT: String(r.sos),
      spark: sp.points, sx: sp.cx, sy: sp.cy, trajT: 'Pre ' + sgn(r.traj[0]) + ' → ' + sgn(r.rating),
      hasNext: !!nt, bye: !nt, nextHa: nt ? (r.neutral ? 'vs' : nt.ha) : '', opp: nt ? team(nt.opp) : {}, nextLine: nt ? nt.line : '',
      isNeutral: !!r.neutral, isPick: !!(nt && nt.tier), edge: nt ? nt.edge : '', tier: nt ? nt.tier : '', tierBg: tc[0], tierFg: tc[1],
      nextShort: nt ? `${r.neutral ? 'vs' : nt.ha} ${T[nt.opp].n}${r.neutral ? ' (N)' : ''}` : 'Bye week',
    };
  });
  const outlookRows = outlook.map(o => ({ ...o, key: o.t, team: team(o.t), rk: String(rank[o.t]), bars: hist(o.dist), barsLg: hist(o.dist, 28), ptgC: odds(o.ptg), ptC: odds(o.pt), pcfpC: odds(o.pcfp) }));

  const osu = {
    team: team('OSU'), conf: 'Big Ten', rec: '5-0', ats: '3-2', rating: '+27.4', off: '+14.1', offRk: '3rd', def: '+13.3', defRk: '1st', sos: '34',
    prior: 24.0, now: 27.4, retProd: '58%', talent: '2', priorWeight: '30%',
    traj: { labels: ['Pre', 'Wk 2', 'Wk 3', 'Wk 4', 'Wk 5', 'Wk 6'],
      overall: [24.0, 24.9, 25.6, 26.1, 26.8, 27.4], off: [12.6, 13.0, 13.3, 13.5, 13.8, 14.1], def: [11.4, 11.9, 12.3, 12.6, 13.0, 13.3] },
    schedule: [
      { wk: '1', ha: 'vs', opp: 'AKR', mkt: 'OSU −45', model: 'OSU −47.1', edge: '+2.1 OSU', st: 'final', res: 'W 52-6', ats: 'cov' },
      { wk: '2', ha: 'vs', opp: 'OHIO', mkt: 'OSU −32.5', model: 'OSU −30.8', edge: '+1.7 OHIO', st: 'final', res: 'W 38-13', ats: 'miss' },
      { wk: '3', ha: '@', opp: 'RUTG', mkt: 'OSU −20.5', model: 'OSU −22.0', edge: '+1.5 OSU', st: 'final', res: 'W 38-14', ats: 'cov' },
      { wk: '4', ha: '@', opp: 'MINN', mkt: 'OSU −17.5', model: 'OSU −16.2', edge: '+1.3 MINN', st: 'final', res: 'W 27-10', ats: 'miss' },
      { wk: '5', ha: 'vs', opp: 'UW', mkt: 'OSU −13.5', model: 'OSU −15.0', edge: '+1.5 OSU', st: 'final', res: 'W 34-20', ats: 'cov' },
      { wk: '6', ha: 'vs', opp: 'PUR', mkt: 'OSU −27.5', model: 'OSU −31.2', edge: '+3.7 OSU', tier: 'B', st: 'live', res: '24-3 · Q3 9:12', win: '99%', note: 'Pick OSU −27.5 · behind by 6.5' },
      { wk: '7', ha: '@', opp: 'PSU', mkt: 'OSU −3.5', model: 'OSU −4.1', edge: '+0.6 OSU', st: 'up', res: 'Sat 10/17', win: '61%', swing: true },
      { wk: '11', ha: 'vs', opp: 'ORE', mkt: '', model: 'OSU −4.9', edge: '', st: 'up', res: 'Sat 11/14', win: '63%', swing: true },
    ],
    units: [
      { grp: 'Offense', rows: [['Pass offense', 97], ['Rush offense', 91], ['Success rate', 95], ['Explosiveness', 89]] },
      { grp: 'Defense', rows: [['Pass defense', 99], ['Rush defense', 96], ['Havoc', 93], ['Explosives allowed', 97]] },
    ],
    path: { pcfp: 89, ptg: 71, pt: 48, proj: '11.2-0.8', dist: [1, 3, 15, 41, 40],
      swing: [{ wk: 'Wk 7', ha: '@', opp: 'PSU', line: 'OSU −4.1', win: 61 }, { wk: 'Wk 11', ha: 'vs', opp: 'ORE', line: 'OSU −4.9', win: 63 }] },
  };
  const ord = n => n + (n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th');
  const atsMap = { cov: { g: '✓', t: 'Covered', c: 'var(--pos)' }, miss: { g: '✗', t: 'Not covered', c: 'var(--neg)' } };
  const schedRows = osu.schedule.map(s => {
    const tc = s.tier ? tierColor[s.tier] : [];
    return { ...s, key: s.wk, opp: team(s.opp), isFinal: s.st === 'final', isLive: s.st === 'live', isUp: s.st === 'up',
      hasMkt: !!s.mkt, noMkt: !s.mkt, isPick: !!s.tier, lowEdge: !s.tier && !!s.edge, noEdge: !s.edge, tierBg: tc[0], tierFg: tc[1],
      hasAts: !!s.ats, atsG: s.ats ? atsMap[s.ats].g : '', atsT: s.ats ? atsMap[s.ats].t : '', atsC: s.ats ? atsMap[s.ats].c : '',
      hasWin: !!s.win, win: s.win || '', swing: !!s.swing, hasNote: !!s.note, note: s.note || '' };
  });
  const unitGroups = osu.units.map(g => ({ grp: g.grp, rows: g.rows.map(([l, p]) => ({ l, p: ord(p), w: p + '%' })) }));
  const pathOut = { ...osu.path, bars: hist(osu.path.dist, 56), pcfpC: odds(osu.path.pcfp), ptgC: odds(osu.path.ptg), ptC: odds(osu.path.pt),
    swing: osu.path.swing.map(s => ({ ...s, opp: team(s.opp), winT: s.win + '%', winW: s.win + '%' })) };
  const seasons = Array.from({ length: 13 }, (_, i) => 2026 - i);
  // rating trajectory chart geometry: y domain +10..+30
  const chart = (W, H, p) => {
    const tr = osu.traj, n = tr.labels.length, step = (W - p.l - p.r) / (n - 1);
    const x = i => p.l + i * step, y = v => p.t + (30 - v) / 20 * (H - p.t - p.b);
    const ser = [['overall', 'Overall', 'var(--chart-1)'], ['off', 'Off', 'var(--chart-2)'], ['def', 'Def', 'var(--chart-3)']].map(([k, l, c]) => ({
      k, l, c, points: tr[k].map((v, i) => x(i).toFixed(1) + ',' + y(v).toFixed(1)).join(' '),
      dots: tr[k].map((v, i) => ({ cx: x(i).toFixed(1), cy: y(v).toFixed(1) })), endY: y(tr[k][n - 1]), endT: l + ' ' + sgn(tr[k][n - 1]) }));
    const a = ser[1], b = ser[2];
    if (Math.abs(a.endY - b.endY) < 14) { const m = (a.endY + b.endY) / 2, up = a.endY <= b.endY; a.endY = m + (up ? -7 : 7); b.endY = m + (up ? 7 : -7); }
    ser.forEach(s => { s.ly = (s.endY + 4).toFixed(1); });
    return {
      W, H, ser, lx: (W - p.r + 8).toFixed(1), x0: String(p.l), x1: (W - p.r).toFixed(1),
      yt: [10, 15, 20, 25, 30].map(v => ({ y: y(v).toFixed(1), ty: (y(v) + 4).toFixed(1), t: '+' + v, stroke: v === 10 ? 'var(--input)' : 'var(--border)' })),
      xt: tr.labels.map((l, i) => ({ x: x(i).toFixed(1), l, ty: (H - p.b + 18).toFixed(1) })),
      priorY: y(osu.prior).toFixed(1), priorLy: (y(osu.prior) + 4).toFixed(1),
      cols: tr.labels.map((l, i) => ({ i, x: (x(i) - step / 2).toFixed(1), w: step.toFixed(1), cx: x(i).toFixed(1),
        tip: { l: l === 'Pre' ? 'Preseason' : l, overall: sgn(tr.overall[i]), off: sgn(tr.off[i]), def: sgn(tr.def[i]) } })),
      xAt: i => x(i),
    };
  };
  return { T, team, powerRows, outlookRows, osu, schedRows, unitGroups, path: pathOut, seasons, sgn, ord, chart };
})();
