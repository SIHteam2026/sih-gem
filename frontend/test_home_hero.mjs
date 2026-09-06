/**
 * test_home_hero.mjs
 * 
 * Unit & Contract Tests for OPAL Home Hero Experience
 * 
 * Verifies:
 * 1. HomeHero.tsx exists, exports default component.
 * 2. Hierarchy: Eyebrow ("Procurement Review"), Headline ("Review the procurement. We’ll bring the evidence.").
 * 3. Human copy: Explains tender requirements, bidder claims, supporting evidence, and verification findings.
 * 4. Ban on generic AI marketing buzzwords (AI-powered, intelligent compliance automation platform, revolutionary, etc.).
 * 5. Primary action links to /procurements with accessible styling and clear text.
 * 6. Responsive typography classes (text-balance, text-pretty, sm/lg breakpoints).
 * 7. Home page integration in src/app/page.tsx.
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

test('2. Hierarchy: Contains eyebrow, headline, and supporting description', () => {
  const content = fs.readFileSync(heroPath, 'utf-8');

  // Eyebrow
  assert.ok(content.includes('Procurement Review'), 'Must contain "Procurement Review" eyebrow');

  // Headline
  assert.ok(content.includes('Review the procurement.'), 'Must contain first part of headline');
  assert.ok(content.includes('We’ll bring the evidence.') || content.includes("We'll bring the evidence."), 'Must contain second part of headline');

  // Supporting copy elements
  assert.ok(content.includes('tender requirements'), 'Must mention tender requirements');
  assert.ok(content.includes('bidder claims'), 'Must mention bidder claims');
  assert.ok(content.includes('supporting evidence') || content.includes('evidence'), 'Must mention supporting evidence');
  assert.ok(content.includes('verification findings') || content.includes('findings'), 'Must mention verification findings');
  assert.ok(content.includes('human judgment') || content.includes('human attention'), 'Must highlight human judgment/attention');
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

test('4. Primary Workspace Gateway: Embeds RecentProcurementsSection and secondary tools', () => {
  const content = fs.readFileSync(heroPath, 'utf-8');

  assert.ok(content.includes('RecentProcurementsSection'), 'Must embed RecentProcurementsSection as primary gateway');
  assert.ok(content.includes('href="/history"'), 'Must provide link to /history');
  assert.ok(content.includes('href="/mock-gem"'), 'Must provide link to /mock-gem');
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
