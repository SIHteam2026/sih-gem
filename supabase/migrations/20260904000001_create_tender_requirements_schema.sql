-- Migration: Create Canonical Tender Requirements Schema for OPAL Platform
-- Timestamp: 20260904000001
-- Extends: 20260904000000_create_procurement_canonical_schema.sql

-- Enable UUID extension if not present
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 6. Tender Requirements Table (Linked to Canonical Tenders)
CREATE TABLE IF NOT EXISTS public.tender_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id UUID NOT NULL REFERENCES public.tenders(id) ON DELETE CASCADE,
    requirement_id TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT,
    description TEXT NOT NULL,
    mandatory BOOLEAN NOT NULL DEFAULT true,
    structured_condition JSONB,
    applicability JSONB,
    evidence_spec JSONB,
    source_provenance JSONB,
    ambiguity JSONB,
    evidence_required JSONB DEFAULT '[]'::jsonb,
    is_ambiguous BOOLEAN NOT NULL DEFAULT false,
    ambiguity_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_tender_requirement UNIQUE (tender_id, requirement_id)
);

-- Indexes for Requirement Query Performance & Rapid Compliance Filtering
CREATE INDEX IF NOT EXISTS idx_tender_requirements_tender_id ON public.tender_requirements(tender_id);
CREATE INDEX IF NOT EXISTS idx_tender_requirements_category ON public.tender_requirements(category);
CREATE INDEX IF NOT EXISTS idx_tender_requirements_ambiguous ON public.tender_requirements(is_ambiguous);
CREATE INDEX IF NOT EXISTS idx_tender_requirements_mandatory ON public.tender_requirements(mandatory);

-- Enable Row Level Security (RLS)
ALTER TABLE public.tender_requirements ENABLE ROW LEVEL SECURITY;

-- Allow open development policies for prototype API access
DROP POLICY IF EXISTS "Allow all access to tender_requirements" ON public.tender_requirements;
CREATE POLICY "Allow all access to tender_requirements" ON public.tender_requirements FOR ALL USING (true) WITH CHECK (true);
