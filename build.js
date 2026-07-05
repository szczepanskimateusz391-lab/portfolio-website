import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(".");
const dist = resolve("dist");
const entries = ["assets", "index.html", "script.js", "styles.css", "README.md", "package.json"];

if (existsSync(dist)) {
  rmSync(dist, { force: true, recursive: true });
}
mkdirSync(dist, { recursive: true });

for (const entry of entries) {
  const source = resolve(root, entry);
  if (existsSync(source)) {
    cpSync(source, resolve(dist, entry), { recursive: true });
  }
}

console.log("Static site built to dist/");
