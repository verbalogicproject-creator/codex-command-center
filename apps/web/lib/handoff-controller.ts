import type {Handoff} from "./types";

export type PlanEditOperation = "append" | "replace" | "remove" | "reorder";

export type HandoffControllerResult = {
  ok: boolean;
  message: string;
  surface?: "handoff";
  handoff?: Handoff | null;
};

export type HandoffController = {
  startSession: (repository: string, intent: string) => Promise<HandoffControllerResult>;
  prepare: () => Promise<HandoffControllerResult>;
  selectCapability: (capabilityRef: string) => Promise<HandoffControllerResult>;
  editPlan: (
    operation: PlanEditOperation,
    index: number,
    text?: string,
    destination?: number,
  ) => Promise<HandoffControllerResult>;
  openPacket: () => Promise<HandoffControllerResult>;
  publish: () => Promise<HandoffControllerResult>;
};

export function editOpenPlan(
  plan: string[],
  operation: PlanEditOperation,
  index: number,
  text = "",
  destination?: number,
): string[] {
  if (!Number.isInteger(index)) throw new Error("Plan index must be an integer.");
  const next = [...plan];
  if (operation === "append") {
    const value = text.trim();
    if (!value) throw new Error("A plan step is required.");
    if (index < -1 || index >= next.length) throw new Error("Plan index is out of range.");
    next.splice(index + 1, 0, value);
  } else {
    if (index < 0 || index >= next.length) throw new Error("Plan index is out of range.");
    if (operation === "replace") {
      const value = text.trim();
      if (!value) throw new Error("A replacement plan step is required.");
      next[index] = value;
    } else if (operation === "remove") {
      next.splice(index, 1);
    } else {
      if (destination === undefined || !Number.isInteger(destination)
        || destination < 0 || destination >= next.length) {
        throw new Error("Plan destination is out of range.");
      }
      const [moved] = next.splice(index, 1);
      next.splice(destination, 0, moved);
    }
  }
  if (!next.length) throw new Error("The Open Plan must keep at least one step.");
  if (next.length > 12) throw new Error("The Open Plan cannot exceed 12 steps.");
  if (next.some((step) => step.length > 500)) {
    throw new Error("Open Plan steps cannot exceed 500 characters.");
  }
  return next;
}
