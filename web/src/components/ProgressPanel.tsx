import type { AgentProgress, LifecycleStatus } from "../types";

const STAGES: LifecycleStatus[] = [
  "CREATED",
  "PLANNING",
  "RESEARCHING",
  "VALIDATING",
  "ANALYZING",
  "REVIEWING",
  "COMPLETED",
];

function pillClass(stage: LifecycleStatus, current: LifecycleStatus): string {
  const currentIndex = STAGES.indexOf(current === "FAILED" ? "REVIEWING" : current);
  const index = STAGES.indexOf(stage);
  if (current === "FAILED" && stage === "COMPLETED") {
    return "pill";
  }
  if (stage === current) {
    return "pill active";
  }
  if (index >= 0 && index < currentIndex) {
    return "pill done";
  }
  return "pill";
}

type Props = {
  stage: LifecycleStatus;
  agents: AgentProgress;
  evidenceCount: number;
  researchIteration: number;
  error: string | null;
};

export function ProgressPanel({
  stage,
  agents,
  evidenceCount,
  researchIteration,
  error,
}: Props) {
  return (
    <div className="panel">
      <h2>Investigation progress</h2>
      <div className="stage-row">
        {STAGES.map((item) => (
          <span key={item} className={pillClass(item, stage)}>
            {item}
          </span>
        ))}
        {stage === "FAILED" ? <span className="pill active">FAILED</span> : null}
      </div>
      <div className="stats">
        <div className="stat">
          <span className="muted">Current stage</span>
          <b>{stage}</b>
        </div>
        <div className="stat">
          <span className="muted">Evidence</span>
          <b>{evidenceCount}</b>
        </div>
        <div className="stat">
          <span className="muted">Research iteration</span>
          <b>{researchIteration}</b>
        </div>
        <div className="stat">
          <span className="muted">Agents running</span>
          <b>{agents.running.length}</b>
        </div>
      </div>
      <h3>Agents</h3>
      <p className="muted">Running</p>
      <div className="agent-list">
        {agents.running.length
          ? agents.running.map((name) => (
              <span key={name} className="agent running">
                {name}
              </span>
            ))
          : <span className="muted">None</span>}
      </div>
      <p className="muted">Completed</p>
      <div className="agent-list">
        {agents.completed.length
          ? agents.completed.map((name) => (
              <span key={name} className="agent completed">
                {name}
              </span>
            ))
          : <span className="muted">None yet</span>}
      </div>
      <p className="muted">Failed</p>
      <div className="agent-list">
        {agents.failed.length
          ? agents.failed.map((name) => (
              <span key={name} className="agent failed">
                {name}
              </span>
            ))
          : <span className="muted">None</span>}
      </div>
      {error ? <p className="error">{error}</p> : null}
    </div>
  );
}
