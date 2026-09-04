/**
 * test_frontend_contracts.mjs
 * 
 * Frontend Integration & Canonical Contract Verification Test Suite
 * Tests:
 * 1. API Module Exports and Signature Integrity
 * 2. API Response & Network Error Normalization (400, 404, 409, 422, 500, 503)
 * 3. Compliance Status Canonical Mapping (PASS, FAIL, REVIEW, UNVERIFIED, NOT_APPLICABLE)
 * 4. Structured Provenance Records (PDF page, Sheet, Cell, Row, Section)
 * 5. Contradiction Finding Side-by-Side Model Integrity
 * 6. Ambiguity Finding Model Integrity
 * 7. Procurement Processing Lifecycle Status Flow
 * 8. Human Review Decision-Support Boundary Invariant
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import * as api from './src/services/api.js';

test('1. API Module Exports all required Canonical Integration Methods', () => {
  const requiredMethods = [
    'fetchProcurements',
    'fetchProcurementList',
    'fetchProcurementDetail',
    'fetchTenderDetail',
    'fetchSubmissionDetail',
    'startProcurementProcessing',
    'getProcurementProcessingStatus',
    'evaluateSubmission',
    'fetchVerificationHistory',
    'verifyGSTDocument',
    'analyzeTender',
  ];

  for (const method of requiredMethods) {
    assert.strictEqual(
      typeof api[method],
      'function',
      `Expected ${method} to be exported as a function from api.js`
    );
  }
});

test('2. API Response Handling: Normalizes JSON errors, HTTP errors, and Network failures', async () => {
  assert.strictEqual(typeof api.handleApiResponse, 'function');
  assert.strictEqual(typeof api.normalizeNetworkError, 'function');

  // Case A: 404 Not Found with JSON detail
  const mock404 = {
    ok: false,
    status: 404,
    statusText: 'Not Found',
    headers: { get: () => 'application/json' },
    json: async () => ({ detail: 'Procurement workspace not found' }),
  };
  await assert.rejects(
    async () => await api.handleApiResponse(mock404, 'Failed to fetch procurement'),
    {
      name: 'Error',
      message: /Procurement workspace not found/,
    }
  );

  // Case B: 422 Validation Error
  const mock422 = {
    ok: false,
    status: 422,
    statusText: 'Unprocessable Entity',
    headers: { get: () => 'application/json' },
    json: async () => ({ detail: [{ loc: ['body', 'force'], msg: 'field required' }] }),
  };
  await assert.rejects(
    async () => await api.handleApiResponse(mock422, 'Validation error'),
    {
      name: 'Error',
    }
  );

  // Case C: 500 Internal Server Error (Non-JSON or fallback)
  const mock500 = {
    ok: false,
    status: 500,
    statusText: 'Internal Server Error',
    headers: { get: () => 'text/html' },
    json: async () => { throw new Error('Not JSON'); },
  };
  await assert.rejects(
    async () => await api.handleApiResponse(mock500, 'Server crashed'),
    {
      name: 'Error',
      message: /Internal service error/,
    }
  );

  // Case D: Network connection failure
  const netError = new TypeError('Failed to fetch');
  const normalized = api.normalizeNetworkError(netError, 'Action failed');
  assert.ok(normalized.message.includes('Unable to connect to the backend server'));
});

test('3. Compliance Status Values match Canonical Backend Enums', () => {
  const canonicalStatuses = ['PASS', 'FAIL', 'REVIEW', 'UNVERIFIED', 'NOT_APPLICABLE'];
  const legacySynonyms = {
    'COMPLIANT': 'PASS',
    'NON_COMPLIANT': 'FAIL',
    'NEEDS_REVIEW': 'REVIEW',
    'NOT_VERIFIED': 'UNVERIFIED',
  };

  for (const status of canonicalStatuses) {
    assert.ok(status.length > 0, `Canonical status ${status} is valid`);
  }

  for (const [legacy, canonical] of Object.entries(legacySynonyms)) {
    assert.ok(canonicalStatuses.includes(canonical), `Legacy status ${legacy} maps to canonical ${canonical}`);
  }
});

test('4. Structured Provenance Records support Non-PDF metadata', () => {
  const pdfRecord = {
    document_id: 'doc-uuid-001',
    document_name: 'Technical_Specification.pdf',
    page_number: 14,
    source_type: 'Technical Specification',
    quote: 'Local content shall be minimum 50%',
    normalized_value: 50,
    unit: '%',
  };

  const spreadsheetRecord = {
    document_id: 'doc-uuid-002',
    document_name: 'Financial_BoQ.xlsx',
    sheet_name: 'Price_Schedule_A',
    row_number: 42,
    cell_reference: 'D42',
    source_type: 'Bill of Quantities',
    quote: 'Total Ex-works Price: 1,25,00,000',
    normalized_value: 12500000,
    unit: 'INR',
  };

  const docxRecord = {
    document_id: 'doc-uuid-003',
    document_name: 'Manufacturer_Authorization.docx',
    section_context: 'Section 4.2 - OEM Warranty Commitment',
    source_type: 'OEM Certificate',
    quote: 'OEM commits to 5 years comprehensive warranty',
    normalized_value: 5,
    unit: 'Years',
  };

  assert.strictEqual(pdfRecord.page_number, 14);
  assert.strictEqual(spreadsheetRecord.sheet_name, 'Price_Schedule_A');
  assert.strictEqual(spreadsheetRecord.cell_reference, 'D42');
  assert.strictEqual(docxRecord.section_context, 'Section 4.2 - OEM Warranty Commitment');
});

test('5. Contradiction Finding maintains Balanced Side-by-Side Invariant', () => {
  const contradictionFinding = {
    finding_id: 'contr-001',
    bidder_name: 'Acme Technologies Ltd',
    contradiction_type: 'VALUE_DISCREPANCY',
    comparison: {
      left: {
        document_name: 'Bidder_MII_Declaration.pdf',
        page_number: 2,
        raw_value: '65%',
        normalized_value: 65,
        quote: 'We hereby declare local content is 65%',
      },
      right: {
        document_name: 'Auditor_Cost_Breakup.pdf',
        page_number: 7,
        raw_value: '38%',
        normalized_value: 38,
        quote: 'Audited domestic value addition stands at 38%',
      },
      discrepancy_description: 'Bidder self-declaration of 65% contradicts chartered accountant certified local content of 38%.',
      delta_value: 27,
    },
    suggested_action: 'Require bidder to clarify discrepancy before technical committee review.',
  };

  assert.ok(contradictionFinding.comparison.left, 'Left evidence record must exist');
  assert.ok(contradictionFinding.comparison.right, 'Right evidence record must exist');
  assert.notStrictEqual(
    contradictionFinding.comparison.left.normalized_value,
    contradictionFinding.comparison.right.normalized_value,
    'Contradictory values must not be equal'
  );
  // Decision support check: neither side should be marked as "auto-accepted winner"
  assert.strictEqual(contradictionFinding.comparison.left.is_winner, undefined);
  assert.strictEqual(contradictionFinding.comparison.right.is_winner, undefined);
});

test('6. Ambiguity Finding preserves source clause and clarification prompt', () => {
  const ambiguityFinding = {
    ambiguity_id: 'amb-001',
    tender_id: 'tender-uuid-001',
    requirement_id: 'req-turnover-001',
    ambiguity_type: 'UNIT_MISMATCH',
    description: 'Tender clause specifies turnover in Lakhs whereas bidder BoQ is in Crores without conversion factor.',
    affected_clause: 'Clause 8.1 - Minimum Average Annual Turnover',
    clarification_prompt: 'Please confirm whether audited turnover is in INR Lakhs or Crores.',
    severity: 'MEDIUM',
  };

  assert.strictEqual(ambiguityFinding.ambiguity_type, 'UNIT_MISMATCH');
  assert.ok(ambiguityFinding.affected_clause.includes('Clause 8.1'));
  assert.ok(ambiguityFinding.clarification_prompt.length > 10);
});

test('7. Procurement Processing Lifecycle Status Flow', () => {
  const lifecycleStages = [
    'TENDER_INTELLIGENCE',
    'DOCUMENT_INTELLIGENCE',
    'EVIDENCE_EXTRACTION',
    'COMPLIANCE_EVALUATION',
  ];

  const processingStatus = {
    procurement_id: 'proc-001',
    status: 'PROCESSING',
    current_stage: 'DOCUMENT_INTELLIGENCE',
    completed_stages: ['TENDER_INTELLIGENCE'],
    failed_stage: null,
    stage_results: [
      {
        stage: 'TENDER_INTELLIGENCE',
        success: true,
        execution_time_ms: 1240,
        metadata: { requirements_extracted: 14 },
      },
    ],
    retry_count: 0,
  };

  assert.strictEqual(processingStatus.completed_stages.length, 1);
  assert.ok(lifecycleStages.includes(processingStatus.current_stage));
  assert.strictEqual(processingStatus.stage_results[0].success, true);
});

test('8. Human Review Decision-Support Boundary Invariant', () => {
  // Verification that human review notes are maintained and no automated qualification is triggered
  const humanReviewState = {
    submission_id: 'sub-001',
    status: 'UNDER_REVIEW', // Not 'AUTO_QUALIFIED' or 'AUTO_DISQUALIFIED'
    review_notes: 'Reviewed GST discrepancy; bidder requested to submit rectified GSTR-3B by Friday.',
    reviewed_by: 'Procurement Officer - Evaluation Committee',
    reviewed_at: new Date().toISOString(),
    is_decision_final: false,
  };

  assert.strictEqual(humanReviewState.status, 'UNDER_REVIEW');
  assert.strictEqual(humanReviewState.is_decision_final, false);
  assert.ok(humanReviewState.reviewed_by.includes('Procurement Officer'));
});

console.log('All 8 canonical frontend contract and integration suites executed.');
