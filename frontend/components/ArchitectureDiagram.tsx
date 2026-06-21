"use client";

import React from "react";

export function ArchitectureDiagram() {
  return (
    <div className="w-full max-w-4xl mx-auto mt-16 mb-16 relative h-[400px] z-10 animate-slide-up animate-delay-400">
      <svg className="w-full h-full" viewBox="0 0 800 400">
        <defs>
          <radialGradient id="membraneGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.4" />
            <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
          </radialGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>

        {/* Connections */}
        <g stroke="var(--border)" strokeWidth="1" fill="none">
          {/* Claude to Membrane */}
          <path d="M 400 80 L 400 160" className="opacity-50" />
          {/* Cursor to Membrane */}
          <path d="M 200 200 L 320 200" className="opacity-50" />
          {/* OpenAI to Membrane */}
          <path d="M 600 200 L 480 200" className="opacity-50" />
          {/* LangGraph to Membrane */}
          <path d="M 400 320 L 400 240" className="opacity-50" />
          
          {/* Membrane to Walrus */}
          <path d="M 450 240 L 550 320" className="opacity-30" strokeDasharray="4 4" />
          {/* Membrane to Sui */}
          <path d="M 350 240 L 250 320" className="opacity-30" strokeDasharray="4 4" />
        </g>

        {/* Animated Particles on Paths */}
        <g fill="var(--primary)">
          {/* Claude -> Membrane */}
          <circle r="3" className="animate-flow-down">
            <animateTransform attributeName="transform" type="translate" values="400 80; 400 160" dur="2s" repeatCount="indefinite" />
          </circle>
          {/* Cursor -> Membrane */}
          <circle r="3" className="animate-flow-right">
            <animateTransform attributeName="transform" type="translate" values="200 200; 320 200" dur="2.5s" repeatCount="indefinite" />
          </circle>
          {/* LangGraph -> Membrane */}
          <circle r="3" className="animate-flow-up">
            <animateTransform attributeName="transform" type="translate" values="400 320; 400 240" dur="3s" repeatCount="indefinite" />
          </circle>
          {/* OpenAI -> Membrane */}
          <circle r="3" className="animate-flow-left">
            <animateTransform attributeName="transform" type="translate" values="600 200; 480 200" dur="2.2s" repeatCount="indefinite" />
          </circle>
          
          {/* Membrane -> Walrus */}
          <circle r="2" fill="var(--secondary)">
            <animateTransform attributeName="transform" type="translate" values="430 220; 550 320" dur="1.5s" repeatCount="indefinite" />
          </circle>
          {/* Membrane -> Sui */}
          <circle r="2" fill="var(--secondary)">
            <animateTransform attributeName="transform" type="translate" values="370 220; 250 320" dur="1.8s" repeatCount="indefinite" />
          </circle>
        </g>

        {/* Nodes */}
        <g className="cursor-pointer group">
          <circle cx="400" cy="80" r="16" fill="var(--background)" stroke="white" strokeWidth="2" className="group-hover:scale-110 transition-transform origin-[400px_80px]" filter="url(#glow)" />
          <text x="400" y="50" fill="white" fontSize="12" fontFamily="var(--font-mono)" textAnchor="middle" className="uppercase tracking-widest opacity-80 group-hover:opacity-100 transition-opacity">Claude</text>
        </g>

        <g className="cursor-pointer group">
          <circle cx="200" cy="200" r="16" fill="var(--background)" stroke="white" strokeWidth="2" className="group-hover:scale-110 transition-transform origin-[200px_200px]" filter="url(#glow)" />
          <text x="160" y="204" fill="white" fontSize="12" fontFamily="var(--font-mono)" textAnchor="end" className="uppercase tracking-widest opacity-80 group-hover:opacity-100 transition-opacity">Cursor</text>
        </g>

        <g className="cursor-pointer group">
          <circle cx="600" cy="200" r="16" fill="var(--background)" stroke="white" strokeWidth="2" className="group-hover:scale-110 transition-transform origin-[600px_200px]" filter="url(#glow)" />
          <text x="640" y="204" fill="white" fontSize="12" fontFamily="var(--font-mono)" textAnchor="start" className="uppercase tracking-widest opacity-80 group-hover:opacity-100 transition-opacity">OpenAI</text>
        </g>

        <g className="cursor-pointer group">
          <circle cx="400" cy="320" r="16" fill="var(--background)" stroke="white" strokeWidth="2" className="group-hover:scale-110 transition-transform origin-[400px_320px]" filter="url(#glow)" />
          <text x="400" y="350" fill="white" fontSize="12" fontFamily="var(--font-mono)" textAnchor="middle" className="uppercase tracking-widest opacity-80 group-hover:opacity-100 transition-opacity">LangGraph</text>
        </g>

        {/* Infrastructure Nodes */}
        <g className="cursor-pointer group">
          <circle cx="250" cy="320" r="12" fill="var(--background)" stroke="var(--secondary)" strokeWidth="1" className="group-hover:scale-110 transition-transform origin-[250px_320px]" />
          <circle cx="250" cy="320" r="4" fill="var(--primary)" className="opacity-50 group-hover:opacity-100 transition-opacity" />
          <text x="210" y="324" fill="var(--secondary)" fontSize="10" fontFamily="var(--font-mono)" textAnchor="end" className="uppercase tracking-widest group-hover:text-white transition-colors">Sui</text>
        </g>

        <g className="cursor-pointer group">
          <circle cx="550" cy="320" r="12" fill="var(--background)" stroke="var(--secondary)" strokeWidth="1" className="group-hover:scale-110 transition-transform origin-[550px_320px]" />
          <circle cx="550" cy="320" r="4" fill="var(--primary)" className="opacity-50 group-hover:opacity-100 transition-opacity" />
          <text x="590" y="324" fill="var(--secondary)" fontSize="10" fontFamily="var(--font-mono)" textAnchor="start" className="uppercase tracking-widest group-hover:text-white transition-colors">Walrus</text>
        </g>

        {/* Central Membrane Node */}
        <g className="cursor-pointer group">
          <circle cx="400" cy="200" r="80" fill="url(#membraneGlow)" />
          <polygon points="400,160 440,200 400,240 360,200" fill="var(--background)" stroke="var(--primary)" strokeWidth="2" className="group-hover:scale-105 transition-transform origin-[400px_200px]" filter="url(#glow)" />
          <circle cx="400" cy="200" r="8" fill="var(--primary)" className="animate-pulse" />
          <text x="400" y="140" fill="var(--primary)" fontSize="14" fontWeight="bold" fontFamily="var(--font-sans)" textAnchor="middle" className="uppercase tracking-widest opacity-90 group-hover:opacity-100 transition-opacity">MEMBRANE</text>
        </g>
      </svg>
    </div>
  );
}
