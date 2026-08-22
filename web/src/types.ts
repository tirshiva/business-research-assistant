export type LifecycleStatus =
  | "CREATED"
  | "PLANNING"
  | "RESEARCHING"
  | "VALIDATING"
  | "ANALYZING"
  | "REVIEWING"
  | "COMPLETED"
  | "FAILED";

export type AgentProgress = {
  running: string[];
  completed: string[];
  failed: string[];
  unavailable: string[];
};

export type InsightItem = {
  statement: string;
  evidence_ids: string[];
};

export type InsightsSummary = {
  observations: InsightItem[];
  opportunities: InsightItem[];
  risks: InsightItem[];
  unknowns: InsightItem[];
};

export type ScoreSummary = {
  overall_score: number | null;
  recommendation: string | null;
  dimensions: Array<Record<string, unknown>>;
};

export type Investigation = {
  id: string;
  query: string;
  status: LifecycleStatus;
  stage: LifecycleStatus;
  business_type: string | null;
  location: string | null;
  objective: string | null;
  target_customer: string | null;
  budget: string | null;
  plan: string[];
  tasks: Array<{
    task_type: string;
    status: string;
    findings_count: number;
    error: string | null;
  }>;
  agents: AgentProgress;
  evidence_count: number;
  research_iteration: number;
  opportunity_score: number | null;
  recommendation: string | null;
  confidence: number | null;
  scores: ScoreSummary | null;
  insights: InsightsSummary | null;
  critic: {
    status: string | null;
    confidence: number | null;
    issues: string[];
    required_research: string[];
  } | null;
  created_at: string;
  updated_at: string;
};

export type InvestigationStatus = {
  id: string;
  status: LifecycleStatus;
  stage: LifecycleStatus;
  agents: AgentProgress;
  evidence_count: number;
  research_iteration: number;
  created_at: string;
  updated_at: string;
  error: string | null;
};

export type EvidenceItem = {
  evidence_id: string;
  agent: string;
  claim: string;
  value: unknown;
  claim_kind: string;
  source_name: string | null;
  source_url: string | null;
  source_type: string | null;
  retrieved_at: string;
  timestamp: string;
  confidence: number;
  document_id: string | null;
  page: number | null;
};

export type CreateInvestigationBody = {
  research_question: string;
  business_type: string;
  location: string;
  target_customer: string;
  budget: string;
};
