"use client";

import { useEffect, useRef, useState } from "react";

export interface ProgressEntry {
  message: string;
  step: number;
  total_steps: number;
  task?: string;
  status?: string;
}

export interface ReportData {
  product_name: string;
  image_url?: string;
  overall_score: number;
  total_reviews_analyzed: number;
  sources_used: string[];
  sentiment_breakdown: Record<string, number>;
  aspect_scores: AspectScore[];
  fake_report: FakeReport;
  drift_report: DriftReport;
  clusters: Cluster[];
  featured_reviews: Review[];
  executive_summary: string;
  who_should_buy: string;
  who_should_skip: string;
  verdict: string;
  rating_distribution?: Record<string, number>;
  is_simulated?: boolean;
}

export interface AspectScore {
  aspect: string;
  sentiment: "positive" | "negative" | "mixed" | "neutral";
  score: number;
  representative_quote: string;
  mention_count: number;
}

export interface FakeReport {
  total_reviews: number;
  flagged_count: number;
  fake_percentage: number;
  flagged_ids: string[];
  risk_level: "low" | "medium" | "high";
}

export interface DriftReport {
  monthly_sentiment: { month: string; avg_sentiment: number }[];
  change_points: string[];
  trend: "improving" | "declining" | "stable";
}

export interface Cluster {
  cluster_id: number;
  theme: string;
  review_count: number;
  sentiment: "positive" | "negative" | "mixed";
  top_quotes: string[];
}

export interface Review {
  id: string;
  source: string;
  text: string;
  rating: number | null;
  date: string | null;
  verified_purchase: boolean;
  helpful_votes: number;
  reviewer_id: string | null;
  fake_score: number;
}

export function useReportStream(jobId: string) {
  const [report, setReport] = useState<ReportData | null>(null);
  const [progress, setProgress] = useState<ProgressEntry[]>([]);
  const [isComplete, setIsComplete] = useState(false);
  const [isCancelled, setIsCancelled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const es = new EventSource(`${apiUrl}/api/stream/${jobId}`);
    esRef.current = es;

    es.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const type: string = payload.type;

        if (type === "progress") {
          setProgress((prev) => [
            ...prev,
            {
              message: payload.message || "",
              step: payload.step || 0,
              total_steps: payload.total_steps || 8,
              task: payload.task,
              status: payload.status,
            },
          ]);
        } else if (type === "partial") {
          setReport((prev) => ({
            ...((prev ?? {}) as ReportData),
            ...payload.data,
          }));
        } else if (type === "complete") {
          setReport(payload.data);
          setIsComplete(true);
          es.close();
        } else if (type === "cancelled") {
          setIsCancelled(true);
          es.close();
        } else if (type === "error") {
          setError(payload.message || "An error occurred");
          es.close();
        }
      } catch {
        // Ignore parse errors
      }
    };

    es.onerror = () => {
      if (!isComplete) {
        setError("Connection to server lost. Please refresh.");
      }
      es.close();
    };

    return () => {
      es.close();
    };
  }, [jobId]);

  const cancel = async () => {
    // Close the SSE stream immediately for instant UI feedback
    esRef.current?.close();
    setIsCancelled(true);
    // Tell the backend to stop the pipeline
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      await fetch(`${apiUrl}/api/cancel/${jobId}`, { method: "POST" });
    } catch {
      // Ignore — UI is already showing cancelled state
    }
  };

  return { report, progress, isComplete, isCancelled, error, cancel };
}
