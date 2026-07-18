export type Surface =
  "aria" | "handoff" | "capabilities" | "recall" | "graph" | "timeline" | "audit";

export type AriaCommand =
  | {name: "navigate_surface"; arguments: {surface: Surface}}
  | {name: "scroll_page"; arguments: {direction: "up" | "down" | "top" | "bottom"; amount?: "small" | "page"}}
  | {name: "scroll_to"; arguments: {target: "heading" | "content" | "composer" | "results"}}
  | {name: "open_evidence"; arguments: {source_id: string}}
  | {name: "close_evidence"; arguments: Record<string, never>}
  | {name: "focus_graph_node"; arguments: {source_id: string}}
  | {name: "fit_graph"; arguments: {mode: "active" | "all"}}
  | {name: "select_session"; arguments: {session_id: string}}
  | {name: "run_recall"; arguments: {query: string}}
  | {name: "set_deep_synthesis"; arguments: {enabled: boolean}}
  | {name: "open_context_packet"; arguments: Record<string, never>}
  | {name: "start_guided_tour"; arguments: Record<string, never>}
  | {name: "tour_next"; arguments: Record<string, never>}
  | {name: "tour_back"; arguments: Record<string, never>}
  | {name: "tour_repeat"; arguments: Record<string, never>}
  | {name: "tour_stop"; arguments: Record<string, never>}
  | {name: "draft_memory_proposal"; arguments: {
    title: string; content: string; rationale: string;
  }}
  | {name: "approve_handoff"; arguments: {confirmation_phrase: string}};

export type CommandResult = {
  ok: boolean;
  message: string;
  surface?: Surface;
  requires_human_confirmation?: boolean;
};

export type CommandDependencies = {
  navigate: (surface: Surface) => Promise<void>;
  scrollPage: (direction: "up" | "down" | "top" | "bottom", amount: "small" | "page") => Promise<void>;
  scrollTo: (target: "heading" | "content" | "composer" | "results") => Promise<void>;
  openEvidence: (id: string) => Promise<boolean>;
  closeEvidence: () => Promise<void>;
  graph: (action: "focus" | "fit-active" | "fit-all", id?: string) => Promise<boolean>;
  selectSession: (id: string) => Promise<boolean>;
  runRecall: (query: string) => Promise<void>;
  setDeepSynthesis: (enabled: boolean) => Promise<void>;
  openContextPacket: () => Promise<boolean>;
  tour: (action: "start" | "next" | "back" | "repeat" | "stop") => Promise<void>;
  draftProposal: (title: string, content: string, rationale: string) => Promise<string>;
  publishHandoff?: () => Promise<string | null>;
};

const emptyObject = {type: "object", properties: {}, additionalProperties: false};

