"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useReportStream } from "@/hooks/useReportStream";
import ProgressStream from "@/components/ProgressStream";
import ScoreCard from "@/components/ScoreCard";
import RadarChart from "@/components/RadarChart";
import SentimentTimeline from "@/components/SentimentTimeline";
import RatingDistribution from "@/components/RatingDistribution";
import FeaturedReviews from "@/components/FeaturedReviews";
import ThemeClusters from "@/components/ThemeClusters";
import VerdictSection from "@/components/VerdictSection";

export default function ReportPage({
  params,
}: {
  params: { jobId: string };
}) {
  const { jobId } = params;
  const { report, progress, isComplete, isCancelled, error, cancel } = useReportStream(jobId);
  const router = useRouter();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    if (!report?.product_name || isRefreshing) return;
    
    setIsRefreshing(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: report.product_name, use_cache: false }),
      });

      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }

      const data = await res.json();
      router.push(`/report/${data.job_id}`);
    } catch (err) {
      console.error("Refresh failed:", err);
      setIsRefreshing(false);
    }
  };

  if (isCancelled) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center">
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-8">
          <div className="w-12 h-12 rounded-full bg-slate-200 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-slate-800 mb-2">Analysis stopped</h2>
          <p className="text-slate-600 mb-6">You stopped the analysis before it completed.</p>
          <a
            href="/"
            className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
          >
            New search
          </a>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center">
        <div className="bg-red-50 border border-red-200 rounded-xl p-8">
          <div className="text-4xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-red-800 mb-2">Analysis failed</h2>
          <p className="text-red-700">{error}</p>
          <a
            href="/"
            className="mt-6 inline-block px-6 py-3 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 transition-colors"
          >
            Try again
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          {report?.image_url && (
            <div className="flex-shrink-0 w-24 h-24 bg-white rounded-xl border border-slate-200 overflow-hidden flex items-center justify-center p-2 shadow-sm">
              <img 
                src={report.image_url} 
                alt={report.product_name || "Product image"} 
                className="max-w-full max-h-full object-contain"
              />
            </div>
          )}
          <div>
            <div className="mb-2">
              <a href="/" className="text-blue-600 hover:text-blue-700 text-sm font-medium inline-flex items-center">
                ← New search
              </a>
            </div>
            <h1 className="text-3xl font-bold text-slate-900">
              {report?.product_name || "Analyzing..."}
            </h1>
            {report && (
              <p className="text-slate-600 mt-1">
                {report.total_reviews_analyzed ?? 0} reviews analyzed from{" "}
                {(report.sources_used || []).join(", ")}
              </p>
            )}
          </div>
        </div>
        {/* Refresh Button Area */}
        {isComplete && report && (
          <div className="flex-shrink-0 mt-4 md:mt-0">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
            >
              <svg 
                className={`w-4 h-4 ${isRefreshing ? "animate-spin text-blue-500" : "text-slate-500"}`} 
                fill="none" 
                viewBox="0 0 24 24" 
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {isRefreshing ? "Refreshing..." : "Refresh Data"}
            </button>
          </div>
        )}
      </div>

      {/* Progress stream — shown while running */}
      {!isComplete && (
        <div className="space-y-3">
          <ProgressStream progress={progress} />
          <div className="flex justify-center">
            <button
              onClick={cancel}
              className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-red-200 text-red-600 rounded-lg text-sm font-medium hover:bg-red-50 hover:border-red-300 transition-colors shadow-sm"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              Stop analysis
            </button>
          </div>
        </div>
      )}

      {/* Results render as data arrives */}
      {report && (
        <>
          {/* Score card */}
          <ScoreCard report={report} />

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {(report.aspect_scores?.length ?? 0) > 0 && (
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h2 className="text-lg font-semibold text-slate-900 mb-4">Aspect Scores</h2>
                <RadarChart aspects={report.aspect_scores} />
              </div>
            )}
            {(report.drift_report?.monthly_sentiment?.length ?? 0) > 1 && (
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h2 className="text-lg font-semibold text-slate-900 mb-4">Sentiment Over Time</h2>
                <SentimentTimeline
                  monthly={report.drift_report.monthly_sentiment}
                  changePoints={report.drift_report.change_points}
                  trend={report.drift_report.trend}
                />
              </div>
            )}
          </div>

          {/* Rating distribution */}
          {report.rating_distribution && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-4">Rating Distribution</h2>
              <RatingDistribution distribution={report.rating_distribution} />
            </div>
          )}

          {/* Theme clusters */}
          {(report.clusters?.length ?? 0) > 0 && (
            <div>
              <h2 className="text-xl font-semibold text-slate-900 mb-4">Review Themes</h2>
              <ThemeClusters clusters={report.clusters} />
            </div>
          )}

          {/* Featured reviews */}
          {(report.featured_reviews?.length ?? 0) > 0 && (
            <div>
              <h2 className="text-xl font-semibold text-slate-900 mb-4">Featured Reviews</h2>
              <FeaturedReviews reviews={report.featured_reviews} />
            </div>
          )}

          {/* Verdict */}
          <VerdictSection report={report} />
        </>
      )}
    </div>
  );
}
