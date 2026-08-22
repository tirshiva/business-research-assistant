import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getEvidence, getInvestigation, getInvestigationStatus } from "../api";
import { EvidenceExplorer } from "../components/EvidenceExplorer";
import { ProgressPanel } from "../components/ProgressPanel";
import { ResultsPanel } from "../components/ResultsPanel";
import type { EvidenceItem, Investigation, InvestigationStatus } from "../types";

const TERMINAL = new Set(["COMPLETED", "FAILED"]);

export function InvestigationPage() {
  const { id = "" } = useParams();
  const [detail, setDetail] = useState<Investigation | null>(null);
  const [status, setStatus] = useState<InvestigationStatus | null>(null);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer = 0;

    async function refresh() {
      try {
        const [nextStatus, nextDetail] = await Promise.all([
          getInvestigationStatus(id),
          getInvestigation(id),
        ]);
        if (cancelled) {
          return;
        }
        setStatus(nextStatus);
        setDetail(nextDetail);
        if (
          nextDetail.evidence_count > 0 ||
          TERMINAL.has(nextStatus.status)
        ) {
          const bundle = await getEvidence(id);
          if (!cancelled) {
            setEvidence(bundle.items);
          }
        }
        if (!TERMINAL.has(nextStatus.status)) {
          timer = window.setTimeout(refresh, 1500);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Load failed");
        }
      }
    }

    void refresh();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [id]);

  if (error) {
    return (
      <section className="panel">
        <p className="error">{error}</p>
        <Link to="/">Start another investigation</Link>
      </section>
    );
  }

  if (!detail || !status) {
    return (
      <section className="panel">
        <p className="muted">Loading investigation…</p>
      </section>
    );
  }

  const done = TERMINAL.has(status.status);

  return (
    <section>
      <p className="muted">
        <Link to="/">New investigation</Link>
        {" · "}
        {detail.location || "Location pending"}
        {detail.business_type ? ` · ${detail.business_type}` : ""}
      </p>
      <ProgressPanel
        stage={status.stage}
        agents={status.agents}
        evidenceCount={status.evidence_count}
        researchIteration={status.research_iteration}
        error={status.error}
      />
      {done ? (
        <>
          <ResultsPanel investigation={detail} />
          <EvidenceExplorer items={evidence} />
        </>
      ) : (
        <p className="muted">
          Research is running. This page updates as agents finish.
        </p>
      )}
    </section>
  );
}
