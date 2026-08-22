import type { EvidenceItem } from "../types";

function formatTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function EvidenceExplorer({ items }: { items: EvidenceItem[] }) {
  return (
    <div className="panel">
      <h2>Evidence explorer</h2>
      <p className="muted">
        Expand a claim to trace evidence, source, and retrieval timestamp.
      </p>
      {items.length === 0 ? (
        <p className="muted">No evidence stored for this investigation.</p>
      ) : (
        items.map((item) => (
          <details key={item.evidence_id} className="evidence-card">
            <summary>{item.claim}</summary>
            <ol className="chain">
              <li>
                <b>Claim</b> — {item.claim}
              </li>
              <li>
                <b>Evidence</b> — {item.claim_kind} from {item.agent}
                {item.document_id
                  ? ` (document ${item.document_id}${
                      item.page != null ? `, page ${item.page}` : ""
                    })`
                  : ""}
              </li>
              <li>
                <b>Source</b> — {item.source_name || "unspecified"}
                {item.source_url ? (
                  <>
                    {" "}
                    <a href={item.source_url} rel="noreferrer" target="_blank">
                      {item.source_url}
                    </a>
                  </>
                ) : null}
              </li>
              <li>
                <b>Timestamp</b> — {formatTime(item.timestamp || item.retrieved_at)}
              </li>
            </ol>
          </details>
        ))
      )}
    </div>
  );
}
