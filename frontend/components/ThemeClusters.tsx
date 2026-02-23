"use client";

import { Cluster } from "@/hooks/useReportStream";

interface Props {
  clusters: Cluster[];
}

const sentimentConfig = {
  positive: {
    label: "Positive",
    bg: "bg-green-50",
    border: "border-green-200",
    badge: "bg-green-100 text-green-700",
    dot: "bg-green-500",
  },
  negative: {
    label: "Negative",
    bg: "bg-red-50",
    border: "border-red-200",
    badge: "bg-red-100 text-red-700",
    dot: "bg-red-500",
  },
  mixed: {
    label: "Mixed",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    badge: "bg-yellow-100 text-yellow-700",
    dot: "bg-yellow-500",
  },
};

export default function ThemeClusters({ clusters }: Props) {
  const sorted = [...clusters].sort((a, b) => b.review_count - a.review_count);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {sorted.map((cluster) => {
        const config = sentimentConfig[cluster.sentiment];
        return (
          <div
            key={cluster.cluster_id}
            className={`rounded-xl border p-5 ${config.bg} ${config.border}`}
          >
            <div className="flex items-start justify-between mb-3">
              <h3 className="font-semibold text-slate-900">{cluster.theme}</h3>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${config.badge}`}>
                {config.label}
              </span>
            </div>

            <div className="flex items-center gap-1.5 mb-4">
              <div className={`w-2 h-2 rounded-full ${config.dot}`} />
              <span className="text-sm text-slate-600">
                {cluster.review_count} review{cluster.review_count !== 1 ? "s" : ""}
              </span>
            </div>

            {cluster.top_quotes.slice(0, 2).map((quote, i) => (
              <blockquote
                key={i}
                className="text-sm text-slate-700 italic border-l-2 border-slate-300 pl-3 mb-2 leading-relaxed"
              >
                &ldquo;{quote.length > 150 ? quote.slice(0, 147) + "..." : quote}&rdquo;
              </blockquote>
            ))}
          </div>
        );
      })}
    </div>
  );
}
