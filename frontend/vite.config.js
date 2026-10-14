import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFile } from "node:fs/promises";

function localDocs() {
  const docs = new URL("../docs/", import.meta.url);
  const pages = { "/kanban": "kanban.html", "/docs": "dashboard.html" };
  const redirects = {
    "/kanban/": "/kanban", "/docs/": "/docs",
    "/docs/kanban.html": "/kanban", "/docs/dashboard.html": "/docs",
  };
  return {
    name: "local-docs",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (req.method !== "GET" && req.method !== "HEAD") return next();
        const url = new URL(req.url || "/", "http://localhost");
        if (redirects[url.pathname]) {
          res.writeHead(301, { Location: redirects[url.pathname] + url.search });
          return res.end();
        }
        const file = pages[url.pathname];
        if (!file) return next();
        try {
          const html = await readFile(new URL(file, docs));
          res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-cache" });
          res.end(req.method === "HEAD" ? undefined : html);
        } catch (error) {
          res.writeHead(error.code === "ENOENT" ? 404 : 500, { "Content-Type": "text/plain; charset=utf-8" });
          res.end(req.method === "HEAD" ? undefined : "문서 HTML을 읽을 수 없습니다.");
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), localDocs()],
  server: {
    host: true,
    port: 5175,
    proxy: { "/api": "http://127.0.0.1:8011" },
  },
});
