/**
 * test_home_hero.mjs
 * 
 * Unit & Contract Tests for OPAL Home Hero Experience
 * 
 * Verifies:
 * 1. HomeHero.tsx exists, exports default component.
 * 2. Hierarchy: Large Headline ("See What the Evidence Says"), Supporting Description.
 * 3. Human copy: Explains tender requirements, bidder claims, supporting evidence, and verification findings.
 * 4. Ban on generic AI marketing buzzwords (AI-powered, intelligent compliance automation platform, revolutionary, etc.).
 * 5. Primary Workspace Gateway: Embeds RecentProcurementsSection.
 * 6. Responsive Typography: Uses balanced wrapping.
 * 7. Home Page integration in src/app/page.tsx.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const heroPath = path.join(__dirname, 'src', 'components', 'HomeHero.tsx');
const homePagePath = path.join(__dirname, 'src', 'app', 'page.tsx');

test('1. HomeHero component file exists', () => {
  assert.ok(fs.existsSync(heroPath), 'HomeHero.tsx must exist');
});

test('2. Hierarchy: Contains headline and supporting description matching reference', () => {
  const content = fs.readFileSync(heroPath, 'utf-8');

  // Headline
  assert.ok(content.includes('See What the') || content.includes('Review the procurement.'), 'Must contain first part of headline');
  assert.ok(content.includes('Evidence Says') || content.includes('We’ll bring the evidence.'), 'Must contain second part of headline');

  // Supporting copy elements
  assert.ok(content.includes('tender requirements'), 'Must mention tender requirements');
  assert.ok(content.includes('bidder evidence') || content.includes('bidder claims') || content.includes('supporting evidence'), 'Must mention bidder evidence/claims');
  assert.ok(content.includes('contradictions') || content.includes('findings'), 'Must mention contradictions/findings');
  assert.ok(content.includes('critical judgment') || content.includes('human judgment'), 'Must highlight officer judgment');
});

test('3. Copywriter Policy: Zero generic AI hype buzzwords', () => {
  const content = fs.readFileSync(heroPath, 'utf-8');

  const forbiddenTerms = [
    /AI-powered/i,
    /intelligent compliance automation platform/i,
    /revolutionary/i,
    /game-changing/i,
    /autonomous decision/i,
    /automatic rejection/i,
  ];

  for (const term of forbiddenTerms) {
    assert.strictEqual(
      term.test(content),
      false,
      `HomeHero must not contain forbidden marketing jargon: ${term}`
    );
  }
});

test('4. Primary Workspace Gateway: Embeds RecentProcurementsSection', () => {
  const content = fs.readFileSync(heroPath, 'utf-8');

  assert.ok(content.includes('RecentProcurementsSection'), 'Must embed RecentProcurementsSection as primary gateway');
});

test('5. Responsive Typography: Uses balanced wrapping', () => {
  const content = fs.readFileSync(heroPath, 'utf-8');

  assert.ok(content.includes('text-balance'), 'Headline must use text-balance');
  assert.ok(content.includes('text-pretty'), 'Description must use text-pretty');
});

test('6. Home Page: Integrates HomeHero component cleanly', () => {
  const content = fs.readFileSync(homePagePath, 'utf-8');

  assert.ok(content.includes('import HomeHero from "@/components/HomeHero"'), 'page.tsx must import HomeHero');
  assert.ok(content.includes('<HomeHero />') || content.includes('<HomeHero'), 'page.tsx must render HomeHero');
});
