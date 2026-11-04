import { spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { beforeAll, describe, expect, it } from "vitest";

import { checkDrift, dumpSchema, generate, OUTPUT_PATH } from "../scripts/api-types.mjs";

// The web app's API response types are generated from the FastAPI schema (TASK-052, D-011) and
// the committed file must match the API as it is today. `dumpSchema` spawns uv, so the schema is
// dumped once and the tests share it.
const WEB = fileURLToPath(new URL("..", import.meta.url));
const SCRIPT = join(WEB, "scripts/api-types.mjs");
const LIB = join(WEB, "lib");

type Schema = {
  paths: Record<string, unknown>;
  components: { schemas: Record<string, { properties?: Record<string, unknown>; required?: string[] }> };
};

let schema: Schema;
let committed: string;

beforeAll(() => {
  schema = dumpSchema() as Schema;
  committed = readFileSync(OUTPUT_PATH, "utf8");
});

/** The names a `type X = { … }` or `interface X { … }` body declares at its top level. */
function objectTypeBodies(source: string): { name: string; props: string[] }[] {
  const found: { name: string; props: string[] }[] = [];
  const head = /(?:type\s+(\w+)\s*=|interface\s+(\w+))\s*\{/g;
  for (const match of source.matchAll(head)) {
    let depth = 1;
    let i = match.index + match[0].length;
    const start = i;
    while (i < source.length && depth > 0) {
      if (source[i] === "{") depth += 1;
      if (source[i] === "}") depth -= 1;
      i += 1;
    }
    const props: string[] = [];
    let level = 0;
    for (const line of source.slice(start, i - 1).split("\n")) {
      const member = /^\s*(\w+)\??\s*:/.exec(line);
      if (level === 0 && member) props.push(member[1]);
      for (const ch of line) {
        if (ch === "{") level += 1;
        if (ch === "}") level -= 1;
      }
    }
    found.push({ name: match[1] ?? match[2], props });
  }
  return found;
}

/** Hand-written object types whose property names are exactly a schema's: a copy of a response. */
function handWrittenResponseTypes(source: string, schemas: Schema["components"]["schemas"]) {
  const sets = Object.entries(schemas).map(
    ([name, s]) => [name, Object.keys(s.properties ?? {}).sort().join(",")] as const,
  );
  return objectTypeBodies(source).flatMap(({ name, props }) => {
    const key = [...props].sort().join(",");
    return sets.filter(([, setKey]) => setKey !== "" && setKey === key).map(([schemaName]) => `${name} copies ${schemaName}`);
  });
}

describe("AC-1: the generated types cover the schema", () => {
  it("generates a path entry for every route in the schema", async () => {
    const out = await generate(schema);
    const routes = Object.keys(schema.paths);
    expect(routes).toContain("/api/py/teams");
    expect(routes).toContain("/api/py/health");
    for (const route of routes) expect(out).toContain(`"${route}": {`);
  });

  it("generates a type for every response model", async () => {
    const out = await generate(schema);
    for (const name of ["TeamOut", "TeamsOut", "HealthOut"]) expect(out).toContain(`${name}: {`);
  });

  it("two generations are byte-identical, with LF line endings", async () => {
    const [a, b] = [await generate(schema), await generate(schema)];
    expect(a).toBe(b);
    expect(a).not.toContain("\r");
  });

  it("the command writes the file, and a second run leaves it byte-identical", () => {
    const dir = mkdtempSync(join(tmpdir(), "api-types-"));
    const out = join(dir, "api-types.ts");
    try {
      const run = () => spawnSync(process.execPath, [SCRIPT, "--out", out], { cwd: WEB, encoding: "utf8" });
      expect(run().status).toBe(0);
      const first = readFileSync(out, "utf8");
      expect(run().status).toBe(0);
      expect(readFileSync(out, "utf8")).toBe(first);
      expect(first).toBe(committed);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe("AC-2: no hand-written response type in web/lib", () => {
  it("the scan flags a copy of a response model", () => {
    const old = "export type TeamsResponse = {\n  season: number | null;\n  teams: Team[];\n};\n";
    expect(handWrittenResponseTypes(old, schema.components.schemas)).toEqual(["TeamsResponse copies TeamsOut"]);
    const oldHealth = "export type HealthResponse = {\n  commit: string;\n  db_reachable: boolean;\n  migration_head: string | null;\n};\n";
    expect(handWrittenResponseTypes(oldHealth, schema.components.schemas)).toEqual(["HealthResponse copies HealthOut"]);
  });

  it("the scan lets an alias of a generated type through", () => {
    const alias = 'export type Team = components["schemas"]["TeamOut"];\n';
    expect(handWrittenResponseTypes(alias, schema.components.schemas)).toEqual([]);
  });

  it("no file in web/lib copies a response model", () => {
    const files = readdirSync(LIB).filter(
      (f) => f.endsWith(".ts") && !f.endsWith(".test.ts") && f !== "api-types.ts",
    );
    expect(files).toContain("teams.ts");
    const copies = files.flatMap((f) =>
      handWrittenResponseTypes(readFileSync(join(LIB, f), "utf8"), schema.components.schemas).map((c) => `${f}: ${c}`),
    );
    expect(copies).toEqual([]);
  });
});

describe("AC-3: the drift check", () => {
  it("fails a schema with an extra TeamOut field, naming the generated file", async () => {
    const changed = structuredClone(schema);
    const teamOut = changed.components.schemas.TeamOut;
    teamOut.properties = { ...teamOut.properties, logo_url: { anyOf: [{ type: "string" }, { type: "null" }], title: "Logo Url" } };
    teamOut.required = [...(teamOut.required ?? []), "logo_url"];
    const drift = checkDrift(await generate(changed), committed);
    expect(drift.code).toBe(1);
    expect(drift.message).toContain("web/lib/api-types.ts");
    expect(drift.message).toContain("pnpm api:types");
  });

  it("passes the unchanged schema, also against a CRLF checkout", async () => {
    const generated = await generate(schema);
    expect(checkDrift(generated, generated)).toEqual({ code: 0, message: "" });
    expect(checkDrift(generated, generated.replaceAll("\n", "\r\n")).code).toBe(0);
  });

  it("the committed file matches the API today", async () => {
    const drift = checkDrift(await generate(schema), committed);
    expect(drift).toEqual({ code: 0, message: "" });
  });

  it("--check exits 0 on the committed file and 1 on a stale one", () => {
    const check = (...args: string[]) =>
      spawnSync(process.execPath, [SCRIPT, "--check", ...args], { cwd: WEB, encoding: "utf8" });
    expect(check().status).toBe(0);

    const dir = mkdtempSync(join(tmpdir(), "api-types-"));
    const stale = join(dir, "api-types.ts");
    try {
      writeFileSync(stale, committed.replace("TeamOut: {", "TeamOut: {\n      stale: string;"));
      const run = check("--out", stale);
      expect(run.status).toBe(1);
      expect(run.stderr).toContain("pnpm api:types");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});
