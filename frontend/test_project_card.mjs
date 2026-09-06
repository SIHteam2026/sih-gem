import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test("ProjectCard component file exists", () => {
  const cardPath = path.join(__dirname, "src", "components", "procurement", "ProjectCard.tsx");
  assert.ok(fs.existsSync(cardPath), "ProjectCard.tsx must exist");
});

test("ProjectCard contains strict 4-element hierarchy and digital case file structure", () => {
  const cardPath = path.join(__dirname, "src", "components", "procurement", "ProjectCard.tsx");
  const content = fs.readFileSync(cardPath, "utf8");

  // 1. PROJECT NAME: Dominant headline with line clamping
  assert.match(content, /resolvedTitle|procurement\??\.title|title/, "Card must render procurement title as dominant element");
  assert.match(content, /line-clamp-2/, "Project title must wrap gracefully with 2-line clamp");
  assert.match(content, /font-semibold/, "Project title must have strong visual weight");

  // 2. DEPARTMENT / ORGANIZATION: Secondary subtitle directly below
  assert.match(content, /organization|Department of Procurement/, "Card must display department / organization");
  assert.match(content, /text-xs|text-sm/, "Organization text must be smaller secondary text");

  // 3. LOADED DATE: Tertiary quiet metadata
  assert.match(content, /formatLoadedDate/, "Card must format loaded date quietly");
  assert.match(content, /text-xs.*#9ca3af|text-xs.*text-/, "Date must use quiet, subdued tertiary styling");

  // 4. DYNAMIC STATE TAG: NEW or DRAFT with subtle, non-red/green styling
  assert.match(content, /"NEW"/, "Card must handle NEW state tag");
  assert.match(content, /"DRAFT"/, "Card must handle DRAFT state tag");
  assert.match(content, /NEW/, "Must display NEW label");
  assert.match(content, /DRAFT/, "Must display DRAFT label");

  // Interactive link to canonical procurement case route
  assert.match(content, /<Link/, "Entire card must be a semantic Next.js Link container");
  assert.match(content, /\/procurements\//, "Link href must target /procurements/[id]");
  assert.match(content, /focus-ring|focus-visible:/, "Card must have accessible focus state styling");

  // Prohibited KPI and dashboard elements
  assert.doesNotMatch(content, /risk_score|Risk Score/i, "Card must not contain risk score widgets");
  assert.doesNotMatch(content, /confidence|AI Confidence/i, "Card must not contain AI confidence bars");
  assert.doesNotMatch(content, /progressbar|<progress/i, "Card must not contain progress bars");
  assert.doesNotMatch(content, /pie-chart|recharts/i, "Card must not contain dashboard charts");
});

test("Workspace page integrates ProjectCard in a responsive 2-column grid", () => {
  const pagePath = path.join(__dirname, "src", "app", "procurements", "page.tsx");
  const content = fs.readFileSync(pagePath, "utf8");

  // Verify import of ProjectCard
  assert.match(content, /import ProjectCard.*from ["']@\/components\/procurement\/ProjectCard["']/, "Page must import ProjectCard");

  // Verify 2-column grid layout
  assert.match(content, /grid.*md:grid-cols-2/, "Workspace must lay out cards in a 2-column grid on desktop");
  assert.match(content, /gap-5|gap-6/, "Grid must have comfortable spacing between cards");

  // Verify ProjectCard is rendered for each procurement item
  assert.match(content, /<ProjectCard/, "Workspace page must render ProjectCard components");
});
