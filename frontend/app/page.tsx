"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const EXAMPLE_QUERIES = [
  "Sony WH-1000XM5 headphones",
  "Apple AirPods Pro 2nd gen",
  "Samsung Galaxy S24 Ultra",
  "Dyson V15 vacuum cleaner",
  "Instant Pot Duo 7-in-1",
  "Kindle Paperwhite 11th gen",
];

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleSubmit = async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: trimmed, use_cache: true }),
      });

      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }

      const data = await res.json();
      router.push(`/report/${data.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center py-16">
      {/* Hero */}
      <div className="text-center mb-12 max-w-2xl">
        <div className="inline-flex items-center gap-2 bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-sm font-medium mb-6">
          <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
          100% local · No paid APIs
        </div>
        <h1 className="text-5xl font-bold text-slate-900 mb-4 leading-tight">
          Know what reviewers{" "}
          <span className="text-blue-600">actually think</span>
        </h1>
        <p className="text-xl text-slate-600">
          AI-powered analysis of real product reviews. Detects fake reviews,
          tracks sentiment over time, and synthesizes honest verdicts from
          Amazon, Reddit, Best Buy, and YouTube.
        </p>
      </div>

      {/* Search */}
      <div className="w-full max-w-2xl">
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit(query)}
            placeholder="e.g. Sony WH-1000XM5 headphones"
            className="flex-1 px-5 py-4 text-lg rounded-xl border-2 border-slate-200 focus:border-blue-500 focus:outline-none bg-white shadow-sm"
            disabled={loading}
          />
          <button
            onClick={() => handleSubmit(query)}
            disabled={loading || !query.trim()}
            className="px-6 py-4 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm whitespace-nowrap"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Analyzing...
              </span>
            ) : (
              "Analyze"
            )}
          </button>
        </div>

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Example queries */}
        <div className="mt-6">
          <p className="text-sm text-slate-500 mb-3">Try an example:</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => handleSubmit(q)}
                disabled={loading}
                className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-sm text-slate-700 hover:border-blue-300 hover:text-blue-700 transition-colors disabled:opacity-50"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Features */}
      <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl">
        {[
          {
            icon: "🔍",
            title: "Multi-source scraping",
            desc: "Reviews from Amazon, Reddit, Best Buy, and YouTube combined into one analysis.",
          },
          {
            icon: "🛡️",
            title: "Fake review detection",
            desc: "Isolation Forest ML model flags suspicious patterns: generic praise, review bursts, bot behavior.",
          },
          {
            icon: "📈",
            title: "Sentiment drift",
            desc: "Track how opinions change over time. Spot products that are improving or declining.",
          },
          {
            icon: "🎯",
            title: "Aspect analysis",
            desc: "Per-aspect scores for build quality, performance, value, ease of use, and more.",
          },
          {
            icon: "🧩",
            title: "Theme clustering",
            desc: "AI groups reviews into emergent themes so you see what people care about most.",
          },
          {
            icon: "🤖",
            title: "Local LLM",
            desc: "Powered by Ollama + Mistral. All processing stays on your machine.",
          },
        ].map((f) => (
          <div key={f.title} className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="text-3xl mb-3">{f.icon}</div>
            <h3 className="font-semibold text-slate-900 mb-1">{f.title}</h3>
            <p className="text-slate-600 text-sm">{f.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
