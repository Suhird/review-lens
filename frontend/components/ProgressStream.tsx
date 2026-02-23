"use client";

import { ProgressEntry } from "@/hooks/useReportStream";

const STEPS = [
  "Query Enrichment",
  "Scraping Sources",
  "Cleaning Reviews",
  "Analyzing Sentiment",
  "Detecting Fake Reviews",
  "Analyzing Trends",
  "Clustering Themes",
  "Generating Report",
];

interface Props {
  progress: ProgressEntry[];
}

export default function ProgressStream({ progress }: Props) {
  const maxStep = progress.length > 0
    ? Math.max(...progress.map((p) => p.step))
    : 0;

  const latestMessage = progress.length > 0
    ? progress[progress.length - 1].message
    : "Starting...";

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-2 h-2 bg-blue-500 rounded-full pulse-dot"
              style={{ animationDelay: `${i * 0.3}s` }}
            />
          ))}
        </div>
        <span className="font-semibold text-slate-900">Analyzing reviews...</span>
      </div>

      {/* Step checklist */}
      <div className="space-y-2 mb-6">
        {STEPS.map((step, i) => {
          const stepNum = i + 1;
          const isDone = maxStep > stepNum;
          const isActive = maxStep === stepNum;
          const isPending = maxStep < stepNum;

          return (
            <div key={step} className="flex items-center gap-3">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${
                  isDone
                    ? "bg-green-500"
                    : isActive
                    ? "bg-blue-500"
                    : "bg-slate-200"
                }`}
              >
                {isDone ? (
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : isActive ? (
                  <svg className="w-3 h-3 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <span className="text-slate-400 text-xs">{stepNum}</span>
                )}
              </div>
              <span
                className={`text-sm ${
                  isDone
                    ? "text-slate-500 line-through"
                    : isActive
                    ? "text-slate-900 font-medium"
                    : "text-slate-400"
                }`}
              >
                {step}
              </span>
            </div>
          );
        })}
      </div>

      {/* Latest message */}
      <div className="bg-slate-50 rounded-lg p-3 text-sm text-slate-600">
        <span className="font-mono">{latestMessage}</span>
      </div>

      {/* Log */}
      {progress.length > 1 && (
        <details className="mt-4">
          <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-600">
            View full log ({progress.length} messages)
          </summary>
          <div className="mt-2 space-y-1 max-h-48 overflow-y-auto">
            {progress.map((p, i) => (
              <div key={i} className="text-xs text-slate-500 font-mono">
                [{p.step}/{p.total_steps}] {p.message}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
