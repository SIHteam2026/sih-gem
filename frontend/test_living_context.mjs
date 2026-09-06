/**
 * test_living_context.mjs
 * 
 * Unit & Contract Tests for OPAL Living Visual + Human Context Experience
 * 
 * Verifies:
 * 1. LivingVisual markup, geometric stations (Doc -> Fact -> Ready), and CSS animations.
 * 2. Prefers-reduced-motion handling and static calm state.
 * 3. OfficerContextPanel structure, greeting, officer persona, and links.
 * 4. Strict copy validation: Zero presence of prohibited jargon (LLM, RAG, embedding, orchestration, pipeline stages, AI inference, model).
 * 5. LivingContextSection exports and combined layout.
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
  assert.ok(content.includes('Doc') || content.includes('Document'), 'Must contain Document station');
  assert.ok(content.includes('Fact') || content.includes('Evidence'), 'Must contain Evidence station');
  assert.ok(content.includes('Ready') || content.includes('Review'), 'Must contain Review Ready station');

  // Verify restrained keyframe animation definition
  assert.ok(content.includes('@keyframes verticalStreamCycle'), 'Must define verticalStreamCycle animation');
  assert.ok(content.includes('11s'), 'Must use a slow 8-15s animation cycle');
});

test('3. LivingVisual: Implements prefers-reduced-motion for a calm static state', () => {
  const content = fs.readFileSync(livingVisualPath, 'utf-8');

  assert.ok(
    content.includes('@media (prefers-reduced-motion: reduce)'),
    'LivingVisual must explicitly support @media (prefers-reduced-motion: reduce)'
  );
  assert.ok(
    content.includes('animation: none'),
    'Reduced motion must disable continuous animation'
  );
});

test('4. OfficerContextPanel: Human orientation structure with greeting, name, and plain language', () => {
  const content = fs.readFileSync(officerContextPath, 'utf-8');

  // Verify time-aware greeting logic
  assert.ok(content.includes('Good morning'), 'Must include Good morning greeting branch');
  assert.ok(content.includes('Good afternoon'), 'Must include Good afternoon greeting branch');
  assert.ok(content.includes('Good evening'), 'Must include Good evening greeting branch');

  // Verify default officer persona
  assert.ok(content.includes('Mr. Srivastav'), 'Must default to Mr. Srivastav persona');
  assert.ok(content.includes('Procurement Review Officer'), 'Must include role title');

  // Verify human contextual explanation
  assert.ok(
    content.includes('Your procurement reviews and recent activity'),
    'Must contain the contextual explanation'
  );

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
  assert.ok(
    content.includes('tracking-widest') || content.includes('tracking-wider'),
    'Greeting must use restrained uppercase typography'
  );
});

test('8. OfficerContextPanel: Half-emerging edge surface & entrance motion', () => {
  const content = fs.readFileSync(officerContextPath, 'utf-8');

  // Verify half-emerging edge panel styling
  assert.ok(
    content.includes('opal-edge-surface'),
    'Must define opal-edge-surface element'
  );
  assert.ok(
    content.includes('lg:border-r-0') || content.includes('lg:rounded-r-none'),
    'Must open towards the right edge on desktop'
  );

  // Verify entrance animation and reduced-motion fallback
  assert.ok(
    content.includes('@keyframes edgeSlideIn'),
    'Must define edgeSlideIn entrance animation'
  );
  assert.ok(
    content.includes('@media (prefers-reduced-motion: reduce)'),
    'Must support prefers-reduced-motion'
  );
});

test('9. OfficerContextPanel: Real procurement activity integration', () => {
  const content = fs.readFileSync(officerContextPath, 'utf-8');

  assert.ok(
    content.includes('fetchProcurements'),
    'Must import and call fetchProcurements for real activity'
  );
  assert.ok(
    content.includes('recentCases') || content.includes('ProcurementSummaryItem'),
    'Must manage state for recent cases'
  );
});

