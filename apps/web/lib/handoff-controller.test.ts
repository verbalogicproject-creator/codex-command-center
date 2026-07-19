import {describe, expect, it} from "vitest";
import {editOpenPlan} from "./handoff-controller";

describe("bounded Open Plan edits", () => {
  it("supports append, replace, remove, and reorder", () => {
    expect(editOpenPlan(["one", "two"], "append", 0, "middle"))
      .toEqual(["one", "middle", "two"]);
    expect(editOpenPlan(["one", "two"], "replace", 1, "second"))
      .toEqual(["one", "second"]);
    expect(editOpenPlan(["one", "two"], "remove", 0))
      .toEqual(["two"]);
    expect(editOpenPlan(["one", "two", "three"], "reorder", 2, "", 0))
      .toEqual(["three", "one", "two"]);
  });

  it("rejects invalid indices, empty plans, and overflow", () => {
    expect(() => editOpenPlan(["one"], "replace", 2, "bad"))
      .toThrow("out of range");
    expect(() => editOpenPlan(["one"], "remove", 0))
      .toThrow("at least one");
    expect(() => editOpenPlan(
      Array.from({length: 12}, (_, index) => `step ${index}`),
      "append",
      11,
      "overflow",
    )).toThrow("12 steps");
  });
});
