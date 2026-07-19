import {describe, expect, it, vi} from "vitest";
import {
  ariaRealtimeSessionUpdate, CommandDependencies, executeAriaCommand, parseAriaCommand,
} from "./commands";

function dependencies(): CommandDependencies {
  return {
    navigate: vi.fn(async () => undefined),
    scrollPage: vi.fn(async () => undefined),
    scrollTo: vi.fn(async () => undefined),
    openEvidence: vi.fn(async () => true),
    closeEvidence: vi.fn(async () => undefined),
    graph: vi.fn(async () => true),
    selectSession: vi.fn(async () => true),
    runRecall: vi.fn(async () => undefined),
    setDeepSynthesis: vi.fn(async () => undefined),
    openContextPacket: vi.fn(async () => true),
    tour: vi.fn(async () => undefined),
    draftProposal: vi.fn(async () => "prop_voice"),
    startRedesignSession: vi.fn(async () => ({
      ok: true, message: "Started.", surface: "handoff" as const,
    })),
    prepareRedesignHandoff: vi.fn(async () => ({
      ok: true, message: "Prepared.", surface: "handoff" as const,
    })),
    selectHandoffCapability: vi.fn(async () => ({
      ok: true, message: "Selected.", surface: "handoff" as const,
    })),
    editOpenPlan: vi.fn(async () => ({
      ok: true, message: "Edited.", surface: "handoff" as const,
    })),
    openHandoffPacket: vi.fn(async () => ({
      ok: true, message: "Opened.", surface: "handoff" as const,
    })),
    publishHandoff: vi.fn(async () => ({
      ok: true, message: "Published handoff hoff_voice.", surface: "handoff" as const,
    })),
  };
}

describe("Aria command router", () => {
  it("declares the Realtime session union type during updates", () => {
    const update = ariaRealtimeSessionUpdate();
    expect(update.type).toBe("session.update");
    expect(update.session.type).toBe("realtime");
  });

  it("routes graph focus through navigation and waits for the graph command", async () => {
    const deps = dependencies();
    const result = await executeAriaCommand({
      name: "focus_graph_node", arguments: {source_id: "fact_cc_07"},
    }, deps);
    expect(deps.navigate).toHaveBeenCalledWith("graph");
    expect(deps.graph).toHaveBeenCalledWith("focus", "fact_cc_07");
    expect(result.ok).toBe(true);
  });

  it("marks voice-created proposals as pending human work", async () => {
    const result = await executeAriaCommand({
      name: "draft_memory_proposal",
      arguments: {title: "Boundary", content: "Keep browser confirmation.", rationale: "Safety"},
    }, dependencies());
    expect(result.requires_human_confirmation).toBe(true);
    expect(result.message).toContain("explicit browser confirmation");
  });

  it("rejects commands outside the declared catalog", () => {
    expect(() => parseAriaCommand("confirm_memory_write", "{}"))
      .toThrow("Unknown Aria command");
  });

  it("requires the exact handoff publication phrase", async () => {
    const deps = dependencies();
    const refused = await executeAriaCommand({
      name: "approve_handoff", arguments: {confirmation_phrase: "publish it"},
    }, deps);
    expect(refused.ok).toBe(false);
    expect(deps.publishHandoff).not.toHaveBeenCalled();
    const wrongCase = await executeAriaCommand({
      name: "approve_handoff", arguments: {confirmation_phrase: "approve this handoff."},
    }, deps);
    expect(wrongCase.ok).toBe(false);

    const approved = await executeAriaCommand({
      name: "approve_handoff",
      arguments: {confirmation_phrase: "Approve this handoff."},
    }, deps);
    expect(approved.ok).toBe(true);
    expect(deps.publishHandoff).toHaveBeenCalledOnce();
  });

  it("routes reversible redesign draft controls without publication", async () => {
    const deps = dependencies();
    const prepared = await executeAriaCommand({
      name: "prepare_redesign_handoff", arguments: {},
    }, deps);
    expect(prepared.ok).toBe(true);
    expect(deps.prepareRedesignHandoff).toHaveBeenCalledOnce();
    expect(deps.publishHandoff).not.toHaveBeenCalled();

    await executeAriaCommand({
      name: "edit_open_plan",
      arguments: {operation: "replace", index: 1, text: "Verify reduced motion."},
    }, deps);
    expect(deps.editOpenPlan).toHaveBeenCalledWith(
      "replace", 1, "Verify reduced motion.", undefined,
    );
  });

  it("can start the redesign-specific guided tour", async () => {
    const deps = dependencies();
    await executeAriaCommand({
      name: "start_guided_tour", arguments: {mode: "redesign"},
    }, deps);
    expect(deps.tour).toHaveBeenCalledWith("start", "redesign");
  });
});
