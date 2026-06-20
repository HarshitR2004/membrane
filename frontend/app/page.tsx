"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, setWallet, setApiKey, getApiKey, getWallet } from "@/lib/api";
import { ConnectModal, useCurrentAccount, useSignPersonalMessage } from "@mysten/dapp-kit";

export default function LandingPage() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();
  
  const currentAccount = useCurrentAccount();
  const { mutateAsync: signPersonalMessage } = useSignPersonalMessage();

  useEffect(() => {
    // If the wallet connects, immediately trigger the backend authentication flow
    if (currentAccount && !loading) {
      if (getApiKey() && getWallet() === currentAccount.address) {
        router.push("/dashboard");
        return;
      }
      handleAuthFlow(currentAccount.address);
    }
  }, [currentAccount, loading, router]);

  const handleAuthFlow = async (walletAddress: string) => {
    setLoading(true);
    setError("");

    try {
      // 1. Request cryptographic signature from the wallet
      const messageToSign = "Login to Membrane: " + Date.now();
      const encodedMessage = new TextEncoder().encode(messageToSign);
      
      const signatureResult = await signPersonalMessage({
        message: encodedMessage,
      });

      // 2. Connect Wallet to Backend
      const res = await apiFetch("/auth/connect", {
        method: "POST",
        body: JSON.stringify({
          wallet: walletAddress,
          signature: signatureResult.signature, // Use the real signature
          message: messageToSign,
        }),
      });

      setWallet(res.wallet);

      // 3. Automatically generate an API Key for dashboard use
      const keyRes = await apiFetch("/keys", {
        method: "POST",
        body: JSON.stringify({
          wallet: walletAddress,
          name: "Dashboard Session",
        }),
      });

      setApiKey(keyRes.key);

      // 4. Redirect to dashboard
      router.push("/dashboard");
    } catch (err: any) {
      console.error(err);
      setError(`ERR: ${err.message || "AUTHENTICATION_FAILED"}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8 text-center relative overflow-hidden">
      {/* Hero Section */}
      <div className="z-10 max-w-5xl mx-auto flex flex-col items-center">
        <div className="inline-flex items-center px-4 py-1 mb-10 border border-[var(--border)] bg-[var(--card)] animate-slide-up">
          <span className="w-2 h-2 bg-[var(--primary)] mr-3 animate-pulse"></span>
          <span className="text-xs font-mono uppercase tracking-widest text-[var(--secondary)]">SYS.STATUS: ONLINE [TESTNET]</span>
        </div>

        <h1 className="text-6xl md:text-8xl font-black uppercase tracking-tighter mb-8 text-[var(--foreground)] leading-[0.9] animate-slide-up animate-delay-100">
          Universal<br/>
          <span className="text-[var(--primary)]">Compute</span> Layer
        </h1>
        
        <p className="font-mono text-base md:text-lg text-[var(--secondary)] mb-12 max-w-2xl leading-relaxed animate-slide-up animate-delay-200">
          The decentralized, verifiable knowledge infrastructure for autonomous agents. 
          Built on Walrus and Sui for permanent cryptographic state.
        </p>

        <div className="animate-slide-up animate-delay-300 flex flex-col items-center gap-4">
          <ConnectModal
            trigger={
              <button disabled={loading} className="brutalist-button-primary text-xl px-12 py-5 disabled:opacity-50">
                {loading ? "AUTHENTICATING..." : "INITIALIZE_CONNECTION"}
              </button>
            }
            open={isModalOpen}
            onOpenChange={(isOpen) => setIsModalOpen(isOpen)}
          />
          {error && <p className="font-mono text-[var(--accent)] text-xs uppercase animate-pulse">{error}</p>}
        </div>
      </div>

      {/* Features Row */}
      <div className="z-10 grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl w-full mt-32 text-left animate-slide-up animate-delay-400">
        <div className="brutalist-card p-8">
          <div className="font-mono text-xs text-[var(--secondary)] mb-4 border-b border-[var(--border)] pb-2 uppercase tracking-widest">
            Module 01
          </div>
          <h3 className="text-2xl font-bold mb-4 text-[var(--primary)] uppercase tracking-tight">Verifiable State</h3>
          <p className="text-[var(--secondary)] font-mono text-sm leading-relaxed">
            Every operation is anchored to the Sui blockchain, yielding immutable cryptographic proof of origin and sequence.
          </p>
        </div>

        <div className="brutalist-card p-8">
          <div className="font-mono text-xs text-[var(--secondary)] mb-4 border-b border-[var(--border)] pb-2 uppercase tracking-widest">
            Module 02
          </div>
          <h3 className="text-2xl font-bold mb-4 text-[var(--primary)] uppercase tracking-tight">Decentralized Object Store</h3>
          <p className="text-[var(--secondary)] font-mono text-sm leading-relaxed">
            Artifacts are globally distributed across the Walrus storage network. Unstoppable access, infinite scale.
          </p>
        </div>

        <div className="brutalist-card p-8">
          <div className="font-mono text-xs text-[var(--secondary)] mb-4 border-b border-[var(--border)] pb-2 uppercase tracking-widest">
            Module 03
          </div>
          <h3 className="text-2xl font-bold mb-4 text-[var(--primary)] uppercase tracking-tight">Multi-Agent Protocol</h3>
          <p className="text-[var(--secondary)] font-mono text-sm leading-relaxed">
            Standardized MCP endpoints allow arbitrary autonomous entities to synchronize and orchestrate securely.
          </p>
        </div>
      </div>
    </div>
  );
}
