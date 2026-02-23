"use client";

import {
  Radar,
  RadarChart as RechartsRadar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { AspectScore } from "@/hooks/useReportStream";

interface Props {
  aspects: AspectScore[];
}

const RADAR_ASPECTS = [
  "performance",
  "value for money",
  "build quality",
  "ease of use",
  "design",
  "customer support",
];

export default function RadarChart({ aspects }: Props) {
  const filtered = aspects.filter(
    (a) =>
      a.mention_count > 3 &&
      RADAR_ASPECTS.includes(a.aspect.toLowerCase())
  );

  if (filtered.length < 3) {
    // Show all aspects if not enough radar-specific ones
    const fallback = aspects.filter((a) => a.mention_count > 0).slice(0, 8);
    if (fallback.length < 2) {
      return (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
          Not enough aspect data for radar chart
        </div>
      );
    }
  }

  const chartData = (filtered.length >= 3 ? filtered : aspects.slice(0, 8)).map((a) => ({
    aspect: a.aspect
      .split(" ")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" "),
    score: Math.round(a.score * 100),
    fullMark: 100,
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RechartsRadar data={chartData} cx="50%" cy="50%" outerRadius="75%">
        <PolarGrid stroke="#e2e8f0" />
        <PolarAngleAxis
          dataKey="aspect"
          tick={{ fontSize: 11, fill: "#64748b" }}
        />
        <Radar
          name="Score"
          dataKey="score"
          stroke="#3b82f6"
          fill="#3b82f6"
          fillOpacity={0.2}
          strokeWidth={2}
        />
        <Tooltip
          formatter={(value: number) => [`${value}%`, "Score"]}
          contentStyle={{
            background: "white",
            border: "1px solid #e2e8f0",
            borderRadius: "8px",
          }}
        />
      </RechartsRadar>
    </ResponsiveContainer>
  );
}
