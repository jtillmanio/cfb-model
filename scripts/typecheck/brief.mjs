// What the post-edit typecheck shows Claude when it fails (.claude/kit.json › verify.fast): the
// first errors and a count, not the whole log. scripts/typecheck/run.mjs feeds it the real output
// of `pnpm typecheck` (tsc, then pyright); web/lib/typecheck-brief.test.ts feeds it fixtures.
// No imports, so run.mjs runs on bare Node.

// tsc: `lib/a.ts(1,14): error TS2322: …`. pyright: `  c:\…\a.py:2:12 - error: …`.
const ERROR_LINE = /\berror TS\d+:| - error: /;

/** @param {string} line */
const indentOf = (line) => line.length - line.trimStart().length;

/** @param {number} n @param {string} noun */
const plural = (n, noun) => `${n} ${noun}${n === 1 ? "" : "s"}`;

/**
 * @param {string} output combined stdout and stderr of the typecheck
 * @param {number} exitCode its exit code
 * @param {{ maxErrors?: number, maxDetail?: number, tailLines?: number }} [limits]
 *   errors shown, detail lines kept under each, and lines kept when no error line is recognised
 * @returns {string} the text to print; empty when the typecheck passed
 */
export function briefTypecheck(output, exitCode, { maxErrors = 10, maxDetail = 4, tailLines = 40 } = {}) {
  if (exitCode === 0) return "";
  const lines = output.split(/\r?\n/).map((line) => line.trimEnd());

  /** @type {{ indent: number, lines: string[], hidden: number }[]} */
  const errors = [];
  /** @type {{ indent: number, lines: string[], hidden: number } | null} */
  let current = null;
  for (const line of lines) {
    if (ERROR_LINE.test(line)) {
      current = { indent: indentOf(line), lines: [line], hidden: 0 };
      errors.push(current);
    } else if (current && line && indentOf(line) > current.indent) {
      // An indented line under an error is its detail (tsc's elaboration, pyright's rule name).
      if (current.lines.length <= maxDetail) current.lines.push(line);
      else current.hidden += 1;
    } else {
      current = null;
    }
  }

  if (errors.length === 0) {
    while (lines.length && !lines[lines.length - 1]) lines.pop();
    if (lines.length === 0) return `typecheck failed (exit ${exitCode}) with no output`;
    const tail = lines.slice(-tailLines);
    return [
      `typecheck failed (exit ${exitCode}) with no recognised error lines; last ${plural(tail.length, "line")}:`,
      ...tail,
    ].join("\n");
  }

  const more = errors.length - maxErrors;
  const out = [`typecheck failed (exit ${exitCode}): ${plural(errors.length, "error")}${more > 0 ? `, first ${maxErrors} shown` : ""}`];
  for (const error of errors.slice(0, maxErrors)) {
    out.push(...error.lines);
    if (error.hidden) out.push(`${" ".repeat(error.indent + 2)}... ${plural(error.hidden, "more line")}`);
  }
  if (more > 0) out.push(`... ${plural(more, "more error")} not shown`);
  return out.join("\n");
}
