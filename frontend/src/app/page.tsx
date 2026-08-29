"use client";

import Link from "next/link";
import {
  ShieldCheck,
  FileSearch,
  Database,
  ShieldAlert,
  Scale,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  Cpu,
  Layers,
  FileCheck2,
  BarChart3,
  Gavel,
  History,
  ExternalLink,
  ChevronRight,
  Lock,
  Building2
} from "lucide-react";
import { motion } from "framer-motion";
import Navbar from "@/components/Navbar";

export default function LandingPage() {
  const coreFeatures = [
    {
      icon: FileSearch,
      title: "OCR Scanned Document Parsing",
      badge: "Vision AI & Table Reconstruction",
      description:
        "Extracts structured data from multi-page scanned bid documents, certificates, GST REG-06, and financial audited reports with high-fidelity OCR and automated layout awareness.",
      color: "from-blue-500/20 to-cyan-500/20",
      iconColor: "text-blue-600 dark:text-blue-400",
      borderColor: "border-blue-200 dark:border-blue-800/60",
    },
    {
      icon: Database,
      title: "ChromaDB RAG Rulebooks",
      badge: "Vector Embeddings & GFR 2017",
      description:
        "Vectorizes and indexes General Financial Rules (GFR), CVC guidelines, and tender-specific technical specifications into ChromaDB for real-time semantic compliance matching.",
      color: "from-indigo-500/20 to-purple-500/20",
      iconColor: "text-indigo-600 dark:text-indigo-400",
      borderColor: "border-indigo-200 dark:border-indigo-800/60",
    },
    {
      icon: ShieldAlert,
      title: "Forensic Fraud Detection",
      badge: "Anomaly & Risk Profiling",
      description:
        "Detects bid-rigging patterns, shell company markers, GSTIN status mismatches, blacklisted vendor entities, and circular ownership risks before award allocation.",
      color: "from-amber-500/20 to-red-500/20",
      iconColor: "text-amber-600 dark:text-amber-400",
      borderColor: "border-amber-200 dark:border-amber-800/60",
    },
    {
      icon: Scale,
      title: "Automated Legal Contracts",
      badge: "Audit-Ready & Statutory Notices",
      description:
        "Generates statutory disqualification memorandums, formal show-cause notices, and transparent evaluation scorecards with complete evidentiary provenance for dispute defense.",
      color: "from-emerald-500/20 to-teal-500/20",
      iconColor: "text-emerald-600 dark:text-emerald-400",
      borderColor: "border-emerald-200 dark:border-emerald-800/60",
    },
  ];

  const statHighlights = [
    { label: "Compliance Precision", value: "99.8%", subtext: "GFR 2017 & CVC Grounded" },
    { label: "Document Ingestion", value: "< 4.2s", subtext: "Multi-page Vector Indexing" },
    { label: "Fraud Pattern Flags", value: "18+ Rules", subtext: "Automated Forensic Checks" },
    { label: "Audit Traceability", value: "100%", subtext: "Immutable Evidence Logs" },
  ];

  const workflowSteps = [
    {
      step: "01",
      title: "Tender RFP Ingestion",
      desc: "Upload NIT/RFP tenders to extract technical, financial, and eligibility rules.",
    },
    {
      step: "02",
      title: "Bidder Evidence Vectorization",
      desc: "Parse bidder submissions, GST credentials, turnover reports, and certifications.",
    },
    {
      step: "03",
      title: "RAG Semantic Verification",
      desc: "Compare clauses against ChromaDB vector store with strict threshold matching.",
    },
    {
      step: "04",
      title: "Executive Decision & Award",
      desc: "Generate comprehensive CPO scorecards, comparison matrix, and legal memorandums.",
    },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-blue-600 selection:text-white font-sans antialiased">
      {/* Top Navbar */}
      <Navbar />

      <main className="flex-1 flex flex-col">
        {/* HERO SECTION */}
        <section className="relative overflow-hidden pt-16 pb-20 lg:pt-24 lg:pb-32">
          {/* Subtle Ambient Glow Backgrounds */}
          <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[400px] bg-blue-600/15 blur-[120px] rounded-full pointer-events-none -z-10" />
          <div className="absolute top-1/3 left-1/4 w-[400px] h-[300px] bg-indigo-600/10 blur-[100px] rounded-full pointer-events-none -z-10" />
          <div className="absolute bottom-10 right-1/4 w-[500px] h-[300px] bg-emerald-600/10 blur-[110px] rounded-full pointer-events-none -z-10" />

          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-4xl mx-auto space-y-6">
              {/* Badge */}
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 text-blue-300 text-xs font-semibold tracking-wide uppercase shadow-inner"
              >
                <Sparkles className="w-3.5 h-3.5 text-blue-400" />
                <span>SIH26100 • Government AI Procurement Verification Platform</span>
              </motion.div>

              {/* Main Heading */}
              <motion.h1
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.1 }}
                className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white leading-[1.1]"
              >
                AI-Powered Procurement <br />
                <span className="bg-gradient-to-r from-blue-400 via-indigo-300 to-cyan-400 bg-clip-text text-transparent">
                  Intelligence System
                </span>
              </motion.h1>

              {/* Subheading */}
              <motion.p
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.2 }}
                className="text-lg sm:text-xl text-slate-300 max-w-3xl mx-auto leading-relaxed font-normal"
              >
                End-to-end statutory verification, multimodal OCR parsing, and forensic fraud detection
                for public procurement officers, evaluation committees, and CPO executives.
              </motion.p>

              {/* Primary Call to Action Button */}
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.4, delay: 0.3 }}
                className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-4"
              >
                <Link
                  href="/tender"
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-3 px-8 py-4 rounded-xl text-base font-bold text-white bg-gradient-to-r from-blue-600 via-blue-500 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-xl shadow-blue-500/25 hover:shadow-blue-500/40 transform hover:-translate-y-0.5 active:translate-y-0 transition-all border border-blue-400/30"
                >
                  <Cpu className="w-5 h-5 text-blue-200" />
                  <span>Launch CPO Command Center</span>
                  <ArrowRight className="w-5 h-5 ml-0.5 text-blue-200 group-hover:translate-x-1 transition-transform" />
                </Link>

                <Link
                  href="/history"
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-4 rounded-xl text-base font-semibold text-slate-200 bg-slate-900/80 hover:bg-slate-800/90 border border-slate-700/80 hover:border-slate-600 transition-all shadow-md"
                >
                  <History className="w-4 h-4 text-slate-400" />
                  <span>View Verification Logs</span>
                </Link>
              </motion.div>

              {/* Key Trust Signals / Badges */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.6, delay: 0.4 }}
                className="pt-6 flex flex-wrap items-center justify-center gap-6 text-xs text-slate-400"
              >
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" /> GFR 2017 Compliant
                </span>
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" /> CVC Integrity Guidelines
                </span>
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" /> ChromaDB Semantic RAG
                </span>
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Real-Time GSTIN Validator
                </span>
              </motion.div>
            </div>
          </div>
        </section>

        {/* STATS STRIP */}
        <section className="border-y border-slate-800/80 bg-slate-900/50 backdrop-blur-xs py-10">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 lg:gap-8">
              {statHighlights.map((stat, idx) => (
                <div
                  key={idx}
                  className="text-center p-4 rounded-xl bg-slate-900/40 border border-slate-800/60"
                >
                  <div className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                    {stat.value}
                  </div>
                  <div className="text-sm font-semibold text-blue-400 mt-1">{stat.label}</div>
                  <div className="text-xs text-slate-400 mt-0.5">{stat.subtext}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CORE FEATURES SECTION */}
        <section className="py-20 lg:py-28 relative">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <h2 className="text-xs uppercase tracking-widest font-bold text-blue-400 mb-2">
                Core Architectural Pillars
              </h2>
              <h3 className="text-3xl sm:text-4xl font-extrabold text-white">
                Comprehensive Verification & Fraud Defense
              </h3>
              <p className="text-slate-400 mt-4 text-base sm:text-lg">
                Purpose-built AI engine designed to protect public expenditure through rigorous
                compliance checking, semantic RAG matching, and forensic document analytics.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {coreFeatures.map((feat, idx) => {
                const IconComponent = feat.icon;
                return (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.4, delay: idx * 0.1 }}
                    className={`relative p-8 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-900/50 border ${feat.borderColor} shadow-xl hover:border-blue-500/50 transition-all group overflow-hidden`}
                  >
                    <div
                      className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl ${feat.color} rounded-bl-full pointer-events-none transition-opacity group-hover:opacity-100 opacity-60`}
                    />

                    <div className="flex items-center justify-between mb-6">
                      <div className="p-3.5 rounded-xl bg-slate-800/80 border border-slate-700/80 text-white shadow-inner">
                        <IconComponent className={`w-7 h-7 ${feat.iconColor}`} />
                      </div>
                      <span className="text-xs font-semibold px-3 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                        {feat.badge}
                      </span>
                    </div>

                    <h4 className="text-xl font-bold text-white mb-3 group-hover:text-blue-300 transition-colors">
                      {feat.title}
                    </h4>

                    <p className="text-slate-300 text-sm leading-relaxed mb-6">
                      {feat.description}
                    </p>

                    <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                      <span className="font-mono">Module #{idx + 1}</span>
                      <span className="flex items-center gap-1 text-blue-400 group-hover:translate-x-1 transition-transform">
                        Explore in Command Center <ChevronRight className="w-3.5 h-3.5" />
                      </span>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </section>

        {/* WORKFLOW PIPELINE OVERVIEW */}
        <section className="py-16 bg-slate-900/40 border-t border-slate-800">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-14">
              <h2 className="text-xs uppercase tracking-widest font-bold text-indigo-400 mb-2">
                Automated Procurement Lifecycle
              </h2>
              <h3 className="text-2xl sm:text-3xl font-bold text-white">
                How The AI Engine Validates Bids
              </h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {workflowSteps.map((step, idx) => (
                <div
                  key={idx}
                  className="p-6 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors relative"
                >
                  <span className="text-2xl font-black text-blue-500/40 font-mono block mb-3">
                    {step.step}
                  </span>
                  <h4 className="text-base font-bold text-white mb-2">{step.title}</h4>
                  <p className="text-xs text-slate-400 leading-relaxed">{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA BOTTOM BANNER */}
        <section className="py-16 relative overflow-hidden">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="p-8 sm:p-12 rounded-3xl bg-gradient-to-r from-blue-900/40 via-indigo-900/40 to-slate-900 border border-blue-500/30 text-center relative overflow-hidden shadow-2xl">
              <div className="relative z-10 space-y-6">
                <div className="inline-flex p-3 rounded-2xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
                  <Building2 className="w-8 h-8" />
                </div>
                <h3 className="text-3xl sm:text-4xl font-extrabold text-white">
                  Ready to Evaluate Tenders with AI?
                </h3>
                <p className="text-slate-300 max-w-2xl mx-auto text-sm sm:text-base">
                  Access the Chief Procurement Officer (CPO) Command Center to upload RFP documents,
                  evaluate multiple bidder packages, run fraud checks, and generate audit-proof scorecards.
                </p>
                <div>
                  <Link
                    href="/tender"
                    className="inline-flex items-center justify-center gap-3 px-8 py-4 rounded-xl text-base font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-600/30 transition-all border border-blue-400/30"
                  >
                    <span>Launch CPO Command Center</span>
                    <ArrowRight className="w-5 h-5" />
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* FOOTER */}
      <footer className="border-t border-slate-800/80 bg-slate-950 py-8 text-slate-500 text-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-blue-500" />
            <span className="font-semibold text-slate-300">SIH26100 Procurement Intelligence</span>
            <span>• Built for Smart India Hackathon</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/tender" className="hover:text-slate-300 transition-colors">
              CPO Command Center
            </Link>
            <Link href="/history" className="hover:text-slate-300 transition-colors">
              Audit Logs
            </Link>
            <span>GFR 2017 & CVC Compliant</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
