-- Migration: Create Canonical Procurement Data Model for OPAL Platform
-- Timestamp: 20260904000000

-- Enable UUID extension if not present
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Procurements Table
CREATE TABLE IF NOT EXISTS public.procurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system TEXT NOT NULL DEFAULT 'MOCK_GEM',
    external_reference TEXT NOT NULL,
    title TEXT NOT NULL,
    organization TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'IMPORTED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_source_external_ref UNIQUE (source_system, external_reference),
    CONSTRAINT chk_procurement_status CHECK (status IN ('IMPORTED', 'PROCESSING', 'READY', 'FAILED'))
);

-- 2. Tenders Table
CREATE TABLE IF NOT EXISTS public.tenders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    procurement_id UUID NOT NULL REFERENCES public.procurements(id) ON DELETE CASCADE,
    tender_reference TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    estimated_value NUMERIC(15, 2),
    category TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Bidders Table
CREATE TABLE IF NOT EXISTS public.bidders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name TEXT NOT NULL,
    gstin TEXT,
    pan TEXT,
    email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Bid Submissions Table
CREATE TABLE IF NOT EXISTS public.bid_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id UUID NOT NULL REFERENCES public.tenders(id) ON DELETE CASCADE,
    bidder_id UUID NOT NULL REFERENCES public.bidders(id) ON DELETE CASCADE,
    external_submission_reference TEXT,
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'SUBMITTED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Documents Table
CREATE TABLE IF NOT EXISTS public.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    procurement_id UUID NOT NULL REFERENCES public.procurements(id) ON DELETE CASCADE,
    tender_id UUID REFERENCES public.tenders(id) ON DELETE CASCADE,
    bid_submission_id UUID REFERENCES public.bid_submissions(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    document_type TEXT,
    mime_type TEXT NOT NULL DEFAULT 'application/pdf',
    file_size BIGINT,
    storage_path TEXT,
    content_text TEXT,
    processing_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for Foreign Key Lookup Performance
CREATE INDEX IF NOT EXISTS idx_tenders_procurement_id ON public.tenders(procurement_id);
CREATE INDEX IF NOT EXISTS idx_bid_submissions_tender_id ON public.bid_submissions(tender_id);
CREATE INDEX IF NOT EXISTS idx_bid_submissions_bidder_id ON public.bid_submissions(bidder_id);
CREATE INDEX IF NOT EXISTS idx_documents_procurement_id ON public.documents(procurement_id);
CREATE INDEX IF NOT EXISTS idx_documents_tender_id ON public.documents(tender_id);
CREATE INDEX IF NOT EXISTS idx_documents_bid_submission_id ON public.documents(bid_submission_id);

-- Enable Row Level Security (RLS)
ALTER TABLE public.procurements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bidders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bid_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

-- Allow open development policies for prototype API access
DROP POLICY IF EXISTS "Allow all access to procurements" ON public.procurements;
CREATE POLICY "Allow all access to procurements" ON public.procurements FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all access to tenders" ON public.tenders;
CREATE POLICY "Allow all access to tenders" ON public.tenders FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all access to bidders" ON public.bidders;
CREATE POLICY "Allow all access to bidders" ON public.bidders FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all access to bid_submissions" ON public.bid_submissions;
CREATE POLICY "Allow all access to bid_submissions" ON public.bid_submissions FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all access to documents" ON public.documents;
CREATE POLICY "Allow all access to documents" ON public.documents FOR ALL USING (true) WITH CHECK (true);
