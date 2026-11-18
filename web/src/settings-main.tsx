// Stepwise's Settings as a tab of the add-on kit's window, beside What's new
// and About. Built (vite.settings.config.ts) into src/web/settings.js and
// settings.css, which the kit puts in its window (kit.register's
// settings_page, in __init__.py); its calls go to src/settings_page.py.
// The window has the kit's theme and controls already, so this brings only
// Stepwise's own styles.

import { provideSettings } from "./kit/hosted";
import { SettingsPanel } from "./components/Settings";
import "./steps.css";

provideSettings("stepwise", (host) => <SettingsPanel onClose={host.close} />);
