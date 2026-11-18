// An add-on's own Settings, drawn in the kit's window (py/page.py) as its
// Settings tab, beside What's new and About. The add-on builds a script
// that calls provideSettings(), and registers it with the kit:
//
//     kit.register("stepwise", settings_page={
//         "script": "web/settings.js", "style": "web/settings.css",
//         "bridge": settings_bridge})
//
// The panel's pycmd calls go to `bridge` (cmd "kit" stays the kit's). Put
// its buttons in <SettingsFoot> (settings.tsx), as the kit's own Settings
// do. Don't edit a vendored copy (web/src/kit/ in an add-on): change it in
// the kit and run its sync.py.

import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { KIT_SETTINGS_EVENT, type KitSettingsHost } from "./types";

export function provideSettings(id: string, render: (host: KitSettingsHost) => ReactNode): void {
  window.kitSettings = {
    id,
    mount(el, host) {
      const root = createRoot(el);
      root.render(render(host));
      // Not while the window's own page is rendering (React warns).
      return () => setTimeout(() => root.unmount());
    },
  };
  window.dispatchEvent(new Event(KIT_SETTINGS_EVENT));
}
