"use client";

import React from "react";
import {
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  AlertOctagon,
  TrendingDown,
  Info,
  CheckCircle2,
  FileWarning,
} from "lucide-react";
import { motion } from "framer-motion";

export interface FraudData {
  trust_score?: number; // 0 to 100 or 0.0 to 1.0
  is_suspicious?: boolean;
  red_flags?: string[];
  collusion_risk_level?: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
  [key: string]: any;
}

interface FraudAnalyzerProps {
  fraudData?: FraudData | null;
  bidderName?: string;
}

export default function FraudAnalyzer({
  fraudData,
  bidderName,
}: FraudAnalyzerProps) {
  if (!fraudData) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 text-center">
        <Info className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        <p className="text-sm font-medium text-gray-600">
          No fraud risk analysis data available yet.
        </p>
      </div>
    );
  }

  // Normalize trust score to 0 - 100 percentage
  let rawScore = fraudData.trust_score ?? 85;
  if (rawScore <= 1 && rawScore >= 0) {
    rawScore = Math.round(rawScore * 100);
  }
  const trustScore = Math.min(100, Math.max(0, Math.round(rawScore)));

  const isSuspicious = fraudData.is_suspicious ?? (trustScore < 60);
  const redFlags = Array.isArray(fraudData.red_flags) ? fraudData.red_flags : [];
  const riskLevel = (
    fraudData.collusion_risk_level || (trustScore < 40 ? "HIGH" : trustScore < 70 ? "MEDIUM" : "LOW")
  ).toUpperCase();

  // Progress Bar & Badge Styling based on trust score
  const getScoreTheme = (score: number) => {
    if (score >= 80) {
      return {
        bar: "bg-emerald-500",
        badge: "bg-emerald-50 text-emerald-700 border-emerald-200",
        glow: "shadow-emerald-500/20",
        text: "text-emerald-600",
        label: "High Trust / Low Anomaly",
      };
    }
    if (score >= 55) {
      return {
        bar: "bg-amber-500",
        badge: "bg-amber-50 text-amber-700 border-amber-200",
        glow: "shadow-amber-500/20",
        text: "text-amber-600",
        label: "Moderate Trust / Needs Review",
      };
    }
    return {
      bar: "bg-rose-600",
      badge: "bg-rose-50 text-rose-700 border-rose-200",
      glow: "shadow-rose-500/20",
      text: "text-rose-600",
      label: "Low Trust / Forensic Flagged",
    };
  };

  const getRiskBadge = (level: string) => {
    switch (level) {
      case "HIGH":
      case "CRITICAL":
        return "bg-rose-100 text-rose-800 border-rose-300";
      case "MEDIUM":
        return "bg-amber-100 text-amber-800 border-amber-300";
      case "LOW":
      default:
        return "bg-emerald-100 text-emerald-800 border-emerald-300";
    }
  };

  const theme = getScoreTheme(trustScore);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden font-sans">
      {/* Forensic Header */}
      <div className="bg-slate-900 px-6 py-4 flex flex-wrap items-center justify-between gap-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div
            className={`w-9 h-9 rounded-lg flex items-center justify-center ${
              isSuspicious ? "bg-rose-500/20 text-rose-400" : "bg-emerald-500/20 text-emerald-400"
            }`}
          >
            {isSuspicious ? (
              <AlertOctagon className="w-5 h-5" />
            ) : (
              <ShieldCheck className="w-5 h-5" />
            )}
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-wide uppercase flex items-center gap-2">
              Forensic Fraud & Collusion Engine
              {isSuspicious && (
                <span className="px-2 py-0.5 text-[10px] font-extrabold bg-rose-600 text-white rounded tracking-wider animate-pulse">
                  SUSPICIOUS PATTERN
                </span>
              )}
            </h3>
            {bidderName && (
              <p className="text-xs text-slate-400 mt-0.5">
                Target Entity: <span className="text-slate-200 font-semibold">{bidderName}</span>
              </p>
            )}
          </div>
        </div>

        {/* Collusion Risk Badge */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">Collusion Risk:</span>
          <span
            className={`px-3 py-1 text-xs font-extrabold rounded-full border uppercase tracking-wider ${getRiskBadge(
              riskLevel
            )}`}
          >
            {riskLevel}
          </span>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Visual Trust Score Progress Section */}
        <div className="bg-gray-50/80 rounded-xl p-5 border border-gray-200 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-gray-500" />
              <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">
                Integrity & Trust Score
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-2xl font-black ${theme.text}`}>
                {trustScore}%
              </span>
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${theme.badge}`}
              >
                {theme.label}
              </span>
            </div>
          </div>

          {/* Progress Bar Container */}
          <div className="w-full bg-gray-200 rounded-full h-3.5 overflow-hidden p-0.5 shadow-inner">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${trustScore}%` }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              className={`h-full rounded-full ${theme.bar} ${theme.glow} shadow-sm`}
            />
          </div>

          <div className="flex justify-between text-[11px] text-gray-400 font-mono pt-1">
            <span>0% (Critical Risk)</span>
            <span>50% (Review Required)</span>
            <span>100% (Fully Compliant)</span>
          </div>
        </div>

        {/* Danger-Themed Alert Box: Red Flags Warnings */}
        {redFlags.length > 0 ? (
          <div className="bg-rose-50/90 border-2 border-rose-300 rounded-xl p-5 space-y-4 shadow-sm">
            <div className="flex items-center gap-2.5 text-rose-900 border-b border-rose-200 pb-3">
              <div className="p-1.5 bg-rose-200/80 rounded-md text-rose-700">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-extrabold text-sm tracking-tight text-rose-950">
                  Forensic Red Flags Detected ({redFlags.length})
                </h4>
                <p className="text-xs text-rose-700">
                  The automated vigilance engine flagged the following critical anomalies:
                </p>
              </div>
            </div>

            <ul className="space-y-2.5">
              {redFlags.map((flag, idx) => (
                <motion.li
                  key={idx}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="flex items-start gap-2.5 text-xs text-rose-900 bg-white/80 p-3 rounded-lg border border-rose-200/90 shadow-2xs"
                >
                  <FileWarning className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                  <span className="leading-relaxed font-medium">{flag}</span>
                </motion.li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="bg-emerald-50/80 border border-emerald-200 rounded-xl p-4 flex items-center gap-3 text-emerald-800 text-xs">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <div>
              <p className="font-bold">No High-Severity Red Flags</p>
              <p className="text-emerald-700 mt-0.5">
                Bidder evidence cleared baseline collusion and duplicate entity screening heuristics.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
