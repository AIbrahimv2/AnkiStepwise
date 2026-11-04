// Talks to the add-on's Python side (src/bridge.py).
//
// Inside Anki, `pycmd` appears once the QWebChannel connects, a moment
// after the page loads, so calls wait for it. During development the shim in
// index.html posts to tools/devserver.py instead.

import type { PushEvent } from "./types";

type Pycmd = (arg: string, cb?: (result: unknown) => void) => boolean;

declare global {
  interface Window {
    pycmd?: Pycmd;
    tagQueue?: { push: (event: PushEvent) => void };
  }
}

const ready: Promise<Pycmd> = new Promise((resolve) => {
  const check = () => (window.pycmd ? resolve(window.pycmd) : setTimeout(check, 15));
  check();
});

export interface Reply {
  toasts?: string[];
  error?: string;
}

let onToasts: (messages: string[]) => void = () => {};
let onError: (message: string) => void = () => {};

export function setReplyHandlers(handlers: {
  toasts: (messages: string[]) => void;
  error: (message: string) => void;
}): void {
  onToasts = handlers.toasts;
  onError = handlers.error;
}

/** Send a command and resolve with its reply. Toasts and errors carried by
 *  any reply are routed to the handlers above. */
export async function call<T extends object = Record<string, never>>(
  cmd: string,
  args: Record<string, unknown> = {},
): Promise<T & Reply> {
  const pycmd = await ready;
  return new Promise((resolve, reject) => {
    pycmd(JSON.stringify({ cmd, ...args }), (raw) => {
      const reply = (raw ?? {}) as T & Reply;
      if (reply.toasts?.length) onToasts(reply.toasts);
      if (reply.error) {
        onError(reply.error);
        reject(new Error(reply.error));
        return;
      }
      resolve(reply);
    });
  });
}
