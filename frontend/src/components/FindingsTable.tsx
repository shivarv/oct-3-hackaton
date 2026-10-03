import { useQuery } from "@tanstack/react-query";
import { fetchFindings } from "../api/client";

/** Lists findings. All values render as text; never use dangerouslySetInnerHTML for evidence. */
export function FindingsTable({ scanId }: { scanId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["findings", scanId],
    queryFn: () => fetchFindings(scanId),
  });

  if (isLoading) return <p>Loading…</p>;
  if (error) return <p role="alert">{(error as Error).message}</p>;
  if (!data?.length) return <p>No findings.</p>;

  return (
    <table>
      <thead>
        <tr>
          <th>Severity</th><th>Title</th><th>CWE</th><th>Location</th><th>Agent</th>
        </tr>
      </thead>
      <tbody>
        {data.map((f) => (
          <tr key={f.id}>
            <td>{f.severity}</td>
            <td title={f.remediation}>{f.title}</td>
            <td>{f.cwe ?? "—"}</td>
            <td><code>{f.location ?? f.target}</code></td>
            <td>{f.agent}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
