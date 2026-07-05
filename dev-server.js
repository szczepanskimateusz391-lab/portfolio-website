import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";

const args = new Map();
for (let i = 2; i < process.argv.length; i += 1) {
  const arg = process.argv[i];
  if (arg.startsWith("--")) {
    const key = arg.slice(2);
    const next = process.argv[i + 1];
    if (next && !next.startsWith("--")) {
      args.set(key, next);
      i += 1;
    } else {
      args.set(key, true);
    }
  }
}

const host = String(args.get("host") || "127.0.0.1");
const port = Number(args.get("port") || 5173);
const strictPort = args.has("strict-port");
const root = resolve(String(args.get("root") || "."));

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp"
};

function isInsideRoot(filePath) {
  const relative = normalize(filePath).replace(root, "");
  return filePath === root || (relative.startsWith(sep) && !relative.includes(`..${sep}`));
}

function resolveFile(urlPath) {
  const cleanPath = decodeURIComponent(urlPath.split("?")[0]);
  const requested = resolve(join(root, cleanPath));

  if (!isInsideRoot(requested)) return null;
  if (existsSync(requested) && statSync(requested).isFile()) return requested;
  if (existsSync(requested) && statSync(requested).isDirectory()) {
    const indexFile = join(requested, "index.html");
    if (existsSync(indexFile)) return indexFile;
  }

  const fallback = join(root, "index.html");
  return existsSync(fallback) ? fallback : null;
}

const server = createServer((request, response) => {
  const filePath = resolveFile(request.url || "/");

  if (!filePath) {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Not found");
    return;
  }

  response.writeHead(200, {
    "Cache-Control": "no-store",
    "Content-Type": mimeTypes[extname(filePath)] || "application/octet-stream"
  });
  createReadStream(filePath).pipe(response);
});

server.on("error", (error) => {
  if (error.code === "EADDRINUSE" && strictPort) {
    console.error(`Port ${port} is already in use. Stop the other server or change the port.`);
    process.exit(1);
  }
  throw error;
});

server.listen(port, host, () => {
  console.log(`Local server running at http://${host}:${port}/`);
});
