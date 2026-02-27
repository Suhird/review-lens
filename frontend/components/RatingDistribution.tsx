"use client";

interface Props {
  distribution: Record<string, number>;
  fakeIds?: string[];
}

export default function RatingDistribution({ distribution }: Props) {
  const total = Object.values(distribution).reduce((s, n) => s + n, 0);

  if (total === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-400 text-sm">
        No star ratings available
      </div>
    );
  }

  return (
    <div>
      <div className="space-y-2">
        {[5, 4, 3, 2, 1].map((star) => {
          const count = distribution[String(star)] ?? 0;
          const pct = Math.round((count / total) * 100);
          return (
            <div key={star} className="flex items-center gap-3">
              <span className="text-sm text-slate-600 w-10 text-right">{star} ★</span>
              <div className="flex-1 h-6 bg-slate-100 rounded overflow-hidden">
                <div
                  className="h-full bg-blue-400 transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-sm text-slate-500 w-24 text-right">
                {count} ({pct}%)
              </span>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-slate-400 mt-3">{total} rated reviews</p>
    </div>
  );
}
