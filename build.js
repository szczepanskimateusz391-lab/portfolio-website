import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(".");
const dist = resolve("dist");
const entries = [
  "assets",
  "apps-script",
  "projects",
  "index.html",
  "script.js",
  "styles.css",
  "README.md",
  "package.json",
  "favicon.ico",
  "favicon-16x16.png",
  "favicon-32x32.png",
  "apple-touch-icon.png",
  "android-chrome-192x192.png",
  "android-chrome-512x512.png",
  "og-image.png",
  "robots.txt",
  "sitemap.xml"
];

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
