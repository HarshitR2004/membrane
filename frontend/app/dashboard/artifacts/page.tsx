"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Artifact = {
  artifact_id: string;
  type: string;
  filename: string;
  visibility: string;
  timestamp: string;
};

export default function ArtifactsPage() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await apiFetch("/artifacts");
        setArtifacts(res.items || []);
      } catch (err: any) {
        setError(err.message || "Failed to load artifacts");
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
          <h1 className="text-4xl font-bold text-[var(--foreground)] mb-2 tracking-tight uppercase">Artifacts_Db</h1>
          <p className="font-mono text-sm text-[var(--secondary)]">DECENTRALIZED_STORE // STRUCTURED_PAYLOADS</p>
        </div>
        <div className="font-mono text-xs text-[var(--primary)] animate-pulse">
          [{artifacts.length} RECORDS FOUND]
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
      ) : artifacts.length === 0 ? (
        <div className="p-12 text-center font-mono text-[var(--secondary)] border border-dashed border-[var(--border)]">
          // NO_RECORDS_FOUND
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {artifacts.map((art, index) => (
            <div 
              key={art.artifact_id} 
              className="brutalist-card p-6 flex flex-col justify-between animate-slide-up transition-colors hover:border-[var(--primary)] group"
              style={{ animationDelay: `${(index % 10) * 100}ms` }}
            >
              <div>
                <div className="flex justify-between items-start mb-4 border-b border-[var(--border)] pb-4 group-hover:border-[var(--primary)] transition-colors">
                  <div>
                    <div className="font-mono text-[10px] text-[var(--secondary)] mb-1 uppercase tracking-widest">RECORD_ID</div>
                    <div className="font-mono text-sm text-[var(--primary)] truncate max-w-[200px]" title={art.artifact_id}>{(art.artifact_id || "UNKNOWN").split("-")[0]}...</div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-[10px] text-[var(--secondary)] mb-1 uppercase tracking-widest">TYPE</div>
                    <span className="text-[10px] font-mono border border-[var(--foreground)] text-[var(--foreground)] px-2 py-1 uppercase bg-[var(--border)]">
                      {art.type}
                    </span>
                  </div>
                </div>
                
                <div className="font-mono text-[10px] text-[var(--secondary)] mb-2 uppercase tracking-widest">FILENAME</div>
                <div className="text-[var(--foreground)] font-mono text-sm leading-relaxed whitespace-pre-wrap break-words bg-[var(--background)] p-4 border border-[var(--border)] h-32 overflow-y-auto mb-4">
                  {art.filename || "// NO_FILENAME_PROVIDED"}
                </div>
              </div>
              
              <div className="flex justify-between items-end border-t border-[var(--border)] pt-4">
                <div>
                  <div className="font-mono text-[10px] text-[var(--secondary)] mb-1 uppercase tracking-widest">VISIBILITY</div>
                  <div className={`font-mono text-xs uppercase ${art.visibility === 'private' ? 'text-[var(--secondary)]' : 'text-blue-400'}`}>
                    [{art.visibility}]
                  </div>
                </div>
                <div className="font-mono text-[10px] text-[var(--secondary)] uppercase">
                  TS: {new Date(art.timestamp).toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
