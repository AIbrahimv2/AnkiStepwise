import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

// Anki puts our <script> in <head>, before <div id="root"> exists.
function mount() {
  const el = document.getElementById("root");
  if (el) createRoot(el).render(<App />);
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
else mount();
