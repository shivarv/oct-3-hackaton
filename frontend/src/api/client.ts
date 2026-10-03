export type Severity = "info" | "low" | "medium" | "high" | "critical";

export interface Finding {
  id: string;
  scan_id: string;
  agent: string;
  title: string;
  severity: Severity;
  cwe: string | null;
  compliance: string[];
  target: string;
  location: string | null;
  evidence: string;
  remediation: string;
  created_at: string;
}

/** Fetch findings for a scan. Auth uses an HttpOnly session cookie; no tokens are kept in JS. */
export async function fetchFindings(scanId: string, severity?: Severity): Promise<Finding[]> {
  const params = new URLSearchParams();
  if (severity) params.set("severity", severity);
  const res = await fetch(`/api/scans/${encodeURIComponent(scanId)}/findings?${params}`, {
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error(`Failed to load findings (${res.status})`);
  return (await res.json()) as Finding[];
}
