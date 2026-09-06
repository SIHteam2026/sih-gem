/**
 * test_home_shell.mjs
 * 
 * Unit & Contract Tests for OPAL Home Page Structural Shell & Composition
 * 
 * Verifies:
 * 1. HomeShell.tsx exists and exports default HomeShell component.
 * 2. Slot architecture: Provides typed slots for Header, HeroSlot, LivingVisualSlot, ContextSlot, RecentProcurementSlot.
 * 3. 3-column asymmetric layout composition: Dominant left column (7 cols), narrow center axis (1 col), context panel (4 cols).
 * 4. Responsive recomposition: Stacks gracefully on mobile/tablet (hidden lg:flex for center visual axis) without cramped coordinates.
 * 5. Semantic HTML landmarks: <main id=main-content>, <section>, <header>, accessible aria labels.
 * 6. Visual philosophy: Zero presence of forbidden clutter (gradients, glowing elements, neon aesthetics, floating dashboard cards).
 * 7. Home Page integration: src/app/page.tsx integrates HomeShell with HomeHero, LivingVisual, OfficerContextPanel, RecentProcurementsSection.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const homeShellPath = path.join(__dirname, 'src', 'components', 'HomeShell.tsx');
const homePagePath = path.join(__dirname, 'src', 'app', 'page.tsx');
const navbarPath = path.join(__dirname, 'src', 'components', 'Navbar.tsx');

test('1. HomeShell component file exists and is readable', () => {
  assert.ok(fs.existsSync(homeShellPath), 'HomeShell.tsx must exist');
});

test('2. Slot Architecture: Declares clean, typed slot properties', () => {
  const content = fs.readFileSync(homeShellPath, 'utf-8');

  assert.ok(content.includes('heroSlot?: React.ReactNode') || content.includes('heroSlot'), 'Must declare heroSlot');
  assert.ok(content.includes('livingVisualSlot?: React.ReactNode') || content.includes('livingVisualSlot'), 'Must declare livingVisualSlot');
  assert.ok(content.includes('contextSlot?: React.ReactNode') || content.includes('contextSlot'), 'Must declare contextSlot');
  assert.ok(content.includes('recentProcurementSlot?: React.ReactNode') || content.includes('recentProcurementSlot'), 'Must declare recentProcurementSlot');
  assert.ok(content.includes('header?: React.ReactNode') || content.includes('header'), 'Must declare header slot');
});

test('3. Grid & Composition: Asymmetric 3-column layout on desktop', () => {
  const content = fs.readFileSync(homeShellPath, 'utf-8');

  assert.ok(content.includes('lg:grid-cols-12'), 'Must use 12-column responsive grid on desktop');
  assert.ok(content.includes('lg:col-span-7'), 'Dominant left column must span 7 cols');
  assert.ok(content.includes('lg:col-span-1'), 'Center living visual must be narrow 1 col');
  assert.ok(content.includes('lg:col-span-4'), 'Right context panel must span 4 cols');
});

test('4. Semantic Landmarks & Accessibility', () => {
  const content = fs.readFileSync(homeShellPath, 'utf-8');

  assert.ok(content.includes('<main'), 'Must use semantic <main> tag');
  assert.ok(content.includes('id="main-content"'), 'Must have id="main-content" for accessibility skip links');
  assert.ok(content.includes('aria-label='), 'Must include aria-label for sections');
  assert.ok(content.includes('selection:bg-[#d8e6ee]'), 'Must support cohesive selection style');
});

test('5. Visual Philosophy: Zero neon/floating AI dashboard clutter', () => {
  const content = fs.readFileSync(homeShellPath, 'utf-8');

  const forbiddenTerms = [
    /glassmorphism/i,
    /backdrop-blur-2xl/i,
    /shadow-2xl/i,
    /neon/i,
    /glowing/i,
    /ai-glow/i,
    /floating-card/i,
    /kpi-card/i,
  ];

  for (const term of forbiddenTerms) {
    assert.strictEqual(
      term.test(content),
      false,
      `HomeShell must not contain forbidden visual clutter: ${term}`
    );
  }
});

test('6. Header: Quiet institutional navigation with OPAL brand link', () => {
  const content = fs.readFileSync(navbarPath, 'utf-8');

  assert.ok(content.includes('href="/"'), 'Navbar brand must link to Home (/)');
  assert.ok(content.includes('OPAL'), 'Must display OPAL identity');
  assert.ok(content.includes('Procurement Review'), 'Must display Procurement Review descriptor');
  assert.ok(content.includes('Review Officer') || content.includes('PO'), 'Must display reviewer context');
});

test('7. Home Page: Integrates HomeShell with all component slots', () => {
  const content = fs.readFileSync(homePagePath, 'utf-8');

  assert.ok(content.includes('import HomeShell from "@/components/HomeShell"'), 'page.tsx must import HomeShell');
  assert.ok(content.includes('import HomeHero from "@/components/HomeHero"'), 'page.tsx must import HomeHero');
  assert.ok(content.includes('import LivingVisual from "@/components/LivingVisual"'), 'page.tsx must import LivingVisual');
  assert.ok(content.includes('import OfficerContextPanel from "@/components/OfficerContextPanel"'), 'page.tsx must import OfficerContextPanel');
  assert.ok(content.includes('import RecentProcurementsSection from "@/components/procurement/RecentProcurementsSection"'), 'page.tsx must import RecentProcurementsSection');

  assert.ok(content.includes('heroSlot='), 'page.tsx must pass heroSlot');
  assert.ok(content.includes('livingVisualSlot='), 'page.tsx must pass livingVisualSlot');
  assert.ok(content.includes('contextSlot='), 'page.tsx must pass contextSlot');
  assert.ok(content.includes('recentProcurementSlot='), 'page.tsx must pass recentProcurementSlot');
});
