import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import ts from "typescript";
import { describe, expect, it } from "vitest";

// .claude/rules/web.md: never render a next/link <Link> to anything under /api/,
// because prefetch runs the route handler. Use a plain <a>.
//
// Parsed with the TypeScript compiler rather than a regex, so an href after an
// arrow-function prop or an aliased import (`import NextLink from "next/link"`)
// is still seen. An href built from a variable (`href={url}`) can't be resolved
// statically and isn't flagged; the rule still applies to it.

/** The names next/link's default export is bound to in this file. */
function linkNames(sf: ts.SourceFile): Set<string> {
  const names = new Set<string>();
  for (const stmt of sf.statements) {
    if (
      ts.isImportDeclaration(stmt) &&
      ts.isStringLiteral(stmt.moduleSpecifier) &&
      stmt.moduleSpecifier.text === "next/link" &&
      stmt.importClause?.name
    ) {
      names.add(stmt.importClause.name.text);
    }
  }
  return names;
}

/** The literal text an href starts with, or null when it isn't a literal. */
function hrefText(expr: ts.Expression | undefined): string | null {
  if (!expr) return null;
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) return expr.text;
  if (ts.isTemplateExpression(expr)) return expr.head.text;
  if (ts.isParenthesizedExpression(expr)) return hrefText(expr.expression);
  if (ts.isObjectLiteralExpression(expr)) {
    for (const prop of expr.properties) {
      if (ts.isPropertyAssignment(prop) && prop.name.getText() === "pathname") {
        return hrefText(prop.initializer);
      }
    }
  }
  return null;
}

/** `<file>:<line>` for each next/link element whose href points under /api/. */
function apiLinks(file: string, text: string): string[] {
  const kind = file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, kind);
  const names = linkNames(sf);
  if (names.size === 0) return [];

  const found: string[] = [];
  const visit = (node: ts.Node) => {
    if (
      (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
      ts.isIdentifier(node.tagName) &&
      names.has(node.tagName.text)
    ) {
      for (const attr of node.attributes.properties) {
        if (!ts.isJsxAttribute(attr) || attr.name.getText() !== "href") continue;
        const init = attr.initializer;
        const value =
          init && ts.isJsxExpression(init) ? hrefText(init.expression) : hrefText(init);
        if (value?.startsWith("/api/")) {
          const { line } = sf.getLineAndCharacterOfPosition(node.getStart());
          found.push(`${file}:${line + 1}`);
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  return found;
}

const webRoot = fileURLToPath(new URL("..", import.meta.url));

function sourceFiles(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.tsx?$/.test(name) && !/\.test\./.test(name) ? [path] : [];
  });
}

const withLink = (jsx: string, importLine = 'import Link from "next/link";') =>
  `${importLine}\nexport default function Page() {\n  return ${jsx};\n}\n`;

describe("matcher (AC-2)", () => {
  const flags = (source: string) => expect(apiLinks("page.tsx", source)).toEqual(["page.tsx:3"]);
  const passes = (source: string) => expect(apiLinks("page.tsx", source)).toEqual([]);

  it('flags href="/api/x"', () => flags(withLink('<Link href="/api/x">x</Link>')));

  it('flags href={"/api/x"}', () => flags(withLink('<Link href={"/api/x"}>x</Link>')));

  it("flags a template href under /api/", () =>
    flags(withLink("<Link href={`/api/${id}`}>x</Link>")));

  it("flags an object href whose pathname is under /api/", () =>
    flags(withLink('<Link href={{ pathname: "/api/x" }}>x</Link>')));

  it("flags an href on a later line of a multi-line tag, at the tag's line", () =>
    flags(withLink('<Link\n    onClick={() => go()}\n    href="/api/x"\n  >\n    x\n  </Link>')));

  it("flags a self-closing <Link />", () => flags(withLink('<Link href="/api/x" />')));

  it("flags the name next/link is imported as", () =>
    flags(withLink('<NextLink href="/api/x">x</NextLink>', 'import NextLink from "next/link";')));

  it("names every offender with its line", () => {
    const source = withLink('<>\n    <Link href="/api/a">a</Link>\n    <Link href="/api/b">b</Link>\n  </>');
    expect(apiLinks("app/page.tsx", source)).toEqual(["app/page.tsx:4", "app/page.tsx:5"]);
  });

  it('does not flag <a href="/api/x">', () => passes(withLink('<a href="/api/x">x</a>')));

  it('does not flag <Link href="/teams">', () => passes(withLink('<Link href="/teams">x</Link>')));

  it('does not flag <Link href="/apiary">', () => passes(withLink('<Link href="/apiary">x</Link>')));

  it('does not flag <LinkButton href="/api/x">', () =>
    passes(withLink('<LinkButton href="/api/x">x</LinkButton>')));

  it("does not flag <Link> in a file that doesn't import next/link", () =>
    passes(withLink('<Link href="/api/x">x</Link>', 'import Link from "./link";')));
});

describe("web source (AC-1)", () => {
  it("renders no next/link <Link> to /api/", () => {
    const files = ["app", "lib", "components"].flatMap((dir) => sourceFiles(join(webRoot, dir)));
    expect(files.length).toBeGreaterThan(0);
    const offenders = files.flatMap((path) =>
      apiLinks(relative(webRoot, path).replaceAll("\\", "/"), readFileSync(path, "utf8")),
    );
    expect(offenders).toEqual([]);
  });
});
