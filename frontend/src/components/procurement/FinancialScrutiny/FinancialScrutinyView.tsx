import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import type { ProcurementFinancialEvaluationResponse, BidderFinancialEvaluation, FinancialAnomalySignal } from '@/types/financial';
import { runFinancialEvaluation } from '@/services/api/financial';
import { ShieldCheck, Users, Clock, CheckCircle2, AlertTriangle, Calculator, DollarSign, XCircle, ChevronRight, Activity, FileText } from 'lucide-react';

interface FinancialScrutinyViewProps {
  data: ProcurementFinancialEvaluationResponse;
  procurementTitle: string;
  procurementOrganization?: string;
  onReloadRequested: () => void;
}

function AnomalyBadge({ anomaly }: { anomaly: FinancialAnomalySignal }) {
  const isWarning = anomaly.severity === 'WARNING' || anomaly.severity === 'CRITICAL';
  return (
    <div className={`flex items-start gap-2 p-3 rounded border text-xs leading-relaxed ${isWarning ? 'bg-amber-50 border-amber-200 text-amber-800' : 'bg-slate-50 border-slate-200 text-slate-700'}`}>
      <Activity className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${isWarning ? 'text-amber-500' : 'text-slate-400'}`} />
      <div>
        <span className="font-bold uppercase tracking-wider text-[10px] block mb-0.5">
          {anomaly.signal_type.replace(/_/g, ' ')}
        </span>
        {anomaly.description}
        {anomaly.requires_officer_review && (
          <span className="block mt-1 text-[10px] font-medium opacity-75">
            Requires review
          </span>
        )}
      </div>
    </div>
  );
}

function BidderCard({ bidder, onSelect }: { bidder: BidderFinancialEvaluation, onSelect: () => void }) {
  const isExcluded = bidder.technical_eligibility_status !== 'TECHNICALLY_ELIGIBLE' || !bidder.is_cover2_unlocked;
  
  if (isExcluded) {
    return (
      <div className="p-5 border border-slate-200 bg-slate-50 rounded-xl opacity-75 flex items-center justify-between">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">{bidder.bidder_name}</h4>
          <p className="text-xs text-slate-500 mt-1 flex items-center gap-1.5">
            <XCircle className="w-3.5 h-3.5 text-slate-400" />
            Excluded from financial evaluation
          </p>
          {bidder.exclusion_reason && (
            <p className="text-[11px] text-slate-400 mt-0.5">{bidder.exclusion_reason}</p>
          )}
        </div>
      </div>
    );
  }

  const formatCurrency = (val?: number) => {
    if (val === undefined || val === null) return '—';
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: bidder.currency }).format(val);
  };

  const isEvaluated = bidder.commercial_status === 'EVALUATED' || bidder.commercial_status === 'REVIEW_REQUIRED';

  return (
    <div className={`p-5 border rounded-xl bg-white ${bidder.is_l1 ? 'border-emerald-300 shadow-sm' : 'border-slate-200'}`}>
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-bold text-slate-900 text-base">{bidder.bidder_name}</h4>
            {bidder.is_l1 && (
              <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold uppercase tracking-wider rounded">
                L1
              </span>
            )}
            {bidder.rank && !bidder.is_l1 && (
              <span className="px-2 py-0.5 bg-slate-100 text-slate-600 text-[10px] font-bold uppercase tracking-wider rounded">
                L{bidder.rank}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 flex items-center gap-1.5">
            <FileText className="w-3.5 h-3.5" />
            Submission: {bidder.submission_id.slice(0, 8)}
          </p>
        </div>

        {isEvaluated ? (
          <div className="text-right">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Evaluated Amount</p>
            <p className={`text-xl font-bold font-mono tracking-tight ${bidder.is_l1 ? 'text-emerald-700' : 'text-slate-900'}`}>
              {formatCurrency(bidder.evaluated_amount)}
            </p>
            <button onClick={onSelect} className="text-xs text-blue-600 hover:text-blue-800 font-medium mt-1">
              View calculation breakdown →
            </button>
          </div>
        ) : (
          <div className="text-right text-slate-400 text-xs italic mt-1">
            Not yet evaluated
          </div>
        )}
      </div>

      {bidder.anomalies.length > 0 && (
        <div className="mt-4 space-y-2 border-t border-slate-100 pt-3">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Analytical Signals</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {bidder.anomalies.map((a, i) => <AnomalyBadge key={i} anomaly={a} />)}
          </div>
        </div>
      )}
    </div>
  );
}

export function FinancialScrutinyView({
  data,
  procurementTitle,
  procurementOrganization,
  onReloadRequested,
}: FinancialScrutinyViewProps) {
  const router = useRouter();
  const [isRunningEvaluation, setIsRunningEvaluation] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [evalStep, setEvalStep] = useState(0);
  const [selectedBidder, setSelectedBidder] = useState<BidderFinancialEvaluation | null>(null);
  const [isOfficerConfirmed, setIsOfficerConfirmed] = useState(false);

  const evaluationSteps = [
    "Reading commercial submissions...",
    "Normalizing quoted values...",
    "Applying tender evaluation rules...",
    "Analyzing commercial patterns..."
  ];

  const handleRunEvaluation = async () => {
    setIsRunningEvaluation(true);
    setEvalError(null);
    setEvalStep(0);

    // Presentation-only steps to communicate process
    for (let i = 0; i < evaluationSteps.length; i++) {
      setEvalStep(i);
      await new Promise(r => setTimeout(r, 600));
    }

    try {
      await runFinancialEvaluation(data.procurement_id);
      onReloadRequested();
    } catch (err: unknown) {
      setEvalError(err instanceof Error ? err.message : 'Failed to execute evaluation');
    } finally {
      setIsRunningEvaluation(false);
    }
  };

  const formattedDate = data.evaluated_at
    ? new Date(data.evaluated_at).toLocaleString([], {
        day: 'numeric', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    : null;

  const isFullyEvaluated = data.cover2_status === 'EVALUATED' || data.cover2_status === 'REVIEW_REQUIRED';

  return (
    <div className="min-h-screen bg-slate-50 text-[#0f172a] font-sans">
      <header className="sticky top-0 z-20 bg-white/95 backdrop-blur-md border-b border-slate-200 py-4 px-8">
        <div className="max-w-5xl mx-auto flex items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest bg-slate-100 text-slate-500 uppercase">
                {data.procurement_id.slice(0, 8)}
              </span>
              <span className="text-xs text-slate-400 font-medium tracking-wider uppercase">
                Financial Scrutiny · Cover 2
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
                isFullyEvaluated ? 'bg-blue-50 text-blue-600 border-blue-100' : 'bg-amber-50 text-amber-600 border-amber-100'
              }`}>
                {data.cover2_status.replace(/_/g, ' ')}
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#0f172a] truncate">
              {procurementTitle}
            </h1>
            <div className="flex flex-wrap items-center gap-4 mt-1">
              {procurementOrganization && (
                <span className="text-xs text-slate-500">{procurementOrganization}</span>
              )}
              {data.total_bidders > 0 && (
                <span className="flex items-center gap-1 text-xs text-slate-500">
                  <Users className="w-3 h-3" />
                  {data.eligible_bidders_count} of {data.total_bidders} eligible for financial review
                </span>
              )}
            </div>
          </div>
          <div className="shrink-0 hidden sm:flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 border border-slate-200 rounded-full">
            <ShieldCheck className="w-3.5 h-3.5 text-slate-500" />
            <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">
              Officer Decision Required
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 sm:px-8 py-10">
        
        {/* State: UNLOCKED but not evaluated */}
        {data.cover2_status === 'UNLOCKED' && !isFullyEvaluated && (
          <div className="bg-white border border-slate-200 p-8 rounded-xl text-center mb-8">
            <Calculator className="w-8 h-8 text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg font-bold text-slate-800 mb-2">Commercial Review is Open</h3>
            <p className="text-sm text-slate-500 mb-6 max-w-lg mx-auto leading-relaxed">
              Cover 2 envelopes have been unsealed. The next step is to evaluate the quoted prices, check arithmetic, apply normalization rules, and compute the final commercial ranking.
            </p>
            {isRunningEvaluation ? (
              <div className="bg-slate-50 border border-slate-100 rounded-lg p-4 inline-flex items-center gap-3 animate-pulse min-w-[300px] justify-center">
                <div className="w-4 h-4 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
                <span className="text-sm font-medium text-slate-600">{evaluationSteps[evalStep]}</span>
              </div>
            ) : (
              <button
                onClick={handleRunEvaluation}
                className="inline-flex items-center gap-2 px-6 py-3 bg-[#0f172a] hover:bg-[#1e293b] text-white text-sm font-medium rounded-full transition-colors shadow-sm"
              >
                Run Financial Evaluation
              </button>
            )}
            {evalError && (
              <div className="mt-4 text-sm text-red-600 flex items-center justify-center gap-1.5">
                <XCircle className="w-4 h-4" /> {evalError}
              </div>
            )}
          </div>
        )}

        {/* State: EVALUATED */}
        {isFullyEvaluated && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-slate-900 mb-1">Commercial Evaluation</h2>
                <p className="text-sm text-slate-500">Ranked by evaluated amount.</p>
              </div>
              {formattedDate && (
                <div className="text-right">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Evaluated</p>
                  <p className="text-xs text-slate-600 flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {formattedDate}</p>
                </div>
              )}
            </div>

            {/* Bidders List */}
            <div className="space-y-4">
              {data.bidder_evaluations
                .slice()
                .sort((a, b) => {
                  if (a.rank && b.rank) return a.rank - b.rank;
                  if (a.rank) return -1;
                  if (b.rank) return 1;
                  return 0;
                })
                .map((bidder) => (
                <BidderCard key={bidder.bidder_id} bidder={bidder} onSelect={() => setSelectedBidder(bidder)} />
              ))}
            </div>

            {/* Cross-bidder Anomalies */}
            {data.comparative_signals.length > 0 && (
              <div className="p-5 bg-white border border-slate-200 rounded-xl">
                <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-slate-400" /> Peer & Comparative Analysis
                </h3>
                <div className="space-y-2">
                  {data.comparative_signals.map((sig, idx) => (
                    <AnomalyBadge key={idx} anomaly={sig} />
                  ))}
                </div>
              </div>
            )}

            {/* Officer Confirmation & Proceed */}
            <div className="p-6 bg-white border-2 border-slate-200 rounded-xl mt-12">
              <h3 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-600" /> Officer Commercial Review
              </h3>
              <p className="text-sm text-slate-600 leading-relaxed mb-6">
                Commercial ranking calculated by Opal. Final procurement decision remains with the authorized officer. Anomaly signals must not alter ranking but require human determination.
              </p>
              
              <div className="flex items-center gap-4 border-t border-slate-100 pt-6">
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input 
                    type="checkbox" 
                    checked={isOfficerConfirmed}
                    onChange={(e) => setIsOfficerConfirmed(e.target.checked)}
                    className="w-4 h-4 text-[#0f172a] rounded border-slate-300 focus:ring-[#0f172a]" 
                  />
                  <span className="text-sm font-medium text-slate-700 group-hover:text-slate-900">
                    I have reviewed the evaluated amounts and analytical signals.
                  </span>
                </label>
                
                <button
                  disabled={!isOfficerConfirmed}
                  onClick={() => router.push(`/procurements/${data.procurement_id}/action-studio`)}
                  className="ml-auto inline-flex items-center gap-2 px-6 py-2.5 bg-[#0f172a] hover:bg-[#1e293b] text-white text-sm font-medium rounded-full transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Proceed to Action Studio <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Bidder Detail Modal / Overlay */}
      {selectedBidder && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-2xl rounded-2xl shadow-xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div>
                <h3 className="font-bold text-lg text-slate-900">{selectedBidder.bidder_name}</h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">Sub: {selectedBidder.submission_id}</p>
              </div>
              <button onClick={() => setSelectedBidder(null)} className="p-2 hover:bg-slate-200 rounded-full text-slate-500 transition-colors">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto space-y-6">
              <div>
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Evaluated Amount Breakdown</h4>
                <div className="bg-slate-50 rounded-lg p-4 font-mono text-sm space-y-2 border border-slate-100">
                  <div className="flex justify-between text-slate-600">
                    <span>Base / Subtotal</span>
                    <span>{new Intl.NumberFormat('en-IN', { style: 'currency', currency: selectedBidder.currency }).format(selectedBidder.subtotal || 0)}</span>
                  </div>
                  <div className="flex justify-between text-slate-600">
                    <span>+ Tax</span>
                    <span>{new Intl.NumberFormat('en-IN', { style: 'currency', currency: selectedBidder.currency }).format(selectedBidder.tax_amount || 0)}</span>
                  </div>
                  <div className="flex justify-between text-slate-600">
                    <span>+ Freight</span>
                    <span>{new Intl.NumberFormat('en-IN', { style: 'currency', currency: selectedBidder.currency }).format(selectedBidder.freight_amount || 0)}</span>
                  </div>
                  <div className="flex justify-between text-slate-600">
                    <span>− Discount</span>
                    <span>{new Intl.NumberFormat('en-IN', { style: 'currency', currency: selectedBidder.currency }).format(selectedBidder.discount_amount || 0)}</span>
                  </div>
                  <div className="border-t border-slate-200 pt-2 mt-2 flex justify-between font-bold text-slate-900 text-base">
                    <span>Evaluated Amount</span>
                    <span className={selectedBidder.is_l1 ? 'text-emerald-700' : ''}>
                      {new Intl.NumberFormat('en-IN', { style: 'currency', currency: selectedBidder.currency }).format(selectedBidder.evaluated_amount || 0)}
                    </span>
                  </div>
                </div>
              </div>

              {selectedBidder.line_items.length > 0 && (
                <div>
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Quoted Line Items</h4>
                  <div className="border border-slate-200 rounded-lg overflow-hidden text-xs">
                    <table className="w-full text-left border-collapse">
                      <thead className="bg-slate-50 border-b border-slate-200">
                        <tr>
                          <th className="px-3 py-2 font-semibold text-slate-600">Item</th>
                          <th className="px-3 py-2 font-semibold text-slate-600 text-right">Qty</th>
                          <th className="px-3 py-2 font-semibold text-slate-600 text-right">Rate</th>
                          <th className="px-3 py-2 font-semibold text-slate-600 text-right">Total</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 bg-white">
                        {selectedBidder.line_items.map((li, idx) => (
                          <tr key={idx}>
                            <td className="px-3 py-2 text-slate-700">{li.description}</td>
                            <td className="px-3 py-2 text-slate-600 text-right">{li.quantity} {li.unit}</td>
                            <td className="px-3 py-2 text-slate-600 text-right">{new Intl.NumberFormat('en-IN', { style: 'decimal' }).format(li.unit_rate)}</td>
                            <td className="px-3 py-2 text-slate-900 font-medium text-right">{new Intl.NumberFormat('en-IN', { style: 'decimal' }).format(li.total_price)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
            <div className="p-4 border-t border-slate-100 bg-slate-50 flex justify-end">
              <button onClick={() => setSelectedBidder(null)} className="px-4 py-2 bg-white border border-slate-300 hover:bg-slate-50 rounded-full text-sm font-medium text-slate-700">
                Close Detail
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
