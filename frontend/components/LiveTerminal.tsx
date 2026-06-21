"use client";

import React, { useEffect, useState } from "react";

const SEQUENCE = [
  { text: "> ingest_memory()", delay: 800, class: "text-[var(--primary)]" },
  { text: "", delay: 400 },
  { text: "Uploading artifact...", delay: 600, class: "text-[var(--secondary)]" },
  { text: "✓ Blob stored on Walrus", delay: 800, class: "text-[var(--foreground)]" },
  { text: "", delay: 300 },
  { text: "Generating proof...", delay: 600, class: "text-[var(--secondary)]" },
  { text: "✓ Digest created", delay: 700, class: "text-[var(--foreground)]" },
  { text: "", delay: 300 },
  { text: "Submitting transaction...", delay: 900, class: "text-[var(--secondary)]" },
  { text: "✓ Confirmed on Sui", delay: 800, class: "text-[var(--foreground)]" },
  { text: "", delay: 400 },
  { text: "Synchronizing agents...", delay: 1200, class: "text-[var(--secondary)]" },
  { text: "", delay: 200 },
  { text: "Claude        ✓", delay: 300, class: "text-[var(--primary)]" },
  { text: "Cursor        ✓", delay: 300, class: "text-[var(--primary)]" },
  { text: "LangGraph     ✓", delay: 500, class: "text-[var(--primary)]" },
  { text: "", delay: 400 },
  { text: "STATUS: COMPLETE", delay: 3000, class: "text-[var(--primary)] font-bold" },
];

export function LiveTerminal() {
  const [lines, setLines] = useState<number>(0);

  useEffect(() => {
    let timeout: NodeJS.Timeout;
    let isMounted = true;

    const runSequence = async () => {
      setLines(0);
      for (let i = 0; i < SEQUENCE.length; i++) {
        if (!isMounted) return;
        await new Promise((resolve) => {
          timeout = setTimeout(resolve, SEQUENCE[i].delay);
        });
        if (!isMounted) return;
        setLines(i + 1);
      }
      
      // Wait before restarting
      timeout = setTimeout(() => {
        if (isMounted) runSequence();
      }, 5000);
    };

    runSequence();

    return () => {
      isMounted = false;
      clearTimeout(timeout);
    };
  }, []);

  return (
    <div className="w-full max-w-3xl mx-auto mt-20 mb-32 z-10 animate-slide-up animate-delay-500">
      <div className="brutalist-card bg-[#050505] overflow-hidden">
        {/* Terminal Header */}
        <div className="h-8 border-b border-[var(--border)] flex items-center px-4 gap-2 bg-[var(--card)]">
          <div className="w-2.5 h-2.5 rounded-full bg-[var(--accent)] opacity-80"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-[#FFD700] opacity-80"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-[var(--primary)] opacity-80"></div>
          <div className="flex-1 text-center font-mono text-[10px] text-[var(--secondary)] uppercase tracking-widest">
            system_log.sh
          </div>
        </div>
        
        {/* Terminal Body */}
        <div className="p-6 font-mono text-xs md:text-sm text-left h-[320px] overflow-hidden flex flex-col justify-start">
          {SEQUENCE.slice(0, lines).map((line, idx) => (
            <div key={idx} className={`min-h-[1.5rem] ${line.class || ""}`}>
              {line.text}
            </div>
          ))}
          {lines < SEQUENCE.length && (
            <div className="flex items-center min-h-[1.5rem]">
              <span className="w-2 h-4 bg-[var(--primary)] animate-blink"></span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
