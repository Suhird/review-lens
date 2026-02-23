CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_name TEXT UNIQUE NOT NULL,
    display_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    source TEXT NOT NULL,
    text TEXT NOT NULL,
    rating FLOAT,
    review_date TIMESTAMPTZ,
    verified_purchase BOOLEAN DEFAULT FALSE,
    helpful_votes INTEGER DEFAULT 0,
    reviewer_id TEXT,
    fake_score FLOAT DEFAULT 0.0,
    embedding vector(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id),
    report_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS reviews_embedding_idx ON reviews USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS reviews_product_id_idx ON reviews (product_id);
CREATE INDEX IF NOT EXISTS reviews_source_idx ON reviews (source);
