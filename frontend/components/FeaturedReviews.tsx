"use client";

import { useState } from "react";
import { Review } from "@/hooks/useReportStream";

interface Props {
  reviews: Review[];
}

const sourceColors: Record<string, string> = {
  amazon: "bg-orange-100 text-orange-700",
  reddit: "bg-red-100 text-red-700",
  bestbuy: "bg-blue-100 text-blue-700",
  youtube: "bg-red-50 text-red-600",
};

function StarDisplay({ rating }: { rating: number | null }) {
  if (rating === null) return null;
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <svg
          key={i}
          className={`w-3.5 h-3.5 ${i < Math.round(rating) ? "text-yellow-400 fill-yellow-400" : "text-slate-200 fill-slate-200"}`}
          viewBox="0 0 20 20"
        >
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ))}
    </div>
  );
}

function ReviewCard({ review }: { review: Review }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = review.text.length > 250;
  const displayText = expanded || !isLong ? review.text : review.text.slice(0, 250) + "...";

  const sentimentBorder =
    review.rating !== null
      ? review.rating >= 4
        ? "border-l-4 border-l-green-400"
        : review.rating <= 2
        ? "border-l-4 border-l-red-400"
        : "border-l-4 border-l-yellow-400"
      : "border-l-4 border-l-slate-300";

  return (
    <div className={`bg-white rounded-xl border border-slate-200 p-5 ${sentimentBorder}`}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-medium ${
              sourceColors[review.source] || "bg-slate-100 text-slate-700"
            }`}
          >
            {review.source.charAt(0).toUpperCase() + review.source.slice(1)}
          </span>
          {review.verified_purchase && (
            <span className="flex items-center gap-1 text-green-700 text-xs font-medium">
              <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              Verified
            </span>
          )}
          <StarDisplay rating={review.rating} />
        </div>
        {review.helpful_votes > 0 && (
          <span className="text-xs text-slate-400 whitespace-nowrap">
            {review.helpful_votes} helpful
          </span>
        )}
      </div>

      <p className="text-slate-700 text-sm leading-relaxed">{displayText}</p>

      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 text-blue-600 text-xs hover:underline"
        >
          {expanded ? "Show less" : "Read more"}
        </button>
      )}

      <div className="mt-3 flex items-center gap-3 text-xs text-slate-400">
        {review.reviewer_id && <span>by {review.reviewer_id}</span>}
        {review.date && (
          <span>
            {new Date(review.date).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}
          </span>
        )}
        {review.fake_score > 0.5 && (
          <span className="text-amber-600 font-medium">Suspicious pattern</span>
        )}
      </div>
    </div>
  );
}

export default function FeaturedReviews({ reviews }: Props) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {reviews.map((r) => (
        <ReviewCard key={r.id} review={r} />
      ))}
    </div>
  );
}
