"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";

interface MonthData {
  month: string;
  avg_sentiment: number;
}

interface Props {
  monthly: MonthData[];
  changePoints: string[];
  trend: "improving" | "declining" | "stable";
}

const trendColors = {
  improving: "#22c55e",
  declining: "#ef4444",
  stable: "#3b82f6",
};

export default function SentimentTimeline({ monthly, changePoints, trend }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || monthly.length < 2) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const margin = { top: 20, right: 20, bottom: 40, left: 50 };
    const width = svgRef.current.clientWidth || 500;
    const height = 220;
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const parseMonth = d3.timeParse("%Y-%m");
    const data = monthly
      .map((d) => ({ date: parseMonth(d.month)!, value: d.avg_sentiment }))
      .filter((d) => d.date != null)
      .sort((a, b) => a.date.getTime() - b.date.getTime());

    const x = d3
      .scaleTime()
      .domain(d3.extent(data, (d) => d.date) as [Date, Date])
      .range([0, innerWidth]);

    const y = d3.scaleLinear().domain([0, 1]).range([innerHeight, 0]);

    // Grid lines
    g.append("g")
      .attr("class", "grid")
      .call(
        d3
          .axisLeft(y)
          .tickSize(-innerWidth)
          .tickFormat(() => "")
      )
      .selectAll("line")
      .style("stroke", "#f1f5f9")
      .style("stroke-dasharray", "2,2");

    g.select(".grid .domain").remove();

    // Area fill
    const area = d3
      .area<{ date: Date; value: number }>()
      .x((d) => x(d.date))
      .y0(innerHeight)
      .y1((d) => y(d.value))
      .curve(d3.curveCatmullRom);

    g.append("path")
      .datum(data)
      .attr("fill", trendColors[trend])
      .attr("fill-opacity", 0.1)
      .attr("d", area);

    // Line
    const line = d3
      .line<{ date: Date; value: number }>()
      .x((d) => x(d.date))
      .y((d) => y(d.value))
      .curve(d3.curveCatmullRom);

    g.append("path")
      .datum(data)
      .attr("fill", "none")
      .attr("stroke", trendColors[trend])
      .attr("stroke-width", 2.5)
      .attr("d", line);

    // Dots
    g.selectAll("circle")
      .data(data)
      .enter()
      .append("circle")
      .attr("cx", (d) => x(d.date))
      .attr("cy", (d) => y(d.value))
      .attr("r", 4)
      .attr("fill", trendColors[trend])
      .attr("stroke", "white")
      .attr("stroke-width", 2);

    // Change point lines
    const cpParsed = changePoints
      .map((cp) => parseMonth(cp))
      .filter((d): d is Date => d != null);

    cpParsed.forEach((cp) => {
      if (cp >= (d3.min(data, (d) => d.date) as Date) && cp <= (d3.max(data, (d) => d.date) as Date)) {
        g.append("line")
          .attr("x1", x(cp))
          .attr("x2", x(cp))
          .attr("y1", 0)
          .attr("y2", innerHeight)
          .attr("stroke", "#f59e0b")
          .attr("stroke-width", 1.5)
          .attr("stroke-dasharray", "4,3");

        g.append("text")
          .attr("x", x(cp) + 4)
          .attr("y", 12)
          .attr("font-size", 10)
          .attr("fill", "#f59e0b")
          .text("change");
      }
    });

    // Axes
    g.append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .call(
        d3
          .axisBottom(x)
          .ticks(Math.min(data.length, 6))
          .tickFormat((d) => d3.timeFormat("%b %y")(d as Date))
      )
      .selectAll("text")
      .style("font-size", "11px")
      .style("fill", "#94a3b8");

    g.append("g")
      .call(
        d3
          .axisLeft(y)
          .ticks(5)
          .tickFormat((d) => `${Math.round((d as number) * 100)}%`)
      )
      .selectAll("text")
      .style("font-size", "11px")
      .style("fill", "#94a3b8");

  }, [monthly, changePoints, trend]);

  if (monthly.length < 2) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
        Not enough data for timeline
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span
          className={`text-sm font-medium px-2 py-0.5 rounded-full ${
            trend === "improving"
              ? "bg-green-100 text-green-700"
              : trend === "declining"
              ? "bg-red-100 text-red-700"
              : "bg-blue-100 text-blue-700"
          }`}
        >
          {trend.charAt(0).toUpperCase() + trend.slice(1)}
        </span>
        {changePoints.length > 0 && (
          <span className="text-xs text-amber-600">
            {changePoints.length} change point{changePoints.length !== 1 ? "s" : ""} detected
          </span>
        )}
      </div>
      <svg ref={svgRef} className="w-full" />
    </div>
  );
}
