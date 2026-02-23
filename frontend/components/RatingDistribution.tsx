"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Review } from "@/hooks/useReportStream";

interface Props {
  reviews: Review[];
  fakeIds: string[];
}

export default function RatingDistribution({ reviews, fakeIds }: Props) {
  const fakeSet = new Set(fakeIds);

  const distribution: Record<number, { real: number; fake: number }> = {
    5: { real: 0, fake: 0 },
    4: { real: 0, fake: 0 },
    3: { real: 0, fake: 0 },
    2: { real: 0, fake: 0 },
    1: { real: 0, fake: 0 },
  };

  const ratedReviews = reviews.filter((r) => r.rating !== null);

  for (const r of ratedReviews) {
    const star = Math.round(r.rating!);
    if (star >= 1 && star <= 5) {
      if (fakeSet.has(r.id)) {
        distribution[star].fake++;
      } else {
        distribution[star].real++;
      }
    }
  }

  const total = ratedReviews.length;

  if (total === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-400 text-sm">
        No star ratings available
      </div>
    );
  }

  const data = [5, 4, 3, 2, 1].map((star) => ({
    star: `${star} ★`,
    real: distribution[star].real,
    fake: distribution[star].fake,
    total: distribution[star].real + distribution[star].fake,
    pct: Math.round(((distribution[star].real + distribution[star].fake) / total) * 100),
  }));

  return (
    <div>
      <div className="space-y-2">
        {data.map((d) => (
          <div key={d.star} className="flex items-center gap-3">
            <span className="text-sm text-slate-600 w-10 text-right">{d.star}</span>
            <div className="flex-1 h-6 bg-slate-100 rounded overflow-hidden flex">
              {d.real > 0 && (
                <div
                  className="h-full bg-blue-400 transition-all duration-500"
                  style={{ width: `${(d.real / total) * 100}%` }}
                  title={`${d.real} genuine`}
                />
              )}
              {d.fake > 0 && (
                <div
                  className="h-full bg-blue-200 transition-all duration-500"
                  style={{ width: `${(d.fake / total) * 100}%` }}
                  title={`${d.fake} flagged as suspicious`}
                />
              )}
            </div>
            <span className="text-sm text-slate-500 w-24 text-right">
              {d.total} ({d.pct}%)
            </span>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-4 mt-4 text-xs text-slate-500">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-blue-400 rounded" />
          Genuine reviews
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-blue-200 rounded" />
          Flagged suspicious
        </div>
      </div>
    </div>
  );
}
