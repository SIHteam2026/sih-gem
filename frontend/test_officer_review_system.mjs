/**
 * test_officer_review_system.mjs
 * 
 * Unit & Contract Tests for Officer Review & Determination System
 * 
 * Verifies:
 * 1. reviewDecisions.ts service exports required state management and stat computation methods.
 * 2. OfficerReviewActionCard.tsx renders "Confirm Verifications" and "Need Further Review" buttons.
 * 3. OfficerContextPanel.tsx renders the dynamic review determination panel breakdown.
 * 4. Procurement detail and submission pages integrate the review action card under reports.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const servicePath = path.join(__dirname, 'src', 'services', 'reviewDecisions.ts');
const actionCardPath = path.join(__dirname, 'src', 'components', 'procurement', 'OfficerReviewActionCard.tsx');
const contextPanelPath = path.join(__dirname, 'src', 'components', 'OfficerContextPanel.tsx');
const procurementPagePath = path.join(__dirname, 'src', 'app', 'procurements', '[procurementId]', 'page.tsx');
const submissionPagePath = path.join(__dirname, 'src', 'app', 'submissions', '[submissionId]', 'page.tsx');
const executiveReportPath = path.join(__dirname, 'src', 'components', 'ExecutiveReport.tsx');

test('1. reviewDecisions service exists and exports state methods', () => {
  assert.ok(fs.existsSync(servicePath), 'reviewDecisions.ts must exist');
  const content = fs.readFileSync(servicePath, 'utf-8');

  assert.ok(content.includes('saveOfficerDecision'), 'Must export saveOfficerDecision');
  assert.ok(content.includes('getOfficerDecisionFor'), 'Must export getOfficerDecisionFor');
  assert.ok(content.includes('computeReviewStats'), 'Must export computeReviewStats');
  assert.ok(content.includes('subscribeToReviewDecisions'), 'Must export subscribeToReviewDecisions');
});

test('2. OfficerReviewActionCard contains Confirm Verifications & Need Further Review actions', () => {
  assert.ok(fs.existsSync(actionCardPath), 'OfficerReviewActionCard.tsx must exist');
  const content = fs.readFileSync(actionCardPath, 'utf-8');

  assert.ok(content.includes('Confirm Verifications'), 'Must have "Confirm Verifications" button text');
  assert.ok(content.includes('Need Further Review'), 'Must have "Need Further Review" button text');
  assert.ok(content.includes('saveOfficerDecision'), 'Must call saveOfficerDecision');
});

test('3. OfficerContextPanel renders dynamic review status breakdown', () => {
  const content = fs.readFileSync(contextPanelPath, 'utf-8');

  assert.ok(content.includes('Pending Reviews'), 'Must show Pending Reviews count label');
  assert.ok(content.includes('Further Analysis') || content.includes('Further Review'), 'Must show Further Analysis count label');
  assert.ok(content.includes('Confirmed'), 'Must show Confirmed count label');
  assert.ok(content.includes('computeReviewStats'), 'Must call computeReviewStats');
  assert.ok(content.includes('subscribeToReviewDecisions'), 'Must subscribe to live updates');
});

test('4. Procurement and Submission pages integrate OfficerReviewActionCard', () => {
  const procContent = fs.readFileSync(procurementPagePath, 'utf-8');
  assert.ok(procContent.includes('OfficerReviewActionCard'), 'Procurement page must include OfficerReviewActionCard');

  const subContent = fs.readFileSync(submissionPagePath, 'utf-8');
  assert.ok(subContent.includes('OfficerReviewActionCard'), 'Submission page must include OfficerReviewActionCard');

  const repContent = fs.readFileSync(executiveReportPath, 'utf-8');
  assert.ok(repContent.includes('OfficerReviewActionCard'), 'ExecutiveReport must include OfficerReviewActionCard');
});
