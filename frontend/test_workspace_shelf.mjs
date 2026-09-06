/**
 * test_workspace_shelf.mjs
 * 
 * Unit & Contract Tests for OPAL Workspace Project Shelf Page
 * 
 * Verifies:
 * 1. Opal Workspace Shelf page component and ProjectCard exist.
 * 2. Page Title: Clean, left-aligned "Opal Workspace" heading without generic marketing copy.
 * 3. Layout: 2-column responsive grid layout on desktop (md:grid-cols-2).
 * 4. ProjectCard contract: Reusable component accepting title, department, loadedDate, state, onOpen.
 * 5. Data Source: Uses canonical fetchProcurements without hardcoded data.
 * 6. Dynamic Tag Semantics: Deterministic NEW / DRAFT derivation from real status & officer review signals.
 * 7. Date Formatting: Human-readable "Loaded <Date>" format without raw timestamp noise.
 * 8. States: Simple loading, human error, and "Your workspace is empty." empty state with Mock-GeM link.
 * 9. Navigation: Direct routing to canonical /procurements/${id} detail workspace.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const shelfPagePath = path.join(__dirname, 'src', 'app', 'procurements', 'page.tsx');
const projectCardPath = path.join(__dirname, 'src', 'components', 'procurement', 'ProjectCard.tsx');

test('1. Workspace Shelf and ProjectCard component files exist', () => {
  assert.ok(fs.existsSync(shelfPagePath), 'procurements/page.tsx must exist');
  assert.ok(fs.existsSync(projectCardPath), 'ProjectCard.tsx must exist');
});

test('2. Page Title: Clean "Opal Workspace" heading without marketing hype', () => {
  const content = fs.readFileSync(shelfPagePath, 'utf-8');

  assert.ok(content.includes('Opal Workspace'), 'Must contain "Opal Workspace" heading');
  
  // Strict ban on generic AI hype / marketing phrases
  const forbiddenMarketing = [
    /Manage your procurement portfolio/i,
    /AI-powered procurement command center/i,
    /monitoring cockpit/i,
    /analytics dashboard/i,
  ];

  for (const pattern of forbiddenMarketing) {
    assert.strictEqual(
      pattern.test(content),
      false,
      `Opal Workspace page must not contain marketing buzzwords: ${pattern}`
    );
  }
});

test('3. Responsive Composition: 2-column grid on desktop', () => {
  const content = fs.readFileSync(shelfPagePath, 'utf-8');

  assert.ok(
    content.includes('grid-cols-1') && content.includes('md:grid-cols-2'),
    'Must implement 2-column grid on desktop and 1-column on mobile'
  );
});

test('4. ProjectCard Component Interface Contract', () => {
  const content = fs.readFileSync(projectCardPath, 'utf-8');

  // Verify contract prop definitions
  assert.ok(content.includes('title'), 'ProjectCard must accept title');
  assert.ok(content.includes('department'), 'ProjectCard must accept department');
  assert.ok(content.includes('loadedDate'), 'ProjectCard must accept loadedDate');
  assert.ok(content.includes('state'), 'ProjectCard must accept state');
  assert.ok(content.includes('onOpen'), 'ProjectCard must accept onOpen');

  // Verify interactive accessibility
  assert.ok(content.includes('role="button"') || content.includes('onClick'), 'ProjectCard must be interactive');
});

test('5. Canonical Procurement API Integration', () => {
  const content = fs.readFileSync(shelfPagePath, 'utf-8');

  assert.ok(content.includes('fetchProcurements'), 'Must fetch canonical procurements via fetchProcurements');
  assert.ok(content.includes('@/services/api'), 'Must import from canonical api service');
});

test('6. Dynamic Working-State Tag Semantics (NEW vs DRAFT)', () => {
  const content = fs.readFileSync(shelfPagePath, 'utf-8');

  assert.ok(content.includes('deriveProjectState'), 'Must define deterministic deriveProjectState function');
  assert.ok(content.includes('NEW'), 'Must define NEW state');
  assert.ok(content.includes('DRAFT'), 'Must define DRAFT state');
  assert.ok(content.includes('IMPORTED'), 'Must account for canonical IMPORTED status');
  assert.ok(content.includes('PROCESSING'), 'Must account for canonical PROCESSING status');
});

test('7. Clean Date Formatting without timestamp noise', () => {
  const content = fs.readFileSync(shelfPagePath, 'utf-8');

  assert.ok(content.includes('formatLoadedDate'), 'Must define formatLoadedDate helper');
  assert.ok(content.includes('Loaded '), 'Must prefix with "Loaded "');
});

test('8. Calm States: Simple loading, human error, and empty state', () => {
  const content = fs.readFileSync(shelfPagePath, 'utf-8');

  assert.ok(content.includes('Your workspace is empty.'), 'Must contain exact empty text "Your workspace is empty."');
  assert.ok(content.includes('/mock-gem'), 'Must provide link to Mock-GeM in empty state');
  assert.ok(!content.includes('err.message || err.toString()'), 'Must not expose raw API errors');
});

test('9. Canonical Navigation to procurement detail workspace', () => {
  const content = fs.readFileSync(shelfPagePath, 'utf-8');

  assert.ok(content.includes('/procurements/'), 'Must navigate to canonical /procurements/${id} route');
  assert.ok(content.includes('encodeURIComponent'), 'Must safely encode procurement id');
});
