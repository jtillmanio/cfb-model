// Sample data for This Week (2026 · Week 6). Spreads, opening lines, model, cover, tiers, stars, weather and the alert
// come from sample-data.md §1. Intermediate line snapshots (between open and now) are illustrative.
// Totals: only OSU/PUR and TEX/OU have sample values (market vs model, no total picks); every other total shows —.
window.TW = (() => {
  const tm = (n, abbr, color, rank = '', score = '', tag = '') => ({ n, abbr, color, rank, score, tag });
  const P = (t, tone = 'fg', icon = '') => ({ t, tone, icon });
  const games = [
    { id: 'bsu', grp: 0, status: 'final', time: '8:00 PM', net: 'FS1', away: tm('UNLV', 'UNLV', '#CF0A2C', '', '24'), home: tm('Boise State', 'BSU', '#0033A0', '', '31'), win: 'BSU 74%',
      ats: { fav: 'BSU', mkt: 'BSU −10', open: -9.5, hist: [-9.5, -10, -10, -10], model: 'BSU −9.1', edge: '+0.9 UNLV', cover: 52 },
      ou: {},
      notes: { ats: [P('No pick · UNLV covered', 'muted', 'check')], ou: [] } },
    { id: 'osu', grp: 1, status: 'live', clock: 'Q3 9:12', net: 'FOX', away: tm('Purdue', 'PUR', '#CEB888', '', '3'), home: tm('Ohio State', 'OSU', '#BB0000', '1', '24'), win: 'OSU 99%',
      ats: { fav: 'OSU', mkt: 'OSU −27.5', open: -28, hist: [-28, -28, -27.5, -27.5], model: 'OSU −31.2', edge: '+3.7 OSU', cover: 59, tier: 'B', bet: 'OSU −27.5', live: 'Not yet · needs 28+', liveTone: 'neg' },
      ou: { mkt: '52.5', model: '54.1' },
      notes: { ats: [P('OSU −27.5 · not yet, needs 28+', 'neg')], ou: [] } },
    { id: 'wis', grp: 1, status: 'live', clock: 'Q2 2:41', net: 'BTN', star: true,
      wx: { icon: 'wind', kind: 'Wind', main: '17 mph, gusts 26', rest: '48°F · rain 10%', where: 'Camp Randall, Madison · 12:00 PM kickoff', why: 'Sustained wind ≥ 15 mph' },
      away: tm('Iowa', 'IOWA', '#FFCD00', '', '10'), home: tm('Wisconsin', 'WIS', '#C5050C', '', '7'), win: 'IOWA 53%',
      ats: { fav: 'WIS', mkt: 'WIS −1.5', open: -2.5, hist: [-2.5, -2, -1.5, -1.5], model: 'IOWA −1.2', edge: '+2.7 IOWA', cover: 55, tier: 'C', bet: 'IOWA +1.5', live: 'Covering', liveTone: 'pos' },
      ou: {},
      notes: { ats: [P('IOWA +1.5 · covering', 'pos')], ou: [] } },
    { id: 'clem', grp: 1, status: 'up', time: '12:00 PM', net: 'ESPN+', away: tm('Furman', 'FUR', '#582C83', '', '', 'FCS'), home: tm('Clemson', 'CLEM', '#F56600'), win: 'CLEM 99%',
      ats: { model: 'CLEM −34.0' }, ou: {},
      gnote: P('FCS · no lines yet', 'muted', 'clock'), notes: { ats: [], ou: [] } },
    { id: 'lsu', grp: 2, status: 'up', time: '3:30 PM', net: 'CBS', away: tm('Ole Miss', 'MISS', '#CE1126', '6'), home: tm('LSU', 'LSU', '#461D7C', '9'), win: 'MISS 54%',
      ats: { fav: 'LSU', mkt: 'LSU −3.5', open: -2.5, hist: [-2.5, -2.5, -3, -3.5], model: 'MISS −1.4', edge: '+4.9 MISS', cover: 62, tier: 'B', bet: 'MISS +3.5', spark: [-2.5, -2.5, -3, -3.5], move: '+1.0', moveTone: 'pos', picked: 'Picked at +2.5 · CLV +1.0' },
      ou: {},
      notes: { ats: [P('Picked at −2.5 → now −3.5', 'muted', 'history'), P('CLV +1.0 · moved our way', 'pos')], ou: [] } },
    { id: 'nd', grp: 2, status: 'up', time: '3:30 PM', net: 'NBC', away: tm('Notre Dame', 'ND', '#0C2340', '7'), home: tm('Stanford', 'STAN', '#8C1515'), win: 'ND 92%',
      ats: { fav: 'ND', mkt: 'ND −17', open: -16.5, hist: [-16.5, -17, -17, -17], model: 'ND −19.9', edge: '+2.9 ND', cover: 56, tier: 'C', bet: 'ND −17' },
      ou: {},
      notes: { ats: [P('Pick ND −17')], ou: [] } },
    { id: 'nw', grp: 2, status: 'up', time: '3:30 PM', net: 'ABC', away: tm('Michigan', 'MICH', '#00274C', '14'), home: tm('Northwestern', 'NW', '#4E2A84'), win: 'MICH 72%',
      ats: { fav: 'MICH', mkt: 'MICH −9', open: -9, hist: [-9, -9, -9, -9], model: 'MICH −8.4', edge: '+0.6 NW', cover: 51 },
      ou: {},
      notes: { ats: [], ou: [] } },
    { id: 'utah', grp: 3, status: 'up', time: '7:00 PM', net: 'ESPN', away: tm('Kansas State', 'KSU', '#512888'), home: tm('Utah', 'UTAH', '#CC0000', '10'), win: 'UTAH 63%',
      ats: { fav: 'UTAH', mkt: 'UTAH −4', open: -3.5, hist: [-3.5, -4, -4, -4], model: 'UTAH −4.6', edge: '+0.6 UTAH', cover: 51 },
      ou: {},
      notes: { ats: [], ou: [] } },
    { id: 'ou', grp: 3, status: 'up', time: '7:30 PM', net: 'ABC', neutral: 'Dallas', star: true, away: tm('Texas', 'TEX', '#BF5700', '2'), home: tm('Oklahoma', 'OU', '#841617', '4'), win: 'TEX 54%',
      ats: { fav: 'TEX', mkt: 'TEX −6.5', open: -7, hist: [-7, -6.5, -6, -6.5], model: 'TEX −1.3', edge: '+5.2 OU', cover: 63, tier: 'A', bet: 'OU +6.5', spark: [-7, -6.5, -6, -6.5], move: '−0.5', moveTone: 'neg', picked: 'Opened +7 · picked at +6.5' },
      ou: { mkt: '61.5', model: '58.0' },
      notes: { ats: [P('Pick OU +6.5')], ou: [] } },
    { id: 'uga', grp: 3, status: 'up', time: '7:30 PM', net: 'SECN',
      wx: { icon: 'cloud-rain', kind: 'Rain', main: '80% chance, ~0.6 in', rest: '66°F · wind 6 mph', where: 'Sanford Stadium, Athens · 7:30 PM kickoff', why: 'Rain or snow ≥ 60% likely' },
      away: tm('Kentucky', 'UK', '#0033A0'), home: tm('Georgia', 'UGA', '#BA0C2F', '5'), win: 'UGA 92%',
      ats: { fav: 'UGA', mkt: 'UGA −21', open: -22.5, hist: [-22.5, -22, -21.5, -21], model: 'UGA −19.8', edge: '+1.2 UK', cover: 53 },
      ou: {},
      notes: { ats: [], ou: [] } },
    { id: 'byu', grp: 3, status: 'up', time: '10:30 PM', net: 'ESPN', away: tm('Colorado', 'COLO', '#CFB87C'), home: tm('BYU', 'BYU', '#002E5D', '20'), win: 'BYU 74%',
      ats: { fav: 'BYU', mkt: 'BYU −6', open: -7, hist: [-7, -7, -6, -6], model: 'BYU −9.1', edge: '+3.1 BYU', cover: 57, tier: 'C', bet: 'BYU −6' },
      ou: {},
      notes: { ats: [P('Pick BYU −6')], ou: [] } },
  ];
  const groups = [
    { label: 'Fri night', time: 'Fri 10/9 · 8:00 PM ET' },
    { label: 'Sat noon', time: 'Sat 10/10 · 12:00 PM ET' },
    { label: 'Sat afternoon', time: '3:30 PM ET' },
    { label: 'Sat night', time: '7:00 – 10:30 PM ET' },
  ];
  const alerts = [
    { icon: 'move-horizontal', game: 'Colorado @ BYU', title: 'Line moved BYU −7 → −6', body: 'Edge now +3.1 BYU, tier C (was below the threshold)', when: 'Wed 7:04 PM', via: 'Sent by email', unread: true, gid: 'byu' },
  ];
  const tierColor = { A: ['var(--tier-a)', 'var(--tier-a-foreground)'], B: ['var(--tier-b)', 'var(--tier-b-foreground)'], C: ['var(--tier-c)', 'var(--tier-c-foreground)'] };
  const toneColor = { pos: 'var(--pos)', neg: 'var(--neg)', muted: 'var(--muted-foreground)', fg: 'var(--foreground)' };
  const num = v => (v < 0 ? '−' : v > 0 ? '+' : '') + Math.abs(v);
  // Sparkline in favorite-margin terms: a bigger favorite plots higher. Flat lines sit mid-height.
  const spark = (pts, w = 28, h = 12) => {
    if (!pts) return '';
    const m = pts.map(Math.abs), mn = Math.min(...m), mx = Math.max(...m), r = mx - mn;
    return m.map((v, i) => `${(i / (m.length - 1) * w).toFixed(1)},${(r ? 1 + (mx - v) / r * (h - 2) : h / 2).toFixed(1)}`).join(' ');
  };
  const endPt = (pts, w, h) => { const s = spark(pts, w, h).split(' ').pop().split(','); return { x: s[0], y: s[1] }; };
  const line = (g, key) => {
    const m = g[key], isPick = !!m.tier, hasLine = !!m.mkt, tc = tierColor[m.tier] || [];
    const hasOpen = hasLine && m.open != null;
    const flat = hasOpen && m.hist.every(v => v === m.hist[0]);
    return {
      key, label: key === 'ats' ? 'ATS' : 'O/U', hasLine, noLine: !hasLine, mkt: m.mkt || '', model: m.model || '—',
      isPick, notPick: !isPick, lowEdge: !isPick && !!m.edge, noEdge: !m.edge, edge: m.edge || '', edgeOrDash: m.edge || '—',
      hasCover: !!m.cover, noCover: !m.cover, cover: m.cover ? m.cover + '%' : '—', coverW: (m.cover || 0) + '%',
      coverFill: isPick ? 'var(--edge)' : 'var(--input)', coverInk: isPick ? 'var(--foreground)' : 'var(--muted-foreground)', coverWeight: isPick ? '600' : '400',
      tier: m.tier || '', tierBg: tc[0], tierFg: tc[1],
      hasOpen, noOpen: !hasOpen, openT: hasOpen ? num(m.open) : '', hist: hasOpen ? spark(m.hist, 22, 10) : '', histEnd: hasOpen ? endPt(m.hist, 22, 10) : { x: 0, y: 0 },
      histM: hasOpen ? spark(m.hist, 16, 8) : '', histEndM: hasOpen ? endPt(m.hist, 16, 8) : { x: 0, y: 0 },
      openTip: hasOpen ? (flat ? `Opened ${m.fav} ${num(m.open)} · unchanged` : `Opened ${m.fav} ${num(m.open)} → now ${m.mkt} · ${m.hist.length} snapshots`) : '',
      openLbl: hasOpen ? (flat ? 'no move' : 'opened ' + num(m.open)) : '',
      moved: !!m.spark, still: !m.spark, spark: spark(m.spark), move: m.move || '', moveColor: toneColor[m.moveTone] || toneColor.muted,
      bet: m.bet || '', picked: m.picked || '', hasPicked: !!m.picked, live: m.live || '', liveColor: toneColor[m.liveTone] || '',
    };
  };
  const decorate = (g, mkt) => {
    const lines = mkt === 'both' ? [line(g, 'ats'), line(g, 'ou')] : [line(g, mkt === 'spread' ? 'ats' : 'ou')];
    const raw = [g.gnote, ...(mkt !== 'total' ? g.notes.ats : []), ...(mkt !== 'spread' ? g.notes.ou : [])].filter(Boolean);
    const notes = raw.map(n => ({ ...n, color: toneColor[n.tone], hasIcon: !!n.icon }));
    return {
      ...g, lines, notes, hasNotes: notes.length > 0,
      day: g.grp === 0 ? 'Fri' : 'Sat', isLive: g.status === 'live', isFinal: g.status === 'final', isUp: g.status === 'up',
      sep: g.neutral ? 'vs' : '@', hasWx: !!g.wx, wx: g.wx || {}, wxIcon: g.wx ? g.wx.icon : '', wxText: g.wx ? g.wx.kind : '',
      awayRank: g.away.rank, homeRank: g.home.rank, isNeutral: !!g.neutral, neutralText: g.neutral ? 'N · ' + g.neutral : '',
      awayLead: g.away.score && +g.away.score > +g.home.score, homeLead: g.home.score && +g.home.score > +g.away.score,
      coverM: lines.map(l => (lines.length > 1 ? l.label + ' ' : '') + l.cover).join(' · '),
      isPickIn: lines.some(l => l.isPick),
    };
  };
  const slate = (mkt, stars, filter = 'all', list = games) => groups.map((gr, i) => ({
    ...gr, rows: list.filter(g => g.grp === i).map(g => ({ ...decorate(g, mkt), starred: stars ? stars.has(g.id) : !!g.star }))
      .filter(r => filter === 'starred' ? r.starred : filter === 'picks' ? r.isPickIn : true),
  })).filter(gr => gr.rows.length > 0);
  const best = (mkt, stars, list = games) => {
    const all = [];
    list.forEach(g => ['ats', 'ou'].forEach(k => {
      if (!g[k].tier) return;
      if (mkt === 'spread' && k === 'ou') return;
      if (mkt === 'total' && k === 'ats') return;
      const d = decorate(g, 'both'), l = line(g, k);
      all.push({ ...l, coverN: g[k].cover, gid: g.id, g: d, matchup: `${g.away.n} ${d.sep} ${g.home.n}`, started: g.status !== 'up', starred: stars ? stars.has(g.id) : !!g.star,
        sub: l.picked || (l.live ? '' : (k === 'ats' ? 'Spread' : 'Total')) });
    }));
    all.sort((a, b) => b.coverN - a.coverN || parseFloat(b.edge) - parseFloat(a.edge));
    const up = all.filter(x => !x.started).map((x, i) => ({ ...x, rank: i + 1 }));
    const started = all.filter(x => x.started).map(x => ({ ...x, rank: '·' }));
    return { up, started };
  };
  // "This week" record strip, Sat ~2:15 PM ET: 9 spread picks = 1 Thursday win, 2 live (IOWA covering, OSU not yet), 6 to play.
  const week = {
    rec: '1-0', units: '+1.0u', live: 2, liveNote: 'IOWA covering, OSU not yet', toPlay: 6, picks: 9,
    segs: [
      { t: 'Won · Thu night', bg: 'var(--pos)', bd: 'var(--pos)' },
      { t: 'Live · covering · IOWA +1.5', bg: 'repeating-linear-gradient(135deg, color-mix(in oklch, var(--live) 60%, transparent) 0 3px, transparent 3px 6px)', bd: 'var(--live)' },
      { t: 'Live · not covering yet · OSU −27.5', bg: 'repeating-linear-gradient(135deg, color-mix(in oklch, var(--live) 60%, transparent) 0 3px, transparent 3px 6px)', bd: 'var(--live)' },
      ...Array.from({ length: 6 }, () => ({ t: 'To play', bg: 'transparent', bd: 'var(--input)' })),
    ],
  };
  // Before lines post (Sun–Mon): model lines only, no market, no picks. Same games, illustrative state.
  const preLines = games.map(g => ({ ...g, status: 'up', clock: undefined, time: g.time || '12:00 PM', away: { ...g.away, score: '' }, home: { ...g.home, score: '' },
    ats: { model: g.ats.model }, ou: g.ou.model ? { model: g.ou.model } : {}, gnote: g.away.tag === 'FCS' ? g.gnote : P('No line posted yet', 'muted', 'clock'), notes: { ats: [], ou: [] } }));
  // Alert history across weeks (Week 6 rows from sample-data; Weeks 3–5 illustrative, built from Ohio State's schedule lines).
  const alertsHistory = [
    { ...alerts[0], hdr: 'This week · Week 6', hasHdr: true },
    { icon: 'move-horizontal', game: 'Iowa @ Wisconsin', title: 'Line moved WIS −2.5 → −1.5', body: 'Edge now +2.7 IOWA, tier C (was +3.7, tier B)', when: 'Tue 11:20 AM', via: 'Sent by email', unread: true, gid: 'wis', hasHdr: false },
    { icon: 'move-horizontal', game: 'Washington @ Ohio State', title: 'Line moved OSU −15 → −13.5', body: 'Edge now +1.5 OSU, below the threshold', when: 'Thu 6:02 PM', via: 'Sent by email', unread: false, gid: '', hdr: 'Week 5', hasHdr: true },
    { icon: 'move-horizontal', game: 'Ohio State @ Minnesota', title: 'Line moved OSU −16 → −17.5', body: 'Edge now +1.3 MINN, below the threshold', when: 'Wed 8:45 PM', via: 'Sent by email', unread: false, gid: '', hdr: 'Week 4', hasHdr: true },
    { icon: 'move-horizontal', game: 'Ohio State @ Rutgers', title: 'Line moved OSU −19.5 → −20.5', body: 'Edge now +1.5 OSU, below the threshold', when: 'Tue 9:30 AM', via: 'Sent by email', unread: false, gid: '', hdr: 'Week 3', hasHdr: true },
  ];
  return { games, groups, alerts, alertsHistory, slate, best, week, spark, preLines };
})();
