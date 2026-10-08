// Contest (Pick'em) sample data — sample-data.md §3, Splash work league · 2026 Week 6.
// Times are minutes from Thu 10/8 00:00 ET. Raw paste mirrors the real Splash page text shape
// (uploads/sample-splash.txt); records/totals in the raw paste are ignored by the parser and illustrative.
window.CT = (() => {
  const T = (n, abbr, color, rank = '') => ({ n, abbr, color, rank });
  const tm = {
    UNLV: T('UNLV', 'UNLV', '#CF0A2C'), BSU: T('Boise State', 'BSU', '#0033A0'),
    PUR: T('Purdue', 'PUR', '#CEB888'), OSU: T('Ohio State', 'OSU', '#BB0000', '1'),
    MISS: T('Ole Miss', 'MISS', '#CE1126', '6'), LSU: T('LSU', 'LSU', '#461D7C', '9'),
    ND: T('Notre Dame', 'ND', '#0C2340', '7'), STAN: T('Stanford', 'STAN', '#8C1515'),
    TEX: T('Texas', 'TEX', '#BF5700', '2'), OU: T('Oklahoma', 'OU', '#841617', '4'),
    COLO: T('Colorado', 'COLO', '#CFB87C'), BYU: T('BYU', 'BYU', '#002E5D', '20'),
    BUF: T('Buffalo', 'BUF', '#00338D'), NYJ: T('NY Jets', 'NYJ', '#125740'),
    HOU: T('Houston', 'HOU', '#A71930'), JAX: T('Jacksonville', 'JAX', '#006778'),
    KC: T('Kansas City', 'KC', '#E31837'), BAL: T('Baltimore', 'BAL', '#241773'),
    NYG: T('NY Giants', 'NYG', '#0B2265'), PHI: T('Philadelphia', 'PHI', '#004C54'),
  };
  // cA / mA = contest / market spread for the AWAY team. side = model's side (CFB) or the side the contest gap favors (NFL).
  const games = [
    { id: 'bsu', sport: 'CFB', a: tm.UNLV, h: tm.BSU, kick: 2640, kickLbl: 'Fri 8:00 PM', cA: 10, mA: 10, model: 'BSU −9.1', edge: 0.9, side: 'a', cover: 52 },
    { id: 'osu', sport: 'CFB', a: tm.PUR, h: tm.OSU, kick: 3600, kickLbl: 'Sat 12:00 PM', cA: 27, mA: 27.5, model: 'OSU −31.2', edge: 4.2, side: 'h', cover: 60, tier: 'B' },
    { id: 'lsu', sport: 'CFB', a: tm.MISS, h: tm.LSU, kick: 3810, kickLbl: 'Sat 3:30 PM', cA: 3, mA: 3.5, model: 'MISS −1.4', edge: 4.4, side: 'a', cover: 61, tier: 'B' },
    { id: 'nd', sport: 'CFB', a: tm.ND, h: tm.STAN, kick: 3810, kickLbl: 'Sat 3:30 PM', cA: -17.5, mA: -17, model: 'ND −19.9', edge: 2.4, side: 'a', cover: 55 },
    { id: 'ou', sport: 'CFB', a: tm.TEX, h: tm.OU, neutral: 'Dallas', kick: 4050, kickLbl: 'Sat 7:30 PM', cA: -7, mA: -6.5, model: 'TEX −1.3', edge: 5.7, side: 'h', cover: 64, tier: 'A' },
    { id: 'byu', sport: 'CFB', a: tm.COLO, h: tm.BYU, kick: 4230, kickLbl: 'Sat 10:30 PM', cA: 5.5, mA: 6, model: 'BYU −9.1', edge: 3.6, side: 'h', cover: 59, tier: 'B' },
    { id: 'buf', sport: 'NFL', a: tm.BUF, h: tm.NYJ, kick: 5100, kickLbl: 'Sun 1:00 PM', cA: -3, mA: -4.5, side: 'a', cover: 54, approx: true },
    { id: 'hou', sport: 'NFL', a: tm.HOU, h: tm.JAX, kick: 5100, kickLbl: 'Sun 1:00 PM', cA: -1, mA: -1.5, side: 'a', cover: 51, approx: true },
    { id: 'kc', sport: 'NFL', a: tm.KC, h: tm.BAL, kick: 5305, kickLbl: 'Sun 4:25 PM', cA: 2.5, mA: 2.5, side: null, cover: 50 },
    { id: 'phi', sport: 'NFL', a: tm.NYG, h: tm.PHI, kick: 5540, kickLbl: 'Sun 8:20 PM', cA: 6, mA: 7, side: 'h', cover: 53, approx: true },
  ];
  const byId = Object.fromEntries(games.map(g => [g.id, g]));
  const NOW = { thu: { m: 1320, lbl: 'Thu 10:00 PM' }, fri: { m: 2652, lbl: 'Fri 8:12 PM' }, sat: { m: 3735, lbl: 'Sat 2:15 PM' }, sun: { m: 5560, lbl: 'Sun 8:40 PM' } };
  const tierColor = { A: ['var(--tier-a)', 'var(--tier-a-foreground)'], B: ['var(--tier-b)', 'var(--tier-b-foreground)'], C: ['var(--tier-c)', 'var(--tier-c-foreground)'] };

  const num = v => String(Math.abs(v));
  const sgn = v => v === 0 ? 'PK' : (v > 0 ? '+' : '−') + num(v);
  const fav = (g, v) => v === 0 ? 'PK' : v < 0 ? `${g.a.abbr} −${num(v)}` : `${g.h.abbr} −${num(v)}`;
  const sideLine = (g, s) => s === 'a' ? `${g.a.abbr} ${sgn(g.cA)}` : `${g.h.abbr} ${sgn(-g.cA)}`;
  const sideTeam = (g, s) => s === 'a' ? g.a : g.h;
  const gapOf = g => { const d = g.cA - g.mA; return d === 0 ? null : { side: d > 0 ? 'a' : 'h', pts: Math.abs(d) }; };
  const countdown = (kick, now) => {
    const d = kick - now; if (d <= 0) return '';
    const D = Math.floor(d / 1440), H = Math.floor((d % 1440) / 60), M = d % 60;
    return D > 0 ? `${D}d ${H}h` : H > 0 ? `${H}h ${M}m` : `${M}m`;
  };
  const sep = g => g.neutral ? 'vs' : '@';

  // Ranked slate against the contest line
  const rank = nowKey => {
    const now = NOW[nowKey].m;
    const open = games.filter(g => g.kick > now).sort((x, y) => y.cover - x.cover || (y.edge || 0) - (x.edge || 0));
    const locked = games.filter(g => g.kick <= now);
    const order = {}; open.forEach((g, i) => { order[g.id] = i + 1; });
    // Ranking as it stood before kickoffs: used for locked picks, and as the whole ranking once every game has locked.
    const all = games.slice().sort((x, y) => y.cover - x.cover || (y.edge || 0) - (x.edge || 0));
    const preOrder = {}; all.forEach((g, i) => { preOrder[g.id] = i + 1; });
    const allLocked = open.length === 0;
    const top4 = (allLocked ? all : open).filter(g => g.sport === 'CFB' || g.side).slice(0, 4).map(g => g.id);
    locked.forEach(g => { if (order[g.id] == null) order[g.id] = preOrder[g.id]; });
    return { open, locked, order, top4, now, allLocked };
  };

  const btnStyle = (state) => ({
    sel: { bg: 'var(--foreground)', fg: 'var(--background)', bd: 'var(--foreground)', w: '600', op: '1', cur: 'pointer' },
    model: { bg: 'transparent', fg: 'var(--foreground)', bd: 'var(--edge)', w: '600', op: '1', cur: 'pointer' },
    idle: { bg: 'transparent', fg: 'var(--foreground)', bd: 'var(--input)', w: '500', op: '1', cur: 'pointer' },
    full: { bg: 'transparent', fg: 'var(--muted-foreground)', bd: 'var(--border)', w: '500', op: '.55', cur: 'not-allowed' },
    locked: { bg: 'transparent', fg: 'var(--locked)', bd: 'var(--border)', w: '500', op: '.7', cur: 'not-allowed' },
  })[state];

  const row = (g, R, picks, onPick) => {
    const now = R.now, locked = g.kick <= now, pick = picks[g.id], full = Object.keys(picks).length >= 4;
    const gap = gapOf(g), hasModel = g.sport === 'CFB', top = R.top4.includes(g.id);
    const gapGood = gap && (gap.side === g.side);
    const mk = s => {
      const isSel = pick && pick.side === s, isModel = top && g.side === s;
      const st = locked ? 'locked' : isSel ? 'sel' : (!pick && full) ? 'full' : isModel ? 'model' : 'idle';
      const S = btnStyle(st);
      return { label: sideLine(g, s), sel: !!isSel, notSel: !isSel, isModel: isModel && !locked, dotRing: isSel ? 'var(--foreground)' : 'var(--card)', locked, ...S,
        onClick: (e) => { e && e.stopPropagation && e.stopPropagation(); if (!locked) onPick(g.id, s); } };
    };
    const tc = tierColor[g.tier] || [];
    return {
      id: g.id, g, sport: g.sport, isNFL: g.sport === 'NFL', a: g.a, h: g.h, sep: sep(g), isNeutral: !!g.neutral, neutralTxt: g.neutral ? 'N · ' + g.neutral : '',
      rank: locked ? '' : String(R.order[g.id]), top4: top && !locked, notTop: !top || locked,
      contest: fav(g, g.cA), mkt: fav(g, g.mA), mktNum: g.mA === 0 ? 'PK' : '−' + num(g.mA),
      hasGap: !!gap, noGap: !gap, gapTxt: gap ? `${sideTeam(g, gap.side).abbr} +${gap.pts}` : '',
      gapColor: !gap ? 'var(--muted-foreground)' : !g.side ? 'var(--foreground)' : gapGood ? 'var(--pos)' : 'var(--neg)',
      gapIcon: gapGood ? 'arrow-up-right' : 'arrow-down-right',
      gapNote: gap ? `contest ${sgn(g.cA)} · market ${sgn(g.mA)}` : 'same as market',
      hasModel, noModel: !hasModel, model: g.model || '',
      edgeTxt: hasModel ? `+${g.edge} ${sideTeam(g, g.side).abbr}` : '', edgePick: hasModel && g.edge >= 2.5, edgeLow: hasModel && g.edge < 2.5,
      tier: g.tier || '', hasTier: !!g.tier, tierBg: tc[0], tierFg: tc[1],
      nflGap: !hasModel && gap ? `${gap.pts} pt${gap.pts === 1 ? '' : 's'} off mkt → ${sideTeam(g, gap.side).abbr}` : (!hasModel ? 'No gap to market' : ''),
      cover: (g.approx ? '~' : '') + g.cover + '%', coverW: g.cover + '%', approx: !!g.approx || !hasModel, exact: hasModel,
      coverFill: hasModel ? (g.edge >= 2.5 ? 'var(--edge)' : 'var(--input)') : 'var(--muted-foreground)',
      coverInk: locked ? 'var(--locked)' : 'var(--foreground)',
      coverSub: hasModel ? (g.side ? sideLine(g, g.side) : '') : 'mkt-implied',
      kickLbl: g.kickLbl, locked, open: !locked, lockTxt: countdown(g.kick, now), soon: !locked && g.kick - now < 24 * 60,
      lockColor: !locked && g.kick - now < 24 * 60 ? 'var(--foreground)' : 'var(--muted-foreground)',
      picked: !!pick, pickedSide: pick ? pick.side : '',
      ba: mk('a'), bh: mk('h'), ink: locked ? 'var(--locked)' : 'var(--foreground)',
      rowBg: locked ? 'var(--background)' : pick ? 'color-mix(in oklch, var(--foreground) 4%, transparent)' : 'transparent',
      lockedPick: pick ? `Your pick · ${sideLine(g, pick.side)}` : 'Picks closed',
    };
  };

  const build = (nowKey, picks, onPick) => {
    const R = rank(nowKey);
    const open = R.open.map(g => row(g, R, picks, onPick));
    const above = open.slice(0, 4), below = open.slice(4);
    const locked = R.locked.map(g => row(g, R, picks, onPick));
    const n4 = above[3], n5 = below[0];
    const cut = n5 ? { last: n4 ? `#4 ${n4.cover}` : '', next: `#5 ${n5.g.sport === 'NFL' ? sideLine(n5.g, n5.g.side) : sideLine(n5.g, n5.g.side)} · ${n5.cover}`, gap: n4 ? `${Math.abs(n4.g.cover - n5.g.cover)} pts below #4` : '' } : null;
    return { R, above, below, locked, cut, all: [...open, ...locked], hasLocked: locked.length > 0 };
  };

  // Pick tray
  const tray = (nowKey, picks, actions) => {
    const R = rank(nowKey);
    const items = Object.entries(picks).sort((x, y) => x[1].ord - y[1].ord).map(([id, p]) => {
      const g = byId[id], other = p.side === 'a' ? 'h' : 'a', top = R.top4.includes(id);
      const match = top && g.side === p.side, opp = top && g.side !== p.side;
      const gap = gapOf(g), locked = g.kick <= R.now;
      const why = match ? `Model's #${R.order[id]} pick · ${g.cover}% to cover`
        : opp ? `Model has the other side (${sideLine(g, g.side)})`
        : g.sport === 'NFL' ? `No model yet (NFL) · contest ${gap ? gap.pts + ' pts better than market' : 'same as market'} · ~${g.cover}% mkt-implied`
        : `Model ranks it #${R.order[id]} · ${g.cover}% to cover`;
      return {
        id, g, team: sideTeam(g, p.side), line: p.line || sideLine(g, p.side), at: p.at, matchup: `${g.a.n} ${sep(g)} ${g.h.n}`,
        kickLbl: g.kickLbl, lockTxt: countdown(g.kick, R.now), locked, open: !locked,
        match, mismatch: !match, badge: match ? `Model #${R.order[id]}` : opp ? 'Against model' : 'Your call', why,
        notTopTxt: match ? '' : 'Not in model’s top 4', lockLine: locked ? '' : 'open ' + countdown(g.kick, R.now),
        switchLbl: `Switch to ${sideLine(g, other)}`,
        onSwitch: () => actions.pick(id, other), onRemove: () => actions.remove(id),
      };
    });
    const sugg = R.top4.filter(id => !picks[id] && byId[id].kick > R.now).map(id => {
      const g = byId[id];
      return { id, line: sideLine(g, g.side), team: sideTeam(g, g.side), cover: g.cover + '%', rank: '#' + R.order[id], kickLbl: g.kickLbl, onAdd: () => actions.pick(id, g.side) };
    });
    const n = items.length, open = Math.max(0, 4 - n);
    const slots = Array.from({ length: open }, (_, i) => ({ i, s: sugg[i] || null, hasS: !!sugg[i], noS: !sugg[i] }));
    const shared = items.filter(x => x.match).length;
    const segs = Array.from({ length: 4 }, (_, i) => ({ c: i < n ? 'var(--foreground)' : 'var(--secondary)' }));
    return { items, slots, n, open, countTxt: `${n} of 4`, shared, sharedTxt: `${shared} of ${n} match the model`, segs, full: n >= 4, sugg, allLocked: R.allLocked, slotLbl: R.allLocked ? 'Empty · no games left to pick' : 'Open slot', hint: R.allLocked ? 'all games locked, picks are final' : 'tap a side in the slate to add', top4: R.top4.map(id => byId[id]) };
  };

  // Raw Splash paste — same structure as the real page copy
  const blocks = [
    { day: 'Friday, Oct 9' },
    { id: 'bsu', a: 'UNLV', h: 'Boise State', t: 'Fri 8:00pm', ar: '3-2', hr: '4-1', al: '+10', hl: '-10', tot: '55.5' },
    { day: 'Saturday, Oct 10' },
    { id: 'osu', a: 'Purdue', h: 'Ohio State', hrank: '#1ranked #1', t: 'Sat 12:00pm', ar: '1-4', hr: '5-0', al: '+27', hl: '-27', tot: '52.5' },
    { id: 'lsu', a: 'Ole Miss', h: 'LSU', t: 'Sat 3:30pm', ar: '5-0', hr: '4-1', al: '+3', hl: '-3', tot: '55.5' },
    { id: 'nd', a: 'Notre Dame', h: 'Stanford', t: 'Sat 3:30pm', ar: '4-1', hr: '2-3', al: '-17.5', hl: '+17.5', tot: '49.5' },
    { id: 'ou', a: 'Texas', h: 'Oklahoma', t: 'Sat 7:30pm', ar: '5-0', hr: '4-1', al: '-7', hl: '+7', tot: '61.5' },
    { id: 'byu', a: 'Colorado', h: 'BYU', t: 'Sat 10:30pm', ar: '3-2', hr: '4-1', al: '+5.5', hl: '-5.5', tot: '52.5' },
    { day: 'Sunday, Oct 11' },
    { id: 'buf', nfl: 1, a: 'Bills', h: 'Jets', t: 'Sun 1:00pm', ar: '4-1', hr: '1-4', al: '-3', hl: '+3', tot: '44.5' },
    { id: 'hou', nfl: 1, bad: 1, a: 'Hou Texans', h: 'Jax', t: 'Sun 1:00pm', ar: '2-3', hr: '3-2', al: '-1', hl: '+1', tot: '45.5' },
    { id: 'kc', nfl: 1, a: 'Chiefs', h: 'Ravens', t: 'Sun 4:25pm', ar: '3-2', hr: '3-2', al: '+2.5', hl: '-2.5', tot: '47.5' },
    { id: 'phi', nfl: 1, a: 'Giants', h: 'Eagles', t: 'Sun 8:20pm', ar: '2-3', hr: '4-1', al: '+6', hl: '-6', tot: '43.5' },
  ];
  const lines = [], ranges = {};
  const L = (t, kind, gid = '', bad = false) => lines.push({ n: lines.length + 1, t, kind, gid, bad });
  [['Pick against the spread', 'hdr'], ['Picks lock:', 'hdr'], ['Sun, Oct 11, 2026, 8:20 PM', 'lock'], ['PICKS', 'hdr'], ['PTS', 'hdr'], ['STATUS', 'hdr'], ['GAME DETAILS', 'hdr']].forEach(([t, k]) => L(t, k));
  blocks.forEach(b => {
    if (b.day) return L(b.day, 'day');
    const s = lines.length + 1, id = b.id, bad = !!b.bad;
    L(b.a, 'team', id, bad); L(b.h, 'team', id, bad); L('Preview', 'status', id); L(b.t, 'time', id); L('', '', id);
    if (b.nfl) L('', '', id);
    L(b.a, 'team', id, bad); L(b.ar, 'rec', id); L(b.al, 'line', id); L('', '', id);
    if (b.nfl) L('', '', id);
    if (b.hrank) L(b.hrank, 'rank', id);
    L(b.h, 'team', id, bad); L(b.hr, 'rec', id); L(b.hl, 'line', id); L('', '', id);
    L('Over ' + b.tot, 'tot', id); L('', '', id); L('Under ' + b.tot, 'tot', id);
    ranges[id] = [s, lines.length];
  });
  const tagOf = { lock: 'lock time', day: 'date', team: 'team', time: 'kickoff', line: 'spread' };
  const captured = k => !!tagOf[k];

  const parsed = blocks.filter(b => b.id).map(b => {
    const g = byId[b.id], r = ranges[b.id], gap = gapOf(g);
    return { id: b.id, g, bad: !!b.bad, ok: !b.bad, rawA: b.a, rawH: b.h, sport: g.sport, kickLbl: g.kickLbl, a: g.a, h: g.h, sep: sep(g),
      isNeutral: !!g.neutral, neutralTxt: g.neutral ? 'N · ' + g.neutral : '',
      contest: fav(g, g.cA), mkt: fav(g, g.mA), hasGap: !!gap, noGap: !gap, gapTxt: gap ? `${sideTeam(g, gap.side).abbr} +${gap.pts}` : '',
      src: `L${r[0]}–${r[1]}`, start: r[0], end: r[1], inferred: g.sport === 'NFL' ? 'NFL · from team name' : 'CFB' };
  });
  const aliasOpts = {
    a: [{ n: 'Houston Texans', abbr: 'HOU', lg: 'NFL', color: '#A71930', best: true }, { n: 'Houston Cougars', abbr: 'HOU', lg: 'CFB · Big 12', color: '#C8102E' }, { n: 'Houston Christian', abbr: 'HCU', lg: 'FCS', color: '#00247D' }],
    h: [{ n: 'Jacksonville Jaguars', abbr: 'JAX', lg: 'NFL', color: '#006778', best: true }, { n: 'Jacksonville State', abbr: 'JVST', lg: 'CFB · CUSA', color: '#CC0000' }],
  };

  const results = {
    weeks: [
      { w: 'W1', you: '3-1', model: '2-2', y: 3, m: 2 }, { w: 'W2', you: '2-2', model: '3-1', y: 2, m: 3 },
      { w: 'W3', you: '3-1', model: '2-2', y: 3, m: 2 }, { w: 'W4', you: '1-3', model: '2-2', y: 1, m: 2 },
      { w: 'W5', you: '3-1', model: '2-2', y: 3, m: 2 },
    ],
    you: { rec: '12-8', pct: '60.0%' }, model: { rec: '11-9', pct: '55.0%' },
    league: { place: 3, of: 14, behind: 1 },
  };
  let cy = 0, cm = 0;
  results.weeks.forEach(w => { cy += w.y; cm += w.m; w.cy = cy; w.cm = cm; const d = w.y - w.m; w.diff = d === 0 ? '0' : (d > 0 ? '+' : '−') + Math.abs(d); w.diffColor = d > 0 ? 'var(--pos)' : d < 0 ? 'var(--neg)' : 'var(--muted-foreground)'; w.lead = cy - cm; });

  return { tm, games, byId, NOW, build, tray, rank, lines, ranges, tagOf, captured, parsed, aliasOpts, results, sideLine, countdown, fav, sgn };
})();
