// Picks & Performance sample data. Values from sample-data.md §1 and §7.
// ILLUSTRATIVE (not in sample-data.md): the 3 Week 6 picks not shown in §1 (Tulane Thu win, Iowa State, Arizona State),
// picked-at times, every Week 5 pick row, per-week CLV,
// and the conference and favorite/underdog splits (chosen so they sum to 31-24-1, +4.6u).
// Week-of-season records are derived from §7's cumulative units (they are the only W-L split that fits).
// NOTE: §1 lists Ole Miss CLV as +1.0 (picked +2.5, now +3.5). Kept as given; see chat note on the sign.
window.PK = (() => {
  const C = { OU: '#841617', MISS: '#CE1126', OSU: '#BB0000', ISU: '#C8102E', BYU: '#002E5D', ND: '#0C2340', ASU: '#8C1D40', TULN: '#006747', IOWA: '#FFCD00',
    UGA: '#BA0C2F', UTAH: '#CC0000', LSU: '#461D7C', TCU: '#4D1979', MINN: '#7A0019', KSU: '#512888', NCST: '#CC0000', WAKE: '#9E7E38', UCF: '#BA9B37',
    ARMY: '#D3BC8D', WSU: '#981E32', SMU: '#0033A0', TTU: '#CC0000', NAVY: '#00205B' };
  const current = [
    { t: 'OU', tier: 'A', pick: 'OU +6.5', game: 'Texas vs Oklahoma', rk: '#2 vs #4', where: 'N · Dallas', kick: 'Sat 7:30 PM · ABC', conf: 'SEC', side: 'Dog', venue: 'Neutral',
      at: '+6.5', when: 'Mon 9:40 AM', opened: '+7', now: '+6.5', clv: 0, edge: 5.2, edgeAt: 5.2, cover: 63, status: 'up', star: true },
    { t: 'MISS', tier: 'B', pick: 'MISS +2.5', game: 'Ole Miss @ LSU', rk: '#6 @ #9', where: '', kick: 'Sat 3:30 PM · CBS', conf: 'SEC', side: 'Dog', venue: 'Away',
      at: '+2.5', when: 'Sun 6:10 AM', opened: '+2.5', now: '+3.5', clv: 1.0, edge: 4.9, edgeAt: 3.9, cover: 62, coverAt: 60, status: 'up', star: false },
    { t: 'OSU', tier: 'B', pick: 'OSU −27.5', game: 'Purdue @ Ohio State', rk: '@ #1', where: '', kick: 'Sat 12:00 PM · FOX', conf: 'Big Ten', side: 'Fav', venue: 'Home',
      at: '−27.5', when: 'Sun 6:10 AM', opened: '−28', now: '−27.5', clv: 0, edge: 3.7, edgeAt: 3.7, cover: 59, status: 'live', clock: 'Q3 9:12', score: 'OSU 24, PUR 3', liveT: 'Not covering · needs 28+', liveTone: 'neg' },
    { t: 'ISU', tier: 'B', pick: 'ISU −3', game: 'Iowa State @ Cincinnati', rk: '', where: '', kick: 'Sat 7:00 PM · ESPN2', conf: 'Big 12', side: 'Fav', venue: 'Away',
      at: '−3', when: 'Sun 6:10 AM', opened: '−3', now: '−3.5', clv: 0.5, edge: 3.6, edgeAt: 4.1, cover: 58, status: 'up' },
    { t: 'BYU', tier: 'C', pick: 'BYU −6', game: 'Colorado @ BYU', rk: '@ #20', where: '', kick: 'Sat 10:30 PM · ESPN', conf: 'Big 12', side: 'Fav', venue: 'Home',
      at: '−6', when: 'Wed 7:04 PM', opened: '−7', now: '−6', clv: 0, edge: 3.1, edgeAt: 3.1, cover: 57, status: 'up', note: 'Became a pick when the line moved −7 → −6' },
    { t: 'ND', tier: 'C', pick: 'ND −17', game: 'Notre Dame @ Stanford', rk: '#7 @', where: '', kick: 'Sat 3:30 PM · NBC', conf: 'Ind', side: 'Fav', venue: 'Away',
      at: '−17', when: 'Sun 6:10 AM', opened: '−16.5', now: '−17', clv: 0, edge: 2.9, edgeAt: 2.9, cover: 56, status: 'up' },
    { t: 'ASU', tier: 'C', pick: 'ASU +3', game: 'Arizona State @ Baylor', rk: '', where: '', kick: 'Sat 4:00 PM · FS1', conf: 'Big 12', side: 'Dog', venue: 'Away',
      at: '+3', when: 'Sun 6:10 AM', opened: '+3', now: '+2.5', clv: 0.5, edge: 2.9, edgeAt: 3.4, cover: 56, status: 'up' },
    { t: 'TULN', tier: 'C', pick: 'TULN +4', game: 'Tulane @ Memphis', rk: '', where: '', kick: 'Thu 7:30 PM · ESPN', conf: 'American', side: 'Dog', venue: 'Away',
      at: '+4', when: 'Sun 6:10 AM', opened: '+4', now: '+3.5', clv: 0.5, edge: 2.8, edgeAt: 3.3, cover: 56, status: 'final', score: 'TULN 27, MEM 24', res: 'W', units: 1.0 },
    { t: 'IOWA', tier: 'C', pick: 'IOWA +1.5', game: 'Iowa @ Wisconsin', rk: '', where: '', kick: 'Sat 12:00 PM · BTN', conf: 'Big Ten', side: 'Dog', venue: 'Away',
      at: '+1.5', when: 'Tue 11:20 AM', opened: '+2.5', now: '+1.5', clv: 0, edge: 2.7, edgeAt: 2.7, cover: 55, status: 'live', clock: 'Q2 2:41', score: 'IOWA 10, WIS 7', liveT: 'Covering', liveTone: 'pos', star: true },
  ];
  const p = (t, tier, pick, game, at, close, clv, score, res, conf, side, venue) => ({ t, tier, pick, game, at, now: close, clv, score, res, units: res === 'W' ? 1.0 : res === 'L' ? -1.1 : 0, conf, side, venue });
  const w5 = [
    p('UGA', 'A', 'UGA −3.5', 'Georgia @ Auburn', '−3.5', '−5', 1.5, 'UGA 31, AUB 17', 'W', 'SEC', 'Fav', 'Away'),
    p('ND', 'A', 'ND −7', 'Louisville @ Notre Dame', '−7', '−8', 1.0, 'ND 24, LOU 20', 'L', 'Ind', 'Fav', 'Home'),
    p('UTAH', 'B', 'UTAH +1', 'Utah @ Arizona', '+1', 'PK', 1.0, 'UTAH 27, ARIZ 20', 'W', 'Big 12', 'Dog', 'Away'),
    p('LSU', 'B', 'LSU −2.5', 'Missouri @ LSU', '−2.5', '−4', 1.5, 'LSU 34, MIZ 24', 'W', 'SEC', 'Fav', 'Home'),
    p('TCU', 'B', 'TCU +6.5', 'TCU @ Baylor', '+6.5', '+5', 1.5, 'BAY 38, TCU 24', 'L', 'Big 12', 'Dog', 'Away'),
    p('MINN', 'B', 'MINN +10', 'Minnesota @ Michigan', '+10', '+9', 1.0, 'MICH 23, MINN 20', 'W', 'Big Ten', 'Dog', 'Away'),
    p('KSU', 'B', 'KSU −2', 'Arizona State @ Kansas State', '−2', '−3', 1.0, 'ASU 30, KSU 27', 'L', 'Big 12', 'Fav', 'Home'),
    p('NCST', 'C', 'NCST +4', 'NC State @ Clemson', '+4', '+3', 1.0, 'CLEM 28, NCST 27', 'W', 'ACC', 'Dog', 'Away'),
    p('WAKE', 'C', 'WAKE +13', 'Wake Forest @ Miami', '+13', '+12', 1.0, 'MIA 31, WAKE 20', 'W', 'ACC', 'Dog', 'Away'),
    p('UCF', 'C', 'UCF −3', 'Cincinnati @ UCF', '−3', '−3', 0, 'CIN 26, UCF 24', 'L', 'Big 12', 'Fav', 'Home'),
    p('ARMY', 'C', 'ARMY −7', 'Tulsa @ Army', '−7', '−8.5', 1.5, 'ARMY 35, TLSA 13', 'W', 'American', 'Fav', 'Home'),
    p('WSU', 'C', 'WSU +3.5', 'Washington State @ Fresno State', '+3.5', '+2.5', 1.0, 'FRES 33, WSU 21', 'L', 'Pac-12', 'Dog', 'Away'),
    p('SMU', 'C', 'SMU −10', 'Duke @ SMU', '−10', '−11', 1.0, 'SMU 45, DUKE 24', 'W', 'ACC', 'Fav', 'Home'),
    p('TTU', 'C', 'TTU +2.5', 'Texas Tech @ Houston', '+2.5', '+1.5', 1.0, 'HOU 28, TTU 17', 'L', 'Big 12', 'Dog', 'Away'),
    p('NAVY', 'C', 'NAVY +6', 'Navy @ Memphis', '+6', '+4.5', 1.5, 'MEM 30, NAVY 27', 'W', 'American', 'Dog', 'Away'),
  ];
  const weeks = [
    { wk: 5, date: 'Sat Oct 3', w: 9, l: 6, push: 0, units: 2.4, clv: 1.1, n: 15, rows: w5 },
    { wk: 4, date: 'Sat Sep 26', w: 7, l: 7, push: 1, units: -0.7, clv: 0.6, n: 15 },
    { wk: 3, date: 'Sat Sep 19', w: 9, l: 6, push: 0, units: 2.4, clv: 1.2, n: 15 },
    { wk: 2, date: 'Sat Sep 12', w: 2, l: 3, push: 0, units: -1.3, clv: 0.4, n: 5 },
    { wk: 1, date: 'Sat Sep 5', w: 4, l: 2, push: 0, units: 1.8, clv: 0.8, n: 6 },
  ];
  const season = { rec: '31-24-1', w: 31, l: 24, push: 1, pct: 56.4, units: 4.6, roi: 7.6, clv: 0.9, picks: 56 };
  const thisWeek = { rec: '1-0', live: 2, covering: 1, toPlay: 6, units: 1.0, clv: 0.3 };
  const backtest = [
    { k: 'val', label: 'Validation 2016–2023', pct: 54.1, picks: 1184, roi: 3.3 },
    { k: 'hold', label: 'Holdout 2024–2025', pct: 53.2, picks: 263, roi: 1.6 },
  ];
  const cum = [0, 1.8, 0.5, 2.9, 2.2, 4.6];
  const cumPicks = [0, 6, 11, 26, 40, 55];
  const buckets = [
    { l: '2.5–3.5', n: 512, pct: 52.0 }, { l: '3.5–5.0', n: 431, pct: 54.6 }, { l: '5.0–7.0', n: 176, pct: 56.9 }, { l: '7.0+', n: 65, pct: 55.4 },
  ];
  const calib = [[52.5, 52.0], [55, 54.1], [57.5, 56.2], [60, 57.8], [62.5, 58.9], [65, 59.6]];
  const tiers = [
    { l: 'A · edge ≥ 5.0', w: 7, l2: 3, push: 0, bt: '56.5%', btn: 241 },
    { l: 'B · edge ≥ 3.5', w: 12, l2: 9, push: 1, bt: '54.6%', btn: 431 },
    { l: 'C · edge ≥ 2.5', w: 12, l2: 12, push: 0, bt: '52.0%', btn: 512 },
  ];
  const byWeek = weeks.slice().reverse().map(x => ({ l: 'Week ' + x.wk, w: x.w, l2: x.l, push: x.push }));
  const byConf = [
    { l: 'SEC', w: 9, l2: 5, push: 0 }, { l: 'Big Ten', w: 7, l2: 6, push: 1 }, { l: 'Big 12', w: 6, l2: 5, push: 0 },
    { l: 'ACC', w: 4, l2: 5, push: 0 }, { l: 'G5 & Ind', w: 5, l2: 3, push: 0 },
  ];
  const byFav = [{ l: 'Underdog', w: 18, l2: 11, push: 0 }, { l: 'Favorite', w: 13, l2: 13, push: 1 }];
  const versions = [
    { v: 'v1.0', status: 'production', created: 'Aug 20, 2026', mae: '12.9', bt: '54.1%', live: 56 },
    { v: 'v1.1', status: 'candidate', created: 'Sep 14, 2026', mae: '12.8', bt: '54.4%', live: 0 },
    { v: 'v1.2-dev', status: 'dev · backtest running', created: 'Oct 1, 2026', mae: '—', bt: '—', live: 0 },
  ];
  const best = {
    both: [
      { t: 'OU', team: 'Oklahoma', vs: 'vs Texas · N', kick: 'Sat 7:30 PM', line: 'OU +7', src: 'splash', other: 'Market OU +6.5', otherCov: 63, edge: 5.7, cover: 64, tier: 'A' },
      { t: 'MISS', team: 'Ole Miss', vs: '@ LSU', kick: 'Sat 3:30 PM', line: 'MISS +3.5', src: 'market', other: 'Splash MISS +3', otherCov: 61, edge: 4.9, cover: 62, tier: 'B' },
      { t: 'OSU', team: 'Ohio State', vs: 'vs Purdue', kick: 'Sat 12:00 PM', line: 'OSU −27', src: 'splash', other: 'Market OSU −27.5', otherCov: 59, edge: 4.2, cover: 60, tier: 'B' },
      { t: 'BYU', team: 'BYU', vs: 'vs Colorado', kick: 'Sat 10:30 PM', line: 'BYU −5.5', src: 'splash', other: 'Market BYU −6', otherCov: 57, edge: 3.6, cover: 59, tier: 'B' },
      { t: 'ND', team: 'Notre Dame', vs: '@ Stanford', kick: 'Sat 3:30 PM', line: 'ND −17', src: 'market', other: 'Splash ND −17.5', otherCov: 55, edge: 2.9, cover: 56, tier: 'C' },
      { t: 'IOWA', team: 'Iowa', vs: '@ Wisconsin', kick: 'Sat 12:00 PM', line: 'IOWA +1.5', src: 'market', other: '', edge: 2.7, cover: 55, tier: 'C' },
      { t: 'UK', team: 'Kentucky', vs: '@ Georgia', kick: 'Sat 7:30 PM', line: 'UK +21', src: 'market', other: '', edge: 1.2, cover: 53, tier: '' },
      { t: 'UNLV', team: 'UNLV', vs: '@ Boise State', kick: 'Fri 8:00 PM', line: 'UNLV +10', src: 'splash', other: 'Market UNLV +10', otherCov: 52, edge: 0.9, cover: 52, tier: '' },
      { t: 'NW', team: 'Northwestern', vs: 'vs Michigan', kick: 'Sat 3:30 PM', line: 'NW +9', src: 'market', other: '', edge: 0.6, cover: 51, tier: '' },
      { t: 'UTAH', team: 'Utah', vs: 'vs Kansas State', kick: 'Sat 7:00 PM', line: 'UTAH −4', src: 'market', other: '', edge: 0.6, cover: 51, tier: '' },
    ],
    // "Splash only": market lines can't be entered in the contest, so #2 and #5 fall back to Splash and non-contest games drop off.
    splash: [
      { t: 'OU', team: 'Oklahoma', vs: 'vs Texas · N', kick: 'Sat 7:30 PM', line: 'OU +7', src: 'splash', other: 'Market OU +6.5', otherCov: 63, edge: 5.7, cover: 64, tier: 'A' },
      { t: 'MISS', team: 'Ole Miss', vs: '@ LSU', kick: 'Sat 3:30 PM', line: 'MISS +3', src: 'splash', other: 'Market MISS +3.5', otherCov: 62, otherNote: 'better, not in contest', edge: 4.4, cover: 61, tier: 'B' },
      { t: 'OSU', team: 'Ohio State', vs: 'vs Purdue', kick: 'Sat 12:00 PM', line: 'OSU −27', src: 'splash', other: 'Market OSU −27.5', otherCov: 59, edge: 4.2, cover: 60, tier: 'B' },
      { t: 'BYU', team: 'BYU', vs: 'vs Colorado', kick: 'Sat 10:30 PM', line: 'BYU −5.5', src: 'splash', other: 'Market BYU −6', otherCov: 57, edge: 3.6, cover: 59, tier: 'B' },
      { t: 'ND', team: 'Notre Dame', vs: '@ Stanford', kick: 'Sat 3:30 PM', line: 'ND −17.5', src: 'splash', other: 'Market ND −17', otherCov: 56, otherNote: 'better, not in contest', edge: 2.4, cover: 55, tier: '' },
      { t: 'UNLV', team: 'UNLV', vs: '@ Boise State', kick: 'Fri 8:00 PM', line: 'UNLV +10', src: 'splash', other: 'Market UNLV +10', otherCov: 52, edge: 0.9, cover: 52, tier: '' },
    ],
    hidden: 'Iowa, Kentucky, Northwestern, Utah',
  };
  Object.assign(C, { UK: '#0033A0', UNLV: '#CF0A2C', NW: '#4E2A84' });
  best.both.concat(best.splash).forEach(r => r.color = C[r.t]);
  current.forEach(r => r.color = C[r.t]); w5.forEach(r => r.color = C[r.t]);
  const tierBg = { A: ['var(--tier-a)', 'var(--tier-a-foreground)'], B: ['var(--tier-b)', 'var(--tier-b-foreground)'], C: ['var(--tier-c)', 'var(--tier-c-foreground)'] };
  const bestView = src => {
    const list = best[src === 'splash' ? 'splash' : 'both'].map((r, i) => {
      const pick = r.edge >= 2.5, tb = tierBg[r.tier] || [];
      return { ...r, rank: i + 1, isPick: pick, notPick: !pick, edgeT: '+' + r.edge.toFixed(1) + ' ' + r.t, coverT: r.cover + '%', coverW: r.cover + '%',
        coverFill: pick ? 'var(--edge)' : 'var(--input)', coverWt: pick ? '600' : '400', coverInk: pick ? 'var(--foreground)' : 'var(--muted-foreground)',
        isSplash: r.src === 'splash', isMarket: r.src === 'market', hasOther: !!r.other, noOther: !r.other,
        otherCovT: r.otherCov ? r.otherCov + '%' : '', hasOtherNote: !!r.otherNote, otherNote: r.otherNote || '',
        hasTier: !!r.tier, noTier: !r.tier, tierBg: tb[0], tierFg: tb[1] };
    });
    const above = list.filter(r => r.isPick), below = list.filter(r => !r.isPick);
    return { above, below, count: list.length, belowTxt: below.length + ' below · shown for comparison', hidden: src === 'splash' ? best.hidden : '' };
  };
  return { current, weeks, season, thisWeek, backtest, cum, cumPicks, buckets, calib, tiers, byWeek, byConf, byFav, versions, best, bestView };
})();
