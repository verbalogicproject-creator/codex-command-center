import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {describe, expect, it} from "vitest";

const html = readFileSync(resolve(process.cwd(), "public/atlas/index.html"), "utf8");
const page = readFileSync(resolve(process.cwd(), "app/page.tsx"), "utf8");

function atlasData() {
  const match = html.match(
    /<script id="atlas-data" type="application\/json">([\s\S]+?)<\/script>/,
  );
  if (!match) throw new Error("Atlas data payload was not found.");
  return JSON.parse(match[1]) as {
    schema_version: string;
    climax_claim_id: string;
    migration: number;
    counts: Record<string, number>;
    claims: {id: string; source_ids: string[]}[];
    sources: {id: string; claim_ids: string[]}[];
  };
}

describe("Take a step back atlas", () => {
  it("ships the progressive judge path at the static atlas target", () => {
    expect(page).toContain('href="/atlas/index.html"');
    expect(html).toContain("<title>Take a step back");
    expect(html).toContain("NLKE Grounded Continuity Architecture");
    expect(html).toContain('id="grounding"');
    expect(html).toContain('id="compiler"');
    expect(html).toContain('id="boundaries"');
    expect(html).toContain('id="explorer"');
    expect(html).toContain('id="lineage"');
    expect(html).toContain('data-lens="claims"');
    expect(html).toContain('data-lens="sources"');
  });

  it("embeds bidirectional, migration-8 source truth", () => {
    const data = atlasData();
    expect(data.schema_version).toBe("nlke-gca-grounding-receipt-v1");
    expect(data.climax_claim_id).toBe("immutable-handoff");
    expect(data.migration).toBe(8);
    expect(data.counts.modules).toBeGreaterThan(20);
    expect(data.counts.routes).toBeGreaterThan(60);
    expect(data.counts.tests).toBeGreaterThan(100);
    const sources = new Map(data.sources.map((source) => [source.id, source]));
    for (const claim of data.claims) {
      expect(claim.source_ids.length).toBeGreaterThan(0);
      expect(claim.source_ids.every((id) => sources.get(id)?.claim_ids.includes(claim.id)))
        .toBe(true);
    }
  });

  it("keeps mobile layout and reduced-motion boundaries explicit", () => {
    expect(html).toContain("overflow-x:hidden");
    expect(html).toContain("@media(max-width:680px)");
    expect(html).toContain("@media(prefers-reduced-motion:reduce)");
    expect(html).toContain('class="skip"');
  });
});
