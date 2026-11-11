"use client";

import React, { useRef } from "react";

interface LiquidGlassSceneProps {
  children: React.ReactNode;
  className?: string;
}

export const LiquidGlassScene: React.FC<LiquidGlassSceneProps> = ({
  children,
  className = "",
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {children}
    </div>
  );
};

interface LiquidGlassCardProps {
  children: React.ReactNode;
  className?: string;
  config?: Record<string, any>;
  onClick?: () => void;
  style?: React.CSSProperties;
}

export const LiquidGlassCard: React.FC<LiquidGlassCardProps> = ({
  children,
  className = "",
  config,
  onClick,
  style,
}) => {
  return (
    <div
      data-glass="true"
      data-config={config ? JSON.stringify(config) : undefined}
      onClick={onClick}
      style={style}
      className={`liquid-glass rounded-3xl ${className}`}
    >
      {children}
    </div>
  );
};