export const ariaVoiceTools = [
  {
    type: "function", name: "navigate_surface",
    description: "Open one of the five Command Center surfaces.",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {surface: {type: "string", enum: [
        "aria", "handoff", "capabilities", "recall", "graph", "timeline", "audit",
      ]}},
      required: ["surface"],
    },
  },
  {
    type: "function", name: "approve_handoff",
    description: "Publish the currently visible draft handoff only after the user says the exact phrase “Approve this handoff.”",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {confirmation_phrase: {
        type: "string",
        description: "The user's exact spoken phrase. Must be: Approve this handoff.",
      }},
      required: ["confirmation_phrase"],
    },
  },
  {
    type: "function", name: "scroll_page",
    description: "Scroll the current surface. Use top or bottom for an absolute jump.",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {
        direction: {type: "string", enum: ["up", "down", "top", "bottom"]},
        amount: {type: "string", enum: ["small", "page"]},
      },
      required: ["direction"],
    },
  },
  {
    type: "function", name: "scroll_to",
    description: "Move to a named region of the current surface.",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {target: {type: "string", enum: ["heading", "content", "composer", "results"]}},
      required: ["target"],
    },
  },
  {
    type: "function", name: "open_evidence",
    description: "Open an evidence drawer by a cited memory or document source ID.",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {source_id: {type: "string", description: "An evidence ID such as doc_command_center or fact_cc_07."}},
      required: ["source_id"],
    },
  },
  {type: "function", name: "close_evidence", description: "Close the evidence drawer.", parameters: emptyObject},
  {
    type: "function", name: "focus_graph_node",
    description: "Open the graph and center a source node.",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {source_id: {type: "string"}},
      required: ["source_id"],
    },
  },
  {
    type: "function", name: "fit_graph",
    description: "Fit either the active evidence subgraph or the complete graph.",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {mode: {type: "string", enum: ["active", "all"]}},
      required: ["mode"],
    },
  },
  {
    type: "function", name: "select_session",
    description: "Select an Aria session by its exact visible session ID.",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {session_id: {type: "string"}},
      required: ["session_id"],
    },
  },
  {
    type: "function", name: "run_recall",
    description: "Open Recall Explorer and run an evidence search.",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {query: {type: "string"}},
      required: ["query"],
    },
  },
  {
    type: "function", name: "set_deep_synthesis",
    description: "Turn GPT-5.6 Sol Deep Synthesis on or off in Aria.",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {enabled: {type: "boolean"}},
      required: ["enabled"],
    },
  },
  {type: "function", name: "open_context_packet", description: "Open the latest bounded context packet.", parameters: emptyObject},
  {type: "function", name: "start_guided_tour", description: "Start Aria's interactive Command Center tour.", parameters: emptyObject},
  {type: "function", name: "tour_next", description: "Advance the guided tour.", parameters: emptyObject},
  {type: "function", name: "tour_back", description: "Go back one guided-tour step.", parameters: emptyObject},
  {type: "function", name: "tour_repeat", description: "Repeat the current guided-tour explanation.", parameters: emptyObject},
  {type: "function", name: "tour_stop", description: "Stop the guided tour.", parameters: emptyObject},
  {
    type: "function", name: "draft_memory_proposal",
    description: "Create a pending decision proposal for browser review. This never confirms a durable write.",
    parameters: {
      type: "object", additionalProperties: false,
      properties: {
        title: {type: "string"},
        content: {type: "string"},
        rationale: {type: "string"},
      },
      required: ["title", "content", "rationale"],
    },
  },
] as const;

export const ARIA_VOICE_INSTRUCTIONS = `You are Aria, the voice guide for Command Center.
Be warm, concise, and evidence-conscious. Use tools whenever the user asks to navigate,
scroll, inspect evidence, manipulate the graph, run recall, or control the guided tour.
After a tool returns, briefly describe what is now visible. Never claim an interface action
finished before its tool result says it did. You may draft a pending memory proposal, but
you must never confirm or imply confirmation of a durable write. Tell the user that durable
memory requires an explicit browser tap. You may publish a bounded handoff only when
the user says the exact phrase “Approve this handoff.” Publication cannot edit code,
install tools, confirm memory, or perform external actions. Never ask for or repeat secrets.`;

export function ariaRealtimeSessionUpdate() {
  return {
    type: "session.update",
    session: {
      type: "realtime",
      instructions: ARIA_VOICE_INSTRUCTIONS,
      tools: ariaVoiceTools,
      tool_choice: "auto",
    },
  } as const;
}

