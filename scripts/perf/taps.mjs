// Times the screen-to-screen taps in routes.mjs (TASK-014, 02 › Performance checks (Lighthouse) ›
// Taps): a client navigation from one screen to the next, on the profile Lighthouse loads pages on
// (mobile screen and user agent, Slow 4G, 4× CPU; tapEmulation reads Lighthouse's own constants).
// measure.mjs runs it on the fixture build only (tapsFor). Reported, never gated on time.
//
// Each run, in a fresh browser context (cold cache, as Lighthouse's loads are):
//   1. load the tap's `from` route, signed in, and wait until its shell is no longer aria-busy;
//   2. tap `via` (untimed; e.g. opening the More sheet) and wait for `link` to show;
//   3. tap `link`. In the page, the clock starts at that tap's pointerdown and stops twice:
//      `ms` when the <h1> shows `heading` and two frames have painted (the skeleton counts), and
//      `loadedMs` when nothing is aria-busy either and two more frames have painted (the data).
//   4. record every request from the tap to `loadedMs`: report.mjs fails the run on /api/py or
//      another host (tapProblems), exactly as for a page load.
// A run that fails is recorded as { error }, never thrown: the comment lists it.

// The watcher below is serialised and runs in the page, where these exist.
/* global window, document, location, addEventListener, requestAnimationFrame */

import * as constants from "lighthouse/core/config/constants.js";
import puppeteer from "puppeteer-core";

import { scrubText, tapEmulation, tapSession } from "./lib/perf.mjs";

/** Longest a load, the sheet, or a tap may take, throttled, before the run is given up. */
const TIMEOUT_MS = 90_000;

/**
 * @param {{
 *   base: string,
 *   taps: import("./routes.mjs").PerfTap[],
 *   routes: import("./routes.mjs").PerfRoute[],
 *   runs: number,
 *   chromePath: string,
 *   ci: boolean,
 *   headers: Record<string, string>,
 *   secrets: (string | undefined)[],
 * }} args
 * @returns {Promise<Record<string, import("./lib/perf.mjs").MeasuredTap>>}
 */
export async function timeTaps({ base, taps, routes, runs, chromePath, ci, headers, secrets }) {
  /** @type {Record<string, import("./lib/perf.mjs").MeasuredTap>} */
  const out = {};
  if (!taps.length) return out;
  /** @param {unknown} e */
  const fail = (e) => ({ error: scrubText(e instanceof Error ? e.message : String(e), secrets).slice(0, 300) });
  const emulation = tapEmulation(constants);
  const session = tapSession(headers, base);
  const pathOf = (/** @type {string} */ id) => {
    const route = routes.find((r) => r.id === id);
    if (!route) throw new Error(`no route ${id} in routes.mjs`);
    return route.path;
  };

  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: chromePath,
      headless: true,
      // As measure.mjs: Actions' Ubuntu image restricts the user namespaces Chrome's sandbox needs.
      args: ci ? ["--no-sandbox"] : [],
    });
  } catch (e) {
    // No browser, no run: every tap says why, and the comment lists it.
    for (const t of taps) out[t.id] = { from: t.from, to: t.to, loads: Array.from({ length: runs }, () => fail(e)) };
    return out;
  }

  try {
    for (const tap of taps) {
      const loads = [];
      for (let n = 1; n <= runs; n++) {
        const context = await browser.createBrowserContext();
        try {
          if (session.cookie) {
            const { protocol, hostname } = new URL(session.cookie.url);
            await context.setCookie({
              name: session.cookie.name,
              value: session.cookie.value,
              domain: hostname,
              path: "/",
              secure: protocol === "https:",
              httpOnly: true,
              sameSite: "Lax",
            });
          }
          loads.push(await timeOne(await context.newPage(), { base, tap, pathOf, emulation, headers: session.headers }));
        } catch (e) {
          loads.push(fail(e));
        } finally {
          await context.close().catch(() => {});
        }
      }
      out[tap.id] = { from: tap.from, to: tap.to, loads };
      const ok = loads.filter((l) => !("error" in l)).length;
      console.log(`taps: ${tap.id}: ${ok}/${runs} taps landed`);
    }
  } finally {
    await browser.close().catch(() => {});
  }
  return out;
}

/**
 * One run of one tap.
 * @param {import("puppeteer-core").Page} page
 * @param {{
 *   base: string, tap: import("./routes.mjs").PerfTap, pathOf: (id: string) => string,
 *   emulation: ReturnType<typeof tapEmulation>, headers: Record<string, string>,
 * }} args
 * @returns {Promise<import("./lib/perf.mjs").TapLoad>}
 */
async function timeOne(page, args) {
  /** @type {{ step: string }} */
  const at = { step: "set up the browser" };
  try {
    return await steps(page, args, at);
  } catch (e) {
    throw new Error(`${at.step}: ${e instanceof Error ? e.message : String(e)}`, { cause: e });
  }
}

