"use client";

import { ReportData } from "@/hooks/useReportStream";

interface Props {
  report: ReportData;
}

const riskColors = {
  low: "bg-green-100 text-green-700 border-green-200",
  medium: "bg-yellow-100 text-yellow-700 border-yellow-200",
  high: "bg-red-100 text-red-700 border-red-200",
};

const sourceColors: Record<string, string> = {
  amazon: "bg-orange-100 text-orange-700",
  reddit: "bg-red-100 text-red-700",
  bestbuy: "bg-blue-100 text-blue-700",
  youtube: "bg-red-100 text-red-600",
};

function StarRating({ score }: { score: number }) {
  const fullStars = Math.floor((score / 10) * 5);
  const hasHalf = (score / 10) * 5 - fullStars >= 0.5;

  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <svg
          key={i}
          className={`w-5 h-5 ${
            i < fullStars
              ? "text-yellow-400 fill-yellow-400"
              : i === fullStars && hasHalf
              ? "text-yellow-400"
              : "text-slate-300 fill-slate-300"
          }`}
          viewBox="0 0 20 20"
        >
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ))}
    </div>
  );
}

export default function ScoreCard({ report }: Props) {
  const { 
    overall_score = 0, 
    sentiment_breakdown = {}, 
    sources_used = [], 
    fake_report = { risk_level: "low" as "low" | "medium" | "high", fake_percentage: 0, flagged_count: 0, total_reviews: 0, flagged_ids: [] }
  } = report;

  const scoreColor =
    overall_score >= 8
      ? "text-green-600"
      : overall_score >= 6
      ? "text-blue-600"
      : overall_score >= 4
      ? "text-yellow-600"
      : "text-red-600";

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 relative">
      {report.is_simulated && (
        <div className="absolute top-4 right-4 bg-purple-100 text-purple-700 border border-purple-200 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-sm">
          <div className="w-1.5 h-1.5 bg-purple-500 rounded-full animate-pulse" />
          Simulated Data
        </div>
      )}
      <div className="flex flex-wrap gap-8 items-start">
        {/* Score */}
        <div className="text-center">
          <div className={`text-7xl font-black ${scoreColor}`}>{overall_score}</div>
          <div className="text-slate-500 text-sm mt-1">out of 10</div>
          <div className="mt-2">
            <StarRating score={overall_score} />
          </div>
        </div>

        {/* Sentiment breakdown */}
        <div className="flex-1 min-w-48">
          <h3 className="text-sm font-semibold text-slate-700 mb-3 uppercase tracking-wide">
            Sentiment
          </h3>
          {(["positive", "neutral", "negative"] as const).map((s) => {
            const pct = sentiment_breakdown[s] ?? 0;
            return (
              <div key={s} className="mb-2">
                <div className="flex justify-between text-sm mb-1">
                  <span className="capitalize text-slate-600">{s}</span>
                  <span className="font-medium text-slate-900">{pct}%</span>
                </div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      s === "positive"
                        ? "bg-green-400"
                        : s === "negative"
                        ? "bg-red-400"
                        : "bg-slate-400"
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Meta */}
        <div className="space-y-4">
          {/* Sources */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2 uppercase tracking-wide">
              Sources
            </h3>
            <div className="flex flex-wrap gap-2">
              {sources_used.map((s) => (
                <span
                  key={s}
                  className={`px-3 py-1 rounded-full text-xs font-medium ${
                    sourceColors[s] || "bg-slate-100 text-slate-700"
                  }`}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </span>
              ))}
            </div>
          </div>

          {/* Fake review risk */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2 uppercase tracking-wide">
              Fake Review Risk
            </h3>
            <div
              className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-medium ${
                riskColors[fake_report.risk_level]
              }`}
            >
              <div
                className={`w-2 h-2 rounded-full ${
                  fake_report.risk_level === "low"
                    ? "bg-green-500"
                    : fake_report.risk_level === "medium"
                    ? "bg-yellow-500"
                    : "bg-red-500"
                }`}
              />
              {fake_report.risk_level.toUpperCase()} — {fake_report.fake_percentage}% flagged
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
