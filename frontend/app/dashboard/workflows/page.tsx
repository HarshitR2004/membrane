"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Workflow = {
  artifact_id: string;
  type: string;
  filename: string;
  visibility: string;
  timestamp: string;
};

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await apiFetch("/artifacts");
        const items = res.items || [];
        const filtered = items.filter((item: any) => item.type === "workflow");
        setWorkflows(filtered);
      } catch (err: any) {
        setError(err.message || "Failed to load workflows");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-10 animate-slide-up">
      <header className="mb-12 border-b border-[var(--border)] pb-6 flex items-end justify-between">
        <div>
          <h1 className="text-4xl font-bold text-[var(--foreground)] mb-2 tracking-tight uppercase">Workflows_Db</h1>
          <p className="font-mono text-sm text-[var(--secondary)]">EXECUTION_PLANS // AGENT_ORCHESTRATION</p>
        </div>
        <div className="font-mono text-xs text-[var(--primary)] animate-pulse">
          [{workflows.length} RECORDS FOUND]
        </div>
      </header>

      {error && (
        <div className="p-4 border border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--accent)] font-mono text-sm uppercase">
          ERROR: {error}
        </div>
      )}

      {loading ? (
        <div className="p-12 text-center font-mono text-[var(--secondary)] border border-dashed border-[var(--border)]">
          // FETCHING_RECORDS...
        </div>
      ) : workflows.length === 0 ? (
        <div className="p-12 text-center font-mono text-[var(--secondary)] border border-dashed border-[var(--border)]">
          // NO_RECORDS_FOUND
        </div>
      ) : (
        <div className="space-y-6">
          {workflows.map((wf, index) => (
            <div 
              key={wf.artifact_id} 
              className="brutalist-card p-6 flex flex-col md:flex-row gap-6 animate-slide-up transition-colors hover:border-[var(--primary)] group"
              style={{ animationDelay: `${(index % 10) * 100}ms` }}
            >
              <div className="md:w-64 shrink-0 border-b md:border-b-0 md:border-r border-[var(--border)] pb-4 md:pb-0 md:pr-6 group-hover:border-[var(--primary)] transition-colors">
                <div className="font-mono text-[10px] text-[var(--secondary)] mb-1 uppercase tracking-widest">WORKFLOW_ID</div>
                <div className="font-mono text-sm text-[var(--primary)] mb-4 truncate" title={wf.artifact_id}>{(wf.artifact_id || "UNKNOWN").split("-")[0]}...</div>
                
                <div className="font-mono text-[10px] text-[var(--secondary)] mb-1 uppercase tracking-widest">VISIBILITY</div>
                <div className={`font-mono text-xs uppercase ${wf.visibility === 'private' ? 'text-[var(--secondary)]' : 'text-blue-400'}`}>
                  [{wf.visibility}]
                </div>
              </div>
              
              <div className="flex-1">
                <div className="font-mono text-[10px] text-[var(--secondary)] mb-2 uppercase tracking-widest">WORKFLOW_SPEC</div>
                <div className="text-[var(--foreground)] font-mono text-sm leading-relaxed whitespace-pre-wrap break-words bg-[var(--background)] p-4 border border-[var(--border)]">
                  {wf.filename || "// NO_SPEC_PROVIDED"}
                </div>
              </div>
              
              <div className="md:w-48 shrink-0 flex flex-col justify-end">
                <div className="font-mono text-[10px] text-[var(--secondary)] mt-4 uppercase">
                  TS: {new Date(wf.timestamp).toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
