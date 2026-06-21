"use client";

import React from "react";

export function MembraneCore() {
  return (
    <div className="relative w-64 h-64 mx-auto flex items-center justify-center animate-slide-up mb-8">
      {/* Outer Glow */}
      <div className="absolute inset-0 bg-[var(--primary)] opacity-10 blur-3xl rounded-full animate-pulse-glow"></div>
      
      {/* Orbiting Particles */}
      <div className="absolute inset-0 animate-spin-slow">
        <div className="absolute top-0 left-1/2 w-1 h-1 bg-white rounded-full blur-[1px]"></div>
        <div className="absolute bottom-1/4 right-0 w-1.5 h-1.5 bg-[var(--primary)] rounded-full blur-[1px]"></div>
        <div className="absolute bottom-0 left-1/4 w-1 h-1 bg-[var(--secondary)] rounded-full blur-[1px]"></div>
      </div>
      <div className="absolute inset-0 animate-spin-reverse-slow">
        <div className="absolute top-1/4 left-0 w-1.5 h-1.5 bg-[var(--primary)] rounded-full blur-[1px]"></div>
        <div className="absolute bottom-0 right-1/4 w-1 h-1 bg-white rounded-full blur-[1px]"></div>
      </div>

      {/* Core Hexagon Geometry */}
      <svg
        viewBox="0 0 100 100"
        className="w-32 h-32 text-[var(--primary)] animate-breathe"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      >
        <polygon points="50,5 90,25 90,75 50,95 10,75 10,25" className="opacity-40" />
        <polygon points="50,15 80,32 80,68 50,85 20,68 20,32" className="opacity-70" />
        <polygon points="50,25 70,38 70,62 50,75 30,62 30,38" fill="currentColor" className="opacity-90" />
      </svg>
      
      {/* Center Bright Spot */}
      <div className="absolute w-8 h-8 bg-white opacity-80 blur-lg rounded-full"></div>

      <div className="absolute -bottom-12 text-center w-full flex flex-col items-center">
        <div className="font-sans font-bold text-lg tracking-widest text-[var(--primary)] uppercase">
          Membrane Core
        </div>
        <div className="font-mono text-[10px] text-[var(--secondary)] uppercase tracking-[0.2em] mt-1">
          Persistent • Verifiable • Universal
        </div>
      </div>
    </div>
  );
}