/**
 * timeOne's steps; `at.step` names the one running, so a failure says where it stopped.
 * @param {import("puppeteer-core").Page} page
 * @param {Parameters<typeof timeOne>[1]} args
 * @param {{ step: string }} at
 * @returns {Promise<import("./lib/perf.mjs").TapLoad>}
 */
async function steps(page, { base, tap, pathOf, emulation, headers }, at) {
  page.setDefaultTimeout(TIMEOUT_MS);
  await page.setViewport(emulation.viewport);
  await page.setUserAgent({ userAgent: emulation.userAgent });
  if (Object.keys(headers).length) await page.setExtraHTTPHeaders(headers);
  const cdp = await page.createCDPSession();
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", emulation.network);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: emulation.cpuRate });

  const from = pathOf(tap.from);
  const to = pathOf(tap.to);
  at.step = `load ${from}`;
  await page.goto(base + from, { waitUntil: "networkidle0", timeout: TIMEOUT_MS });
  const landed = new URL(page.url()).pathname;
  if (landed !== from) throw new Error(`ended on ${landed}`);
  await page.waitForSelector('[aria-busy="true"]', { hidden: true });

  if (tap.via) {
    at.step = `tap ${tap.via}`;
    await page.tap(tap.via);
    await page.waitForSelector(tap.link, { visible: true });
  }
  // Under 4× CPU, React can still be hydrating after the network goes quiet, and a tap on a link it
  // hasn't hydrated is a full page load, not the client navigation being timed.
  at.step = `wait for ${tap.link} to hydrate`;
  await page.waitForFunction(
    (sel) => {
      const el = document.querySelector(sel);
      return !!el && Object.keys(el).some((k) => k.startsWith("__reactProps$"));
    },
    {},
    tap.link,
  );

  // The watcher runs in the page, so neither clock includes the round trip to this script. A client
  // navigation keeps the document; a full reload would destroy it, and the evaluate below fails.
  at.step = "start the clock";
  await page.evaluate((heading) => {
    const w = /** @type {Window & { __tap?: Promise<{ ms: number, loadedMs: number }> }} */ (window);
    w.__tap = new Promise((resolve) => {
      /** @type {number | null} */
      let start = null;
      /** @type {number | null} */
      let ms = null;
      let frame = 0;
      let headingAt = -1;
      let loadedAt = -1;
      addEventListener("pointerdown", () => (start ??= performance.now()), { capture: true, once: true });
      const tick = () => {
        frame++;
        const now = performance.now();
        if (start !== null) {
          const shown = document.querySelector("h1")?.textContent?.trim() === heading;
          if (shown && headingAt < 0) headingAt = frame;
          if (ms === null && headingAt >= 0 && frame - headingAt >= 2) ms = now - start;
          if (shown && loadedAt < 0 && !document.querySelector('[aria-busy="true"]')) loadedAt = frame;
          if (ms !== null && loadedAt >= 0 && frame - loadedAt >= 2) {
            resolve({ ms: Math.round(ms), loadedMs: Math.round(now - start) });
            return;
          }
        }
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }, tap.heading);

  /** @type {string[]} */
  const requests = [];
  /** @param {import("puppeteer-core").HTTPRequest} req */
  const onRequest = (req) => requests.push(req.url());
  page.on("request", onRequest);
  try {
    at.step = `tap ${tap.link}`;
    await page.tap(tap.link);
    at.step = `wait for ${to}`;
    /** @type {ReturnType<typeof setTimeout> | undefined} */
    let timer;
    const timed = await Promise.race([
      page.evaluate(() => /** @type {Window & { __tap?: Promise<{ ms: number, loadedMs: number }> }} */ (window).__tap),
      new Promise((_, reject) => {
        timer = setTimeout(async () => {
          // Where it stopped, so the comment says why: still on `from`, the skeleton, or another heading.
          const seen = await page
            .evaluate(() => ({
              path: location.pathname,
              h1: [...document.querySelectorAll("h1")].map((h) => h.textContent?.trim()).join(" | ") || "none",
              busy: document.querySelectorAll('[aria-busy="true"]').length,
            }))
            .catch(() => null);
          const where = seen ? ` (on ${seen.path}, <h1> ${seen.h1}, ${seen.busy} busy)` : "";
          reject(new Error(`the <h1> never showed ${tap.heading} with the page loaded${where}`));
        }, TIMEOUT_MS);
      }),
    ]).finally(() => clearTimeout(timer));
    if (!timed) throw new Error("the tap reloaded the page instead of navigating on the client");
    const ended = new URL(page.url()).pathname;
    if (ended !== to) throw new Error(`tapped toward ${to} and ended on ${ended}`);
    return { ms: timed.ms, loadedMs: timed.loadedMs, requests: [...requests] };
  } finally {
    page.off("request", onRequest);
  }
}
