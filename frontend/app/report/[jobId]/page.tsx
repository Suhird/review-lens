"use client";

import { use } from "react";
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
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = use(params);
  const { report, progress, isComplete, error } = useReportStream(jobId);

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
      <div className="flex items-center justify-between">
        <div>
          <a href="/" className="text-blue-600 hover:text-blue-700 text-sm font-medium mb-2 inline-block">
            ← New search
          </a>
          <h1 className="text-3xl font-bold text-slate-900">
            {report?.product_name || "Analyzing..."}
          </h1>
          {report && (
            <p className="text-slate-600 mt-1">
              {report.total_reviews_analyzed} reviews analyzed from{" "}
              {report.sources_used.join(", ")}
            </p>
          )}
        </div>
      </div>

      {/* Progress stream — always shown while running */}
      {!isComplete && (
        <ProgressStream progress={progress} />
      )}

      {/* Results render as data arrives */}
      {report && (
        <>
          {/* Score card */}
          <ScoreCard report={report} />

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {report.aspect_scores.length > 0 && (
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h2 className="text-lg font-semibold text-slate-900 mb-4">Aspect Scores</h2>
                <RadarChart aspects={report.aspect_scores} />
              </div>
            )}
            {report.drift_report.monthly_sentiment.length > 1 && (
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
          {report.total_reviews_analyzed > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-4">Rating Distribution</h2>
              <RatingDistribution
                reviews={report.featured_reviews}
                fakeIds={report.fake_report.flagged_ids}
              />
            </div>
          )}

          {/* Theme clusters */}
          {report.clusters.length > 0 && (
            <div>
              <h2 className="text-xl font-semibold text-slate-900 mb-4">Review Themes</h2>
              <ThemeClusters clusters={report.clusters} />
            </div>
          )}

          {/* Featured reviews */}
          {report.featured_reviews.length > 0 && (
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
