import { useState } from "react";
import { FindingsTable } from "./components/FindingsTable";

export function App() {
  const [scanId, setScanId] = useState("");

  return (
    <main style={{ fontFamily: "system-ui", maxWidth: 1100, margin: "0 auto", padding: 16 }}>
      <h1>SecAudit</h1>
      <label>
        Scan ID{" "}
        <input
          value={scanId}
          onChange={(e) => setScanId(e.target.value.trim())}
          pattern="[a-f0-9]{32}"
          placeholder="32-char hex"
        />
      </label>
      {/^[a-f0-9]{32}$/.test(scanId) && <FindingsTable scanId={scanId} />}
    </main>
  );
}