export async function executeAriaCommand(
  command: AriaCommand,
  dependencies: CommandDependencies,
): Promise<CommandResult> {
  switch (command.name) {
    case "navigate_surface":
      await dependencies.navigate(command.arguments.surface);
      return {
        ok: true,
        message: `Opened ${command.arguments.surface}.`,
        surface: command.arguments.surface,
      };
    case "scroll_page":
      await dependencies.scrollPage(
        command.arguments.direction,
        command.arguments.amount ?? "page",
      );
      return {ok: true, message: `Scrolled ${command.arguments.direction}.`};
    case "scroll_to":
      await dependencies.scrollTo(command.arguments.target);
      return {ok: true, message: `Moved to ${command.arguments.target}.`};
    case "open_evidence": {
      const opened = await dependencies.openEvidence(command.arguments.source_id);
      return {ok: opened, message: opened
        ? `Opened evidence ${command.arguments.source_id}.`
        : `Evidence ${command.arguments.source_id} was not found.`};
    }
    case "close_evidence":
      await dependencies.closeEvidence();
      return {ok: true, message: "Closed the evidence drawer."};
    case "focus_graph_node": {
      await dependencies.navigate("graph");
      const focused = await dependencies.graph("focus", command.arguments.source_id);
      return {ok: focused, message: focused
        ? `Focused graph node ${command.arguments.source_id}.`
        : `Graph node ${command.arguments.source_id} was not found.`, surface: "graph"};
    }
    case "fit_graph":
      await dependencies.navigate("graph");
      await dependencies.graph(command.arguments.mode === "active" ? "fit-active" : "fit-all");
      return {
        ok: true,
        message: `Fitted the ${command.arguments.mode} graph.`,
        surface: "graph",
      };
    case "select_session": {
      const selected = await dependencies.selectSession(command.arguments.session_id);
      return {ok: selected, message: selected
        ? `Selected session ${command.arguments.session_id}.`
        : `Session ${command.arguments.session_id} was not found.`};
    }
    case "run_recall":
      await dependencies.runRecall(command.arguments.query);
      return {
        ok: true,
        message: `Recall completed for “${command.arguments.query}”.`,
        surface: "recall",
      };
    case "set_deep_synthesis":
      await dependencies.navigate("aria");
      await dependencies.setDeepSynthesis(command.arguments.enabled);
      return {
        ok: true,
        message: `Deep Synthesis is ${command.arguments.enabled ? "on" : "off"}.`,
        surface: "aria",
      };
    case "open_context_packet": {
      await dependencies.navigate("aria");
      const opened = await dependencies.openContextPacket();
      return {ok: opened, message: opened
        ? "Opened the latest bounded context packet."
        : "There is no context packet to open yet.", surface: "aria"};
    }
    case "approve_handoff": {
      if (command.arguments.confirmation_phrase.trim().toLowerCase().replace(/[.!]+$/, "")
        !== "approve this handoff") {
        return {
          ok: false,
          message: "Say the exact phrase “Approve this handoff.” to publish.",
          surface: "handoff",
        };
      }
      const handoffId = await (dependencies.publishHandoff?.() ?? Promise.resolve(null));
      return {
        ok: Boolean(handoffId),
        message: handoffId
          ? `Published handoff ${handoffId}. Read the exact Codex command shown in the builder.`
          : "There is no draft handoff ready to publish.",
        surface: "handoff",
      };
    }
    case "start_guided_tour":
    case "tour_next":
    case "tour_back":
    case "tour_repeat":
    case "tour_stop": {
      const action = command.name === "start_guided_tour" ? "start"
        : command.name === "tour_next" ? "next"
          : command.name === "tour_back" ? "back"
            : command.name === "tour_repeat" ? "repeat" : "stop";
      await dependencies.tour(action);
      return {ok: true, message: action === "stop"
        ? "Stopped the guided tour." : `Guided tour: ${action}.`};
    }
    case "draft_memory_proposal": {
      const proposalId = await dependencies.draftProposal(
        command.arguments.title,
        command.arguments.content,
        command.arguments.rationale,
      );
      return {
        ok: true,
        message: `Created pending proposal ${proposalId}. It requires an explicit browser confirmation.`,
        surface: "aria",
        requires_human_confirmation: true,
      };
    }
  }
}

export function parseAriaCommand(name: string, rawArguments: string): AriaCommand {
  const tool = ariaVoiceTools.find((candidate) => candidate.name === name);
  if (!tool) throw new Error(`Unknown Aria command: ${name}`);
  const parsed = rawArguments ? JSON.parse(rawArguments) : {};
  return {name, arguments: parsed} as AriaCommand;
}
