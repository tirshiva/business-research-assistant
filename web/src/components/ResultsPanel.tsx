import type { Investigation } from "../types";

function asNumber(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function InsightBlock({
  title,
  items,
}: {
  title: string;
  items: Array<{ statement: string }>;
}) {
  return (
    <div className="panel">
      <h3>{title}</h3>
      {items.length ? (
        <ul className="insight-list">
          {items.map((item) => (
            <li key={item.statement}>{item.statement}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">None recorded.</p>
      )}
    </div>
  );
}

export function ResultsPanel({ investigation }: { investigation: Investigation }) {
  const dimensions = investigation.scores?.dimensions || [];
  return (
    <>
      <div className="panel">
        <h2>Results</h2>
        <div className="score-card">
          <div>
            <div className="muted">Opportunity score</div>
            <strong>
              {investigation.opportunity_score != null
                ? investigation.opportunity_score.toFixed(1)
                : "—"}
            </strong>
            <div>/ 10</div>
          </div>
          <div>
            <p>
              <b>Recommendation:</b> {investigation.recommendation || "Pending"}
            </p>
            <p>
              <b>Confidence:</b>{" "}
              {investigation.confidence != null
                ? `${Math.round(investigation.confidence * 100)}%`
                : "—"}
            </p>
            <p className="muted">{investigation.query}</p>
          </div>
        </div>
        <h3>Dimension scores</h3>
        <div className="dimensions">
          {dimensions.length ? (
            dimensions.map((item) => {
              const name = String(item.dimension || "dimension");
              const score = asNumber(item.score) ?? 0;
              const missing = Boolean(item.missing);
              return (
                <div className="dim" key={name}>
                  <span>{name.replaceAll("_", " ")}</span>
                  <div className="bar">
                    <span style={{ width: `${missing ? 0 : score * 10}%` }} />
                  </div>
                  <span>{missing ? "n/a" : score.toFixed(1)}</span>
                </div>
              );
            })
          ) : (
            <p className="muted">Scores are not available yet.</p>
          )}
        </div>
      </div>
      <InsightBlock
        title="Opportunities"
        items={investigation.insights?.opportunities || []}
      />
      <InsightBlock title="Risks" items={investigation.insights?.risks || []} />
      <InsightBlock
        title="Unknowns"
        items={investigation.insights?.unknowns || []}
      />
    </>
  );
}
