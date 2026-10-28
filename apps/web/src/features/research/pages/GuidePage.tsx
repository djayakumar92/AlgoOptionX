import { useMemo, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "../guide.css";
import { Cockpit, MarketBar } from "../components/Cockpit";
import { useGuide } from "../hooks/useGuide";

// The content is not in this file on purpose. It is served from
// docs/guides/trading-research.md at the project root (see /api/guide), so the
// document you read in the app and the document on disk are the same one.
// Pasting the text into a component is how docs and apps drift apart.

interface Heading {
  id: string;
  text: string;
  level: number;
}

/** Stable, readable anchor for a heading -- also used by the contents list. */
function slug(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

/** Pull h2/h3 out of the raw markdown for the contents rail.
 *
 *  Read from the source text rather than from the rendered DOM: it runs once,
 *  needs no refs or effects, and cannot fall out of step with what is on
 *  screen. Fenced code blocks are skipped so a `##` inside one is not
 *  mistaken for a heading. */
function outline(markdown: string): Heading[] {
  const headings: Heading[] = [];
  let inFence = false;
  for (const line of markdown.split("\n")) {
    if (line.startsWith("```")) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;
    const match = /^(#{2,3})\s+(.*)$/.exec(line);
    if (match) {
      const text = match[2].trim();
      headings.push({ id: slug(text), text, level: match[1].length });
    }
  }
  return headings;
}

function headingWithAnchor(level: 2 | 3) {
  const Tag = level === 2 ? "h2" : "h3";
  return function HeadingRenderer({ children }: { children?: React.ReactNode }) {
    const text = String(children);
    return <Tag id={slug(text)}>{children}</Tag>;
  };
}

export default function GuidePage() {
  const { data, fetchError } = useGuide();
  const [query, setQuery] = useState("");

  const markdown = data?.markdown ?? "";
  const headings = useMemo(() => outline(markdown), [markdown]);

  // Filtering keeps whole sections rather than matching lines: a rule you
  // half-see is worse than one you cannot see, and every section here is a
  // complete instruction.
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle || !markdown) return markdown;

    const sections = markdown.split(/\n(?=## )/);
    const hits = sections.filter((section) => section.toLowerCase().includes(needle));
    return hits.length > 0 ? hits.join("\n") : "";
  }, [markdown, query]);

  return (
    <Cockpit>
      <MarketBar title="How to Trade">
        <input
          className="guide-search"
          type="search"
          placeholder="Search the guide…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search the guide"
        />
      </MarketBar>

      {fetchError && <div className="banner banner-error">Connection error: {fetchError}</div>}
      {!data && !fetchError && <div className="banner banner-info">Loading the guide…</div>}

      {data && (
        <div className="guide-layout">
          <article className="guide-body panel">
            {filtered ? (
              <Markdown
                remarkPlugins={[remarkGfm]}
                components={{ h2: headingWithAnchor(2), h3: headingWithAnchor(3) }}
              >
                {filtered}
              </Markdown>
            ) : (
              <p className="not-an-order">Nothing in the guide matches “{query}”.</p>
            )}
          </article>

          <nav className="guide-toc" aria-label="Guide contents">
            <span className="setup-field-label">On this page</span>
            {headings.map((h) => (
              <a
                key={h.id}
                href={`#${h.id}`}
                className={h.level === 3 ? "guide-toc-link is-sub" : "guide-toc-link"}
              >
                {h.text}
              </a>
            ))}
          </nav>
        </div>
      )}
    </Cockpit>
  );
}
