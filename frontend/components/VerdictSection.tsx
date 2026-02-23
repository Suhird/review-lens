"use client";

import { ReportData } from "@/hooks/useReportStream";

interface Props {
  report: ReportData;
}

export default function VerdictSection({ report }: Props) {
  const { executive_summary, who_should_buy, who_should_skip, verdict, overall_score } = report;

  const scoreDesc =
    overall_score >= 8
      ? { label: "Excellent", color: "text-green-600", bg: "bg-green-50 border-green-200" }
      : overall_score >= 6.5
      ? { label: "Good", color: "text-blue-600", bg: "bg-blue-50 border-blue-200" }
      : overall_score >= 5
      ? { label: "Average", color: "text-yellow-600", bg: "bg-yellow-50 border-yellow-200" }
      : { label: "Below Average", color: "text-red-600", bg: "bg-red-50 border-red-200" };

  const formatBullets = (text: string) => {
    return text.split("\n").filter((l) => l.trim()).map((line, i) => (
      <li key={i} className="flex items-start gap-2">
        <span className="mt-1 text-slate-400">•</span>
        <span>{line.replace(/^[•\-\*]\s*/, "")}</span>
      </li>
    ));
  };

  const summaryParagraphs = executive_summary
    .split(/\n\n+/)
    .filter((p) => p.trim().length > 0);

  return (
    <div className="space-y-6">
      {/* Executive summary */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">Executive Summary</h2>
        <div className="space-y-4">
          {summaryParagraphs.map((para, i) => (
            <p key={i} className="text-slate-700 leading-relaxed">
              {para.trim()}
            </p>
          ))}
        </div>
      </div>

      {/* Who should buy / skip */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-green-50 rounded-xl border border-green-200 p-6">
          <h3 className="font-semibold text-green-800 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Who Should Buy
          </h3>
          <ul className="space-y-2 text-sm text-green-900">
            {formatBullets(who_should_buy)}
          </ul>
        </div>

        <div className="bg-red-50 rounded-xl border border-red-200 p-6">
          <h3 className="font-semibold text-red-800 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Who Should Skip
          </h3>
          <ul className="space-y-2 text-sm text-red-900">
            {formatBullets(who_should_skip)}
          </ul>
        </div>
      </div>

      {/* Verdict callout */}
      <div className={`rounded-xl border p-6 ${scoreDesc.bg}`}>
        <div className="flex items-center gap-3 mb-3">
          <span className={`text-4xl font-black ${scoreDesc.color}`}>{overall_score}</span>
          <div>
            <div className={`text-lg font-bold ${scoreDesc.color}`}>{scoreDesc.label}</div>
            <div className="text-slate-500 text-sm">out of 10</div>
          </div>
        </div>
        <p className={`text-lg font-medium ${scoreDesc.color}`}>{verdict}</p>
      </div>
    </div>
  );
}
