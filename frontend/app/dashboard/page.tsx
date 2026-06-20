"use client";

import { useEffect, useState } from "react";
import { apiFetch, getWallet } from "@/lib/api";

type Stats = { memories: number; artifacts: number; workflows: number; shared: number };
type Profile = { wallet: string; username: string | null; namespace: string };
type APIKey = { id: string; name: string; key_value: string | null; created_at: string; last_used: string; is_active: boolean };
type Config = { universal: any };

export default function DashboardOverview() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [keys, setKeys] = useState<APIKey[]>([]);
  const [configs, setConfigs] = useState<Config | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  const [claimUsername, setClaimUsername] = useState("");
  const [keyName, setKeyName] = useState("");
  const [loadingAction, setLoadingAction] = useState<"claim" | "key" | null>(null);
  const [configType, setConfigType] = useState<"SSE" | "STDIO">("SSE");
  const [error, setError] = useState("");
  const [copiedConfig, setCopiedConfig] = useState(false);

  const fetchData = async () => {
    try {
      const profileRes = await apiFetch("/profile");
      const [statsRes, keysRes, universalRes] = await Promise.all([
        apiFetch("/stats").catch(() => null),
        apiFetch("/keys").catch(() => []),
        apiFetch("/config/universal").catch(() => null),
      ]);
      setStats(statsRes);
      setProfile(profileRes);
      setKeys(keysRes.filter((k: APIKey) => k.name !== "Dashboard Session"));
      setConfigs({ universal: universalRes });
    } catch (e: any) {
      console.error("Fetch Data Error:", e);
      if (e.message?.includes("401") || e.message?.includes("Inactive") || e.message?.includes("Invalid")) {
        if (typeof window !== "undefined") {
          localStorage.removeItem("membrane_api_key");
          localStorage.removeItem("membrane_wallet");
          window.location.href = "/";
        }
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleClaimId = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoadingAction("claim");
    setError("");
    try {
      await apiFetch("/profile/claim-id", {
        method: "POST",
        body: JSON.stringify({ wallet: getWallet(), username: claimUsername })
      });
      if (typeof window !== "undefined") window.dispatchEvent(new Event("profileUpdated"));
      await fetchData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleGenerateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoadingAction("key");
    try {
      await apiFetch("/keys", {
        method: "POST",
        body: JSON.stringify({ wallet: getWallet(), name: keyName })
      });
      setKeyName("");
      await fetchData();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleRotateKey = async (keyId: string) => {
    if (!confirm("CRITICAL: The old key will immediately stop working. Execute?")) return;
    try {
      await apiFetch("/keys/rotate", {
        method: "POST",
        body: JSON.stringify({ wallet: getWallet(), key_id: keyId })
      });
      await fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDeleteKey = async (keyId: string) => {
    if (!confirm("CRITICAL: This will permanently delete the key and revoke access. Execute?")) return;
    try {
      await apiFetch("/keys/delete", {
        method: "POST",
        body: JSON.stringify({ wallet: getWallet(), key_id: keyId })
      });
      await fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleCopyConfig = () => {
    if (configType === "SSE") {
      if (!configs?.universal) return;
      const filteredUniversal = { mcpServers: { [`membrane-${profile?.username || profile?.namespace || 'default'}`]: configs.universal.mcpServers[`membrane-${profile?.username || profile?.namespace || 'default'}`] } };
      navigator.clipboard.writeText(JSON.stringify(filteredUniversal, null, 2));
    } else {
      const stdioConfig = {
        mcpServers: {
          "membrane-local": {
            command: "python",
            args: ["-m", "membrane"],
            env: { MEMBRANE_API_KEY: "<YOUR_API_KEY>" }
          }
        }
      };
      navigator.clipboard.writeText(JSON.stringify(stdioConfig, null, 2));
    }
    setCopiedConfig(true);
    setTimeout(() => setCopiedConfig(false), 2000);
  };

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-10 animate-slide-up">
      <header className="mb-12 border-b border-[var(--border)] pb-6 flex items-end justify-between">
        <div>
          <h1 className="text-4xl font-bold text-[var(--foreground)] mb-2 tracking-tight">SYSTEM_OVERVIEW</h1>
          <p className="font-mono text-sm text-[var(--secondary)]">IDENTITY | ACCESS_KEYS | TELEMETRY</p>
        </div>
        <div className="font-mono text-xs text-[var(--primary)] animate-pulse">
          [CONNECTED]
        </div>
      </header>

      {/* Stats Row */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 animate-slide-up animate-delay-100">
          {[
            { label: 'MEMORIES', value: stats.memories },
            { label: 'ARTIFACTS', value: stats.artifacts },
            { label: 'WORKFLOWS', value: stats.workflows },
            { label: 'SHARED NODES', value: stats.shared }
          ].map((stat, i) => (
            <div key={stat.label} className="brutalist-card p-6 border-l-4 border-l-[var(--primary)] flex flex-col justify-between">
              <h3 className="text-xs font-mono font-bold text-[var(--secondary)] mb-4">{stat.label}</h3>
              <p className="stat-readout text-5xl text-[var(--foreground)]">{stat.value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
        {/* Identity & Keys Column */}
        <div className="space-y-10 animate-slide-up animate-delay-200">
          
          {/* Claim ID */}
          <div className="brutalist-card p-8">
            <h2 className="text-2xl font-bold text-[var(--foreground)] mb-6 uppercase tracking-tight">Namespace_ID</h2>
            {isLoading ? (
              <div className="font-mono text-sm text-[var(--secondary)] animate-pulse">LOADING_IDENTITY...</div>
            ) : profile?.username ? (
              <div className="p-4 bg-[var(--background)] border border-[var(--border)] flex items-center justify-between">
                <div>
                  <div className="font-mono text-xs text-[var(--secondary)] mb-1">ALLOCATED_NAMESPACE</div>
                  <div className="font-mono text-xl font-bold text-[var(--primary)]">@{profile.username}</div>
                </div>
                <div className="w-10 h-10 border border-[var(--primary)] flex items-center justify-center text-[var(--primary)]">
                  [V]
                </div>
              </div>
            ) : (
              <form onSubmit={handleClaimId} className="space-y-4">
                <p className="font-mono text-xs text-[var(--secondary)] mb-6 leading-relaxed">
                  // Claim a human-readable identifier to replace your raw wallet address.
                </p>
                {error && <p className="font-mono text-xs text-[var(--accent)] uppercase">{error}</p>}
                <div className="flex gap-4">
                  <input 
                    type="text" 
                    placeholder="E.G. ALICE" 
                    className="brutalist-input flex-1"
                    value={claimUsername}
                    onChange={(e) => setClaimUsername(e.target.value)}
                    required
                    pattern="[a-z0-9_-]{3,30}"
                  />
                  <button type="submit" className="brutalist-button-primary" disabled={loadingAction === "claim"}>
                    {loadingAction === "claim" ? "WAIT" : "CLAIM"}
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* API Keys */}
          <div className="brutalist-card p-8">
            <h2 className="text-2xl font-bold text-[var(--foreground)] mb-6 uppercase tracking-tight">Access_Tokens</h2>
            
            <form onSubmit={handleGenerateKey} className="flex gap-4 mb-8">
              <input 
                type="text" 
                placeholder="TOKEN_LABEL" 
                className="brutalist-input flex-1"
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
                required
              />
              <button type="submit" className="brutalist-button-primary" disabled={loadingAction === "key"}>
                GENERATE
              </button>
            </form>

            <div className="space-y-4">
              {isLoading ? (
                <div className="font-mono text-sm text-[var(--secondary)] animate-pulse">LOADING_TOKENS...</div>
              ) : (
                <>
                  {keys.map(key => (
                    <div key={key.id} className={`p-5 border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 transition-colors ${key.is_active ? 'bg-[var(--background)] border-[var(--border)]' : 'bg-[#110505] border-[var(--accent)] opacity-60'}`}>
                      <div className="w-full">
                        <div className="font-bold text-[var(--foreground)] text-lg flex items-center gap-3">
                          {key.name}
                          {!key.is_active && <span className="font-mono text-[10px] bg-[var(--accent)] text-white px-2 py-0.5">REVOKED</span>}
                        </div>
                        {key.key_value && key.is_active && (
                          <div className="font-mono text-xs text-[var(--primary)] mt-3 bg-black p-2 border border-[var(--primary)] break-all select-all">
                            {key.key_value}
                          </div>
                        )}
                        <div className="font-mono text-xs text-[var(--secondary)] mt-3">TS: {new Date(key.created_at).toLocaleDateString()}</div>
                      </div>
                      {key.is_active && (
                        <div className="flex gap-3 shrink-0 sm:ml-4 w-full sm:w-auto">
                          <button 
                            onClick={() => handleRotateKey(key.id)}
                            className="brutalist-button-secondary text-xs flex-1 sm:flex-none"
                          >
                            ROTATE
                          </button>
                          <button 
                            onClick={() => handleDeleteKey(key.id)}
                            className="text-xs font-mono font-bold border border-[var(--accent)] text-[var(--accent)] px-4 py-2 hover:bg-[var(--accent)] hover:text-white transition-colors flex-1 sm:flex-none cursor-pointer"
                          >
                            PURGE
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                  {keys.length === 0 && (
                    <div className="p-6 border border-dashed border-[var(--secondary)] text-center font-mono text-sm text-[var(--secondary)]">
                      // NO ACTIVE TOKENS DETECTED
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

        </div>

        {/* MCP Configs Column */}
        <div className="space-y-10 animate-slide-up animate-delay-300">
          <div className="brutalist-card p-8">
            <h2 className="text-2xl font-bold text-[var(--foreground)] mb-6 uppercase tracking-tight">MCP_Configuration</h2>
            <p className="font-mono text-xs text-[var(--secondary)] mb-8 leading-relaxed">
              // Inject this configuration manifest into your autonomous agent environments to establish a secure connection.
            </p>
            
            <div className="space-y-6">
              <div>
                <div className="flex items-center justify-between mb-4 border-b border-[var(--border)] pb-2">
                  <div className="flex gap-4">
                    <button 
                      onClick={() => setConfigType("SSE")}
                      className={`font-mono text-sm font-bold uppercase transition-colors ${configType === "SSE" ? "text-[var(--primary)]" : "text-[var(--secondary)] hover:text-[var(--foreground)]"}`}
                    >
                      [ UNIVERSAL (SSE) ]
                    </button>
                    <button 
                      onClick={() => setConfigType("STDIO")}
                      className={`font-mono text-sm font-bold uppercase transition-colors ${configType === "STDIO" ? "text-[var(--primary)]" : "text-[var(--secondary)] hover:text-[var(--foreground)]"}`}
                    >
                      [ LOCAL (STDIO) ]
                    </button>
                  </div>
                  <button 
                    onClick={handleCopyConfig}
                    className="font-mono text-xs font-bold text-[var(--primary)] hover:text-[var(--foreground)] transition-colors"
                  >
                    {copiedConfig ? "[ COPIED ]" : "[ COPY ]"}
                  </button>
                </div>
                
                {configType === "SSE" ? (
                  <div className="bg-black border border-[var(--border)] p-6 overflow-x-auto relative mb-8">
                    <pre className="font-mono text-sm text-[var(--primary)] leading-loose">
                      {configs?.universal ? JSON.stringify({ mcpServers: { [`membrane-${profile?.username || profile?.namespace || 'default'}`]: configs.universal.mcpServers[`membrane-${profile?.username || profile?.namespace || 'default'}`] } }, null, 2) : "LOADING_MANIFEST..."}
                    </pre>
                  </div>
                ) : (
                  <div className="bg-black border border-[var(--border)] p-6 overflow-x-auto relative mb-8">
                    <pre className="font-mono text-sm text-[var(--primary)] leading-loose">
{`{
  "mcpServers": {
    "membrane-local": {
      "command": "python",
      "args": [
        "-m",
        "membrane"
      ],
      "env": {
        "MEMBRANE_API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}`}
                    </pre>
                  </div>
                )}

              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
