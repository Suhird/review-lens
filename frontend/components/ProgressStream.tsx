"use client";

import { ProgressEntry } from "@/hooks/useReportStream";
import { useEffect, useState } from "react";

const TASKS = [
  { id: "enrichment", label: "Query Enrichment" },
  { id: "scrape", label: "Scraping Data" },
  { id: "analysis", label: "Analyzing Sentiment & Trends" },
  { id: "synthesis", label: "Generating Report" },
];

interface Props {
  progress: ProgressEntry[];
}

export default function ProgressStream({ progress }: Props) {
  // Compute the latest state of each task
  const [taskStatus, setTaskStatus] = useState<Record<string, "pending" | "running" | "complete">>({
    enrichment: "pending",
    scrape: "pending",
    analysis: "pending",
    synthesis: "pending",
  });

  useEffect(() => {
    const newStatus: Record<string, "pending" | "running" | "complete"> = {
      enrichment: "pending",
      scrape: "pending",
      analysis: "pending",
      synthesis: "pending",
    };

    // Each progress event has {task, status, message} — apply in order
    progress.forEach((p) => {
      const task = p.task;
      const status = p.status as "running" | "complete";
      if (task && (task in newStatus) && status) {
        newStatus[task] = status;
      }
    });

    setTaskStatus(newStatus);
  }, [progress]);

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

      {/* Concurrent Task checklist */}
      <div className="space-y-4 mb-6">
        {TASKS.map(({ id, label }) => {
          const status = taskStatus[id];
          const isDone = status === "complete";
          const isActive = status === "running";

          return (
            <div key={id} className="flex items-center gap-3 bg-slate-50 p-3 rounded-lg border border-slate-100">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${
                  isDone
                    ? "bg-green-500 text-white"
                    : isActive
                    ? "bg-blue-500 text-white"
                    : "bg-slate-200 text-slate-400"
                }`}
              >
                {isDone ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : isActive ? (
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <div className="w-2 h-2 rounded-full bg-slate-300" />
                )}
              </div>
              <span
                className={`text-sm font-medium ${
                  isDone
                    ? "text-slate-500 line-through"
                    : isActive
                    ? "text-slate-900"
                    : "text-slate-400"
                }`}
              >
                {label}
              </span>
              {isActive && (
                <span className="ml-auto text-xs font-semibold text-blue-500 bg-blue-50 px-2 py-1 rounded">
                  In Progress
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Latest message */}
      <div className="bg-slate-50 rounded-lg p-3 text-sm text-slate-600 border mx-auto">
        <span className="font-mono">{latestMessage}</span>
      </div>

      {/* Log */}
      {progress.length > 1 && (
        <details className="mt-4">
          <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-600 font-medium">
            View full log events ({progress.length} messages)
          </summary>
          <div className="mt-4 p-3 bg-slate-900 rounded-lg space-y-1 max-h-48 overflow-y-auto font-mono text-xs">
            {progress.map((p, i) => (
              <div key={i} className="text-emerald-400">
                <span className="text-slate-500 mr-2">[{new Date().toLocaleTimeString()}]</span>
                {p.task && <span className="text-blue-400 mr-2">[{p.task}]</span>}
                {p.message}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
