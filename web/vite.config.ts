import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The add-on loads the UI with plain <script>/<link> tags from
// /_addons/<addon>/web/, so build one IIFE bundle with fixed file names
// straight into the add-on's src/web/ folder.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../src/web",
    emptyOutDir: true,
    cssCodeSplit: false,
    // Anki 24.04 to 25.02 ship Qt 6.6, whose web view is Chromium 112: the
    // oldest browser the AnkiWeb listing offers Stepwise to.
    target: "chrome112",
    rollupOptions: {
      input: "src/main.tsx",
      output: {
        format: "iife",
        entryFileNames: "app.js",
        assetFileNames: "app[extname]",
      },
    },
  },
  // `npm run dev` serves index.html with live reload; bridge calls are
  // proxied to tools/devserver.py, which runs the real Python code against
  // a copy of a collection.
  server: {
    port: 5173,
    proxy: { "/bridge": "http://127.0.0.1:5180" },
  },
});
