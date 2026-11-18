import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Stepwise's Settings, for the add-on kit's window (src/settings-main.tsx):
// a second IIFE bundle beside the window's app.js, built after it (so the
// folder isn't emptied again). The kit inlines both files in its window.
export default defineConfig({
  plugins: [react()],
  base: "./",
  publicDir: false,
  build: {
    outDir: "../src/web",
    emptyOutDir: false,
    cssCodeSplit: false,
    // As app.js: Anki 24.04's web view is Chromium 112.
    target: "chrome112",
    rollupOptions: {
      input: "src/settings-main.tsx",
      output: {
        format: "iife",
        entryFileNames: "settings.js",
        assetFileNames: "settings[extname]",
      },
    },
  },
});
