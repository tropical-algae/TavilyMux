import assert from "node:assert/strict"
import { readFileSync, readdirSync } from "node:fs"
import { join } from "node:path"
import test from "node:test"

const sourceRoot = new URL("../src/", import.meta.url).pathname
const stylesRoot = join(sourceRoot, "styles")

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? sourceFiles(path) : [path]
  })
}

test("keeps palette values inside the token source", () => {
  const nonTokenStyles = readdirSync(stylesRoot)
    .filter((name) => name.endsWith(".css") && name !== "tokens.css")
    .map((name) => readFileSync(join(stylesRoot, name), "utf8"))
    .join("\n")

  assert.doesNotMatch(nonTokenStyles, /#[\da-f]{3,8}\b|rgba?\(/i)
})

test("keeps action buttons on the supported variants", () => {
  const source = sourceFiles(sourceRoot)
    .filter((path) => path.endsWith(".vue") || path.endsWith(".css"))
    .map((path) => readFileSync(path, "utf8"))
    .join("\n")

  const supported = new Set([
    "primary",
    "secondary",
    "ghost",
    "danger",
    "small",
    "wide",
    "icon-mobile",
  ])
  const modifiers = [...source.matchAll(/button--([\w-]+)/g)].map((match) => match[1])
  assert.deepEqual([...new Set(modifiers.filter((modifier) => !supported.has(modifier)))], [])
})

test("keeps type and radius values on the shared scales", () => {
  const styles = readFileSync(join(stylesRoot, "main.css"), "utf8")

  assert.doesNotMatch(styles, /font-size:\s*\d*\.?\d+rem\s*;/)
  assert.doesNotMatch(styles, /border-radius:\s*\d+px/)
})

test("does not fall back to native blocking dialogs", () => {
  const source = sourceFiles(sourceRoot)
    .filter((path) => path.endsWith(".vue") || path.endsWith(".ts"))
    .map((path) => readFileSync(path, "utf8"))
    .join("\n")

  assert.doesNotMatch(source, /window\.(?:alert|confirm|prompt)\s*\(/)
})
