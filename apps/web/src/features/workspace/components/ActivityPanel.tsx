import { useState } from "react";
import { NavLink } from "react-router-dom";
import type { Workspace } from "../types";
import { Icon } from "../../../shared/ui/Icon";
import { Panel } from "../../../shared/ui/Panel";
import { EmptyState } from "../../../shared/ui/EmptyState";

export function ActivityPanel({
  state,
  full = false,
}: {
  state: Workspace;
  full?: boolean;
}) {
  const [filter, setFilter] = useState("ALL");
  const events = state.events
    .filter((e) => filter === "ALL" || e.kind === filter)
    .slice(0, full ? 150 : 5);
  return (
    <Panel
      title={full ? "Session audit trail" : "Recent activity"}
      action={
        full ? (
          <a href="/api/audit/export" className="ax-button subtle" download>
            Export JSON ↓
          </a>
        ) : (
          <NavLink className="ax-text-link" to="/journal">
            View all <Icon name="arrow" size={14} />
          </NavLink>
        )
      }
    >
      {full && (
        <div className="ax-filters">
          {["ALL", "BUY", "SELL", "REJECTED", "DECISION", "CONTROL"].map(
            (f) => (
              <button
                key={f}
                className={filter === f ? "active" : ""}
                onClick={() => setFilter(f)}
              >
                {f === "ALL" ? "All events" : f.toLowerCase()}
              </button>
            ),
          )}
        </div>
      )}
      {!events.length && (
        <EmptyState
          title="No matching events"
          text="Events appear here as your paper session progresses."
        />
      )}
      <div className="ax-activity">
        {events.map((e) => (
          <div className="ax-event" key={e.seq}>
            <div
              className={`ax-event-icon ${e.kind === "REJECTED" ? "warn" : ""}`}
            >
              <Icon
                name={
                  e.kind === "BUY" || e.kind === "SELL"
                    ? "wallet"
                    : e.kind === "FUNDING"
                      ? "spark"
                      : "shield"
                }
                size={16}
              />
            </div>
            <div>
              <strong>{e.payload.message || e.kind}</strong>
              <span>
                Bar {e.tick} · {e.kind}
                {full && ` · ${e.hash.slice(0, 16)}…`}
              </span>
            </div>
            <span className="ax-event-seq">
              #{String(e.seq).padStart(3, "0")}
            </span>
          </div>
        ))}
      </div>
      {full && (
        <p className="ax-footnote">
          Showing the latest 150 events. Export includes the complete session
          hash chain. Local hashes detect accidental changes; they are not
          independently anchored attestations.
        </p>
      )}
    </Panel>
  );
}
