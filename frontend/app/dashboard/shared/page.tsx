"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type SharedNode = {
  id: string;
  sourceType: "MEMORY" | "ARTIFACT";
  contentOrSummary: string;
  visibility: string;
  created_at: string;
};

export default function SharedNodesPage() {
  const [nodes, setNodes] = useState<SharedNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [memRes, artRes] = await Promise.all([
          apiFetch("/memories"),
          apiFetch("/artifacts")
        ]);

        const memItems = memRes.items || [];
        const artItems = artRes.items || [];

        const sharedMems = memItems
          .filter((m: any) => m.visibility !== "private" || m.allowed_users?.length > 0 || m.allowed_agents?.length > 0)
          .map((m: any) => ({
            id: m.memory_id || "UNKNOWN",
            sourceType: "MEMORY" as const,
            contentOrSummary: m.content || `// PAYLOAD_ENCRYPTED_OR_STORED_REMOTELY\n// HASH: ${m.content_hash || "UNKNOWN"}`,
            visibility: m.visibility,
            created_at: m.timestamp
          }));

        const sharedArts = artItems
          .filter((a: any) => a.visibility !== "private" || a.allowed_users?.length > 0 || a.allowed_agents?.length > 0)
          .map((a: any) => ({
            id: a.artifact_id || "UNKNOWN",
            sourceType: "ARTIFACT" as const,
            contentOrSummary: a.filename,
            visibility: a.visibility,
            created_at: a.timestamp
          }));

        const combined = [...sharedMems, ...sharedArts].sort((a, b) => 
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );

        setNodes(combined);
      } catch (err: any) {
        setError(err.message || "Failed to load shared nodes");
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
          <h1 className="text-4xl font-bold text-[var(--foreground)] mb-2 tracking-tight uppercase">Shared_Nodes</h1>
          <p className="font-mono text-sm text-[var(--secondary)]">NETWORK_TOPOLOGY // EXPORTED_STATE</p>
        </div>
        <div className="font-mono text-xs text-blue-400 animate-pulse">
          [{nodes.length} EXPORTED NODES]
        </div>
      </header>

      {error && (
        <div className="p-4 border border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--accent)] font-mono text-sm uppercase">
          ERROR: {error}
        </div>
      )}

      {loading ? (
        <div className="p-12 text-center font-mono text-[var(--secondary)] border border-dashed border-[var(--border)]">
          // SCANNING_NETWORK...
        </div>
      ) : nodes.length === 0 ? (
        <div className="p-12 text-center font-mono text-[var(--secondary)] border border-dashed border-[var(--border)]">
          // NO_SHARED_NODES_DETECTED
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {nodes.map((node, index) => (
            <div 
              key={node.id} 
              className="brutalist-card p-6 flex flex-col justify-between animate-slide-up transition-colors hover:border-[var(--primary)] group"
              style={{ animationDelay: `${(index % 10) * 100}ms` }}
            >
              <div>
                <div className="flex justify-between items-start mb-4 border-b border-[var(--border)] pb-4 group-hover:border-[var(--primary)] transition-colors">
                  <div>
                    <div className="font-mono text-[10px] text-[var(--secondary)] mb-1 uppercase tracking-widest">NODE_ID</div>
                    <div className="font-mono text-sm text-blue-400 truncate max-w-[200px]" title={node.id}>{node.id.split("-")[0]}...</div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-[10px] text-[var(--secondary)] mb-1 uppercase tracking-widest">SOURCE</div>
                    <span className={`text-[10px] font-mono border px-2 py-1 uppercase ${node.sourceType === 'MEMORY' ? 'border-[var(--primary)] text-[var(--primary)] bg-[var(--primary)]/10' : 'border-[var(--foreground)] text-[var(--foreground)] bg-[var(--border)]'}`}>
                      {node.sourceType}
                    </span>
                  </div>
                </div>
                
                <div className="font-mono text-[10px] text-[var(--secondary)] mb-2 uppercase tracking-widest">DATA_PAYLOAD</div>
                <div className="text-[var(--foreground)] font-mono text-sm leading-relaxed whitespace-pre-wrap break-words bg-[var(--background)] p-4 border border-[var(--border)] h-32 overflow-y-auto mb-4">
                  {node.contentOrSummary || "// EMPTY_PAYLOAD"}
                </div>
              </div>
              
              <div className="flex justify-between items-end border-t border-[var(--border)] pt-4">
                <div>
                  <div className="font-mono text-[10px] text-[var(--secondary)] mb-1 uppercase tracking-widest">VISIBILITY</div>
                  <div className="font-mono text-xs uppercase text-blue-400">
                    [{node.visibility}]
                  </div>
                </div>
                <div className="font-mono text-[10px] text-[var(--secondary)] uppercase">
                  TS: {new Date(node.created_at).toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
