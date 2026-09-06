/**
 * test_living_context.mjs
 * 
 * Unit & Contract Tests for OPAL Living Visual + Human Context Experience
 * 
 * Verifies:
 * 1. LivingVisual markup, geometric stations, and static architectural presentation.
 * 2. OfficerContextPanel structure, greeting, officer persona, and links.
 * 3. Strict copy validation: Zero presence of prohibited jargon (LLM, RAG, embedding, orchestration, pipeline stages, AI inference, model).
 * 4. LivingContextSection exports and combined layout.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const livingVisualPath = path.join(__dirname, 'src', 'components', 'LivingVisual.tsx');
const officerContextPath = path.join(__dirname, 'src', 'components', 'OfficerContextPanel.tsx');
const livingContextSectionPath = path.join(__dirname, 'src', 'components', 'LivingContextSection.tsx');

test('1. Component files exist and are readable', () => {
  assert.ok(fs.existsSync(livingVisualPath), 'LivingVisual.tsx must exist');
  assert.ok(fs.existsSync(officerContextPath), 'OfficerContextPanel.tsx must exist');
  assert.ok(fs.existsSync(livingContextSectionPath), 'LivingContextSection.tsx must exist');
});

test('2. LivingVisual: Contains 3-station geometry and restrained document->evidence->review flow', () => {
  const content = fs.readFileSync(livingVisualPath, 'utf-8');

  // Verify accessibility
  assert.ok(content.includes('role="img"'), 'LivingVisual must have role="img"');
  assert.ok(content.includes('aria-label='), 'LivingVisual must have an accessible aria-label');

  // Verify the 3 stations
  assert.ok(content.includes('Document') || content.includes('Doc'), 'Must contain Document station');
  assert.ok(content.includes('Evidence') || content.includes('Fact'), 'Must contain Evidence station');
  assert.ok(content.includes('Review') || content.includes('Ready'), 'Must contain Review Ready station');
});

test('3. LivingVisual: Static and clean presentation', () => {
  const content = fs.readFileSync(livingVisualPath, 'utf-8');

  assert.ok(
    content.includes('pointer-events-none'),
    'LivingVisual must use clean pointer-events-none for structural axes'
  );
});

test('4. OfficerContextPanel: Human orientation structure with greeting, name, and plain language', () => {
  const content = fs.readFileSync(officerContextPath, 'utf-8');

  // Verify time-aware greeting logic
  assert.ok(content.includes('Good Morning') || content.includes('Good morning'), 'Must include Good morning greeting branch');
  assert.ok(content.includes('Good Afternoon') || content.includes('Good afternoon'), 'Must include Good afternoon greeting branch');
  assert.ok(content.includes('Good Evening') || content.includes('Good evening'), 'Must include Good evening greeting branch');

  // Verify default officer persona
  assert.ok(content.includes('Mr. Srivastav'), 'Must default to Mr. Srivastav persona');

  // Verify quick action paths
  assert.ok(content.includes('href="/procurements"'), 'Must link to /procurements');
  assert.ok(content.includes('href="/history"'), 'Must link to /history');
});

test('5. Copywriter Policy: Strict ban on AI/pipeline jargon in officer-facing context', () => {
  const content = fs.readFileSync(officerContextPath, 'utf-8');

  const forbiddenTerms = [
    /\bLLM\b/i,
    /\bLLMs\b/i,
    /\bRAG\b/i,
    /\bembedding\b/i,
    /\bembeddings\b/i,
    /\borchestration\b/i,
    /\bpipeline stages\b/i,
    /\bAI inference\b/i,
  ];

  for (const term of forbiddenTerms) {
    assert.strictEqual(
      term.test(content),
      false,
      `OfficerContextPanel must not contain forbidden technical jargon: ${term}`
    );
  }
});

test('6. LivingContextSection: Re-exports and unifies components cleanly', () => {
  const content = fs.readFileSync(livingContextSectionPath, 'utf-8');

  assert.ok(content.includes('LivingVisual'), 'Must import and render LivingVisual');
  assert.ok(content.includes('OfficerContextPanel'), 'Must import and render OfficerContextPanel');
  assert.ok(content.includes('export { LivingVisual, OfficerContextPanel }'), 'Must export sub-components');
});

test('7. OfficerContextPanel: Freestanding right-edge greeting composition', () => {
  const content = fs.readFileSync(officerContextPath, 'utf-8');

  assert.ok(
    content.includes('text-right') || content.includes('items-end'),
    'Greeting must be right-aligned toward the edge'
  );
});

test('8. OfficerContextPanel: Emerging edge surface card', () => {
  const content = fs.readFileSync(officerContextPath, 'utf-8');

  assert.ok(
    content.includes('rounded-2xl') || content.includes('rounded-3xl'),
    'Must define rounded edge surface container'
  );
  assert.ok(
    content.includes('3 Pending Approvals'),
    'Must include pending approvals alert item'
  );
  assert.ok(
    content.includes('Fiscal Q3 Allocation'),
    'Must include fiscal allocation indicator'
  );
});

test('9. OfficerContextPanel: Real procurement activity integration', () => {
  const content = fs.readFileSync(officerContextPath, 'utf-8');

  assert.ok(
    content.includes('fetchProcurements'),
    'Must import and call fetchProcurements for real activity'
  );
});
