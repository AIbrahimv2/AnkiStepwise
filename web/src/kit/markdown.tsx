// The bit of Markdown a changelog line uses: **bold**, `code` and
// [links](https://…), rendered as React nodes (never as HTML). Don't edit a
// vendored copy (web/src/kit/ in an add-on): change it in the kit and run
// its sync.py.

import type { ReactNode } from "react";

const TOKEN = /\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;

export function Inline(props: { text: string; onLink: (url: string) => void }) {
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of props.text.matchAll(TOKEN)) {
    const i = m.index ?? 0;
    if (i > last) out.push(props.text.slice(last, i));
    if (m[1] !== undefined) out.push(<b key={i}><Inline text={m[1]} onLink={props.onLink} /></b>);
    else if (m[2] !== undefined) out.push(<code key={i}>{m[2]}</code>);
    else {
      const url = m[4];
      out.push(
        <a
          key={i}
          href={url}
          onClick={(e) => {
            e.preventDefault();
            props.onLink(url);
          }}
        >
          {m[3]}
        </a>,
      );
    }
    last = i + m[0].length;
  }
  if (last < props.text.length) out.push(props.text.slice(last));
  return <>{out}</>;
}
