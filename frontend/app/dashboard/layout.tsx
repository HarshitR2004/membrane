"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { getWallet, clearAuth, apiFetch } from "@/lib/api";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [wallet, setWallet] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    const w = getWallet();
    if (!w) {
      router.push("/");
    } else {
      setWallet(w);
      const fetchProfile = () => {
        apiFetch("/profile").then(res => {
          setUsername(res.username);
        }).catch(() => {
          // Handle error or invalid token
          clearAuth();
          router.push("/");
        });
      };
      
      fetchProfile();

      const handleProfileUpdated = () => fetchProfile();
      window.addEventListener("profileUpdated", handleProfileUpdated);
      return () => window.removeEventListener("profileUpdated", handleProfileUpdated);
    }
  }, [router]);

  const handleLogout = () => {
    clearAuth();
    router.push("/");
  };

  if (!wallet) return null;

  return (
    <div className="min-h-screen flex text-[var(--foreground)]">
      {/* Sidebar */}
      <aside className="w-64 border-r border-[var(--border)] bg-[var(--background)] flex flex-col z-20">
        <div className="h-20 flex items-center px-6 border-b border-[var(--border)]">
          <Link href="/" className="font-bold text-xl uppercase tracking-tighter text-[var(--foreground)] flex items-center hover:text-[var(--primary)] transition-colors">
            <span className="w-5 h-5 bg-[var(--primary)] mr-3 flex-shrink-0 animate-pulse"></span>
            Membrane
          </Link>
        </div>
        
        <div className="p-6 flex-1">
          <div className="text-[10px] font-mono font-bold text-[var(--secondary)] uppercase tracking-[0.2em] mb-6">
            // Navigation
          </div>
          <nav className="flex flex-col gap-2 font-mono text-sm">
            {[
              { path: '/dashboard', label: '[ SYSTEM_OVERVIEW ]' },
              { path: '/dashboard/memories', label: '[ MEMORIES ]' },
              { path: '/dashboard/artifacts', label: '[ ARTIFACTS ]' },
              { path: '/dashboard/workflows', label: '[ WORKFLOWS ]' },
              { path: '/dashboard/shared', label: '[ SHARED_NODES ]' },
            ].map(link => (
              <Link 
                key={link.path}
                href={link.path} 
                className={`px-4 py-3 border transition-all ${pathname === link.path ? 'bg-[var(--primary)] text-[var(--background)] border-[var(--primary)] shadow-[4px_4px_0_0_rgba(255,255,255,0.1)]' : 'border-transparent text-[var(--secondary)] hover:border-[var(--border)] hover:text-[var(--foreground)]'}`}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
        
        <div className="p-6 border-t border-[var(--border)] bg-[var(--card)]">
          <div className="flex flex-col gap-2 mb-6">
            <div className="text-xs font-mono font-bold text-[var(--primary)] uppercase truncate">
              {username ? `@${username}` : "UNCLAIMED_ID"}
            </div>
            <div className="text-[10px] text-[var(--secondary)] font-mono truncate">
              {wallet}
            </div>
          </div>
          <button 
            onClick={handleLogout}
            className="w-full text-xs font-mono font-bold border border-[var(--border)] text-[var(--foreground)] px-4 py-3 hover:bg-[var(--accent)] hover:border-[var(--accent)] hover:text-white transition-colors flex items-center justify-center gap-2 cursor-pointer uppercase tracking-wider"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            Terminate Session
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto relative z-10">
        {children}
      </main>
    </div>
  );
}
