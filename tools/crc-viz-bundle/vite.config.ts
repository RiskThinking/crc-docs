import path from "node:path";
import { defineConfig, type Plugin } from "vite";
import tailwindcss from "@tailwindcss/vite";

// crc-viz imports the MapLibre worker as `?worker&url`. A single inline script
// has no file to point at, so embed the worker as a data: URL instead.
function inlineMaplibreWorker(): Plugin {
  const suffix = "?worker&url";
  return {
    name: "inline-maplibre-worker",
    enforce: "pre",
    async resolveId(id, importer) {
      if (!id.endsWith(suffix)) return null;
      const r = await this.resolve(id.slice(0, -suffix.length), importer, { skipSelf: true });
      return r ? "\0worker-data:" + r.id : null;
    },
    async load(id) {
      if (!id.startsWith("\0worker-data:")) return null;
      const file = id.slice("\0worker-data:".length);
      const fs = await import("node:fs");
      const code = fs.readFileSync(file, "utf8").replace(/export\s*\{[^}]*\}\s*;?/g, "");
      const url = "data:text/javascript;charset=utf-8," + encodeURIComponent(code);
      return `export default ${JSON.stringify(url)};`;
    },
  };
}

export default defineConfig({
  plugins: [inlineMaplibreWorker(), tailwindcss()],
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  esbuild: { jsx: "automatic" },
  build: {
    outDir: path.resolve(__dirname, "../../assets/crc-viz"),
    emptyOutDir: false,
    cssCodeSplit: false,
    lib: {
      entry: path.resolve(__dirname, "entry.tsx"),
      name: "CrcViz",
      formats: ["iife"],
      fileName: () => "crc-viz.js",
    },
    rollupOptions: {
      output: { assetFileNames: "crc-viz.[ext]" },
    },
  },
});
