import type {
  CreateInvestigationBody,
  EvidenceItem,
  Investigation,
  InvestigationStatus,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  const body = (await response.json().catch(() => ({}))) as {
    message?: string;
    code?: string;
  } & T;
  if (!response.ok) {
    throw new Error(body.message || `Request failed (${response.status})`);
  }
  return body as T;
}

export function createInvestigation(payload: CreateInvestigationBody) {
  return request<{ id: string; status: string }>("/investigations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getInvestigation(id: string) {
  return request<Investigation>(`/investigations/${id}`);
}

export function getInvestigationStatus(id: string) {
  return request<InvestigationStatus>(`/investigations/${id}/status`);
}

export function getEvidence(id: string) {
  return request<{ investigation_id: string; items: EvidenceItem[] }>(
    `/investigations/${id}/evidence`,
  );
}
