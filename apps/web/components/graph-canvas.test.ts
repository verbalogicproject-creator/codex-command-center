import {describe, expect, it} from "vitest";
import {evidenceEdgeTone} from "./ContextPulseEdge";
import {wrappedDockScrollLeft} from "./InfiniteDock";
import {evidenceNodeTone} from "./MemoryGraph";

describe("evidence canvas semantics", () => {
  it("keeps declared, durable, and injected evidence visually distinct", () => {
    expect(evidenceNodeTone("repository", false)).toBe("declared");
    expect(evidenceNodeTone("declared", false)).toBe("declared");
    expect(evidenceNodeTone("durable", false)).toBe("durable");
    expect(evidenceNodeTone("durable", true)).toBe("context");
  });

  it("animates active context while preserving structural edge tones", () => {
    expect(evidenceEdgeTone({active: true, targetStage: "durable"})).toBe("context");
    expect(evidenceEdgeTone({active: false, targetStage: "declared"})).toBe("declared");
    expect(evidenceEdgeTone({active: false, targetStage: "durable"})).toBe("durable");
    expect(evidenceEdgeTone({active: false})).toBe("structural");
  });
});

describe("infinite dock wrapping", () => {
  it("keeps the viewport inside the middle of three equal segments", () => {
    expect(wrappedDockScrollLeft(99, 100)).toBe(199);
    expect(wrappedDockScrollLeft(100, 100)).toBe(100);
    expect(wrappedDockScrollLeft(175, 100)).toBe(175);
    expect(wrappedDockScrollLeft(200, 100)).toBe(100);
    expect(wrappedDockScrollLeft(0, 0)).toBe(0);
  });
});
