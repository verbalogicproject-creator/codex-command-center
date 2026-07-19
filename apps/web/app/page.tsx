"use client";

import {
  FormEvent, ReactNode, useCallback, useEffect, useMemo, useRef, useState,
} from "react";
import {
  Activity, Archive, BrainCircuit, Boxes, Check, CircleHelp, Clock3, Command,
  GitBranch, KeyRound, Menu, Link2, MessageSquareText, Plus, Search, Send, ShieldCheck,
  Sparkles, Upload, Workflow, X,
} from "lucide-react";
import {api, apiUrl, readSSE} from "@/lib/api";
import type {
  ArchitectureBrief, Audit, Capability, ContextPack, DeclaredDocument, GraphData,
  Handoff, Memory, Proposal, ProviderCredentialStatus, RecallHit,
  RedesignSuggestion, ScreenshotAnalysis, Session, TourScript, TourStep, Trace,
} from "@/lib/types";
import {MemoryGraph} from "@/components/MemoryGraph";
import {InfiniteDock} from "@/components/InfiniteDock";
import {AriaVoice} from "@/components/AriaVoice";
import {
  AriaCommand, executeAriaCommand, Surface,
} from "@/lib/aria/commands";
import {
  editOpenPlan, HandoffController, HandoffControllerResult,
} from "@/lib/handoff-controller";

type ChatItem = {role: "user" | "assistant"; text: string};
type RenderBlock = {title: string; summary: string; evidence_ids?: string[]; projects?: string[]};

const surfaces: {id: Surface; label: string; shortLabel: string; icon: typeof Sparkles}[] = [
  {id: "aria", label: "Aria", shortLabel: "Aria", icon: Sparkles},
  {id: "handoff", label: "Handoff Builder", shortLabel: "Handoff", icon: Workflow},
  {id: "capabilities", label: "Capability Library", shortLabel: "Toolbox", icon: Boxes},
  {id: "recall", label: "Recall Explorer", shortLabel: "Recall", icon: Search},
  {id: "graph", label: "Knowledge Graph", shortLabel: "Graph", icon: GitBranch},
  {id: "timeline", label: "Sessions / Timeline", shortLabel: "Timeline", icon: Clock3},
  {id: "audit", label: "Audit", shortLabel: "Audit", icon: ShieldCheck},
];

const overviewTourSteps: TourStep[] = [
  {
    id: "overview-aria", surface: "aria", target: "heading", evidence_ids: [],
    action: "Meet Aria",
    narration: "Ask across development memory. Aria answers from bounded evidence and shows exactly what was injected.",
  },
  {
    id: "overview-recall", surface: "recall", target: "results", evidence_ids: [],
    action: "Inspect retrieval",
    narration: "Recall Explorer reveals ranked evidence and the lexical, structural, and dense signals behind it.",
  },
  {
    id: "overview-graph", surface: "graph", target: "content", evidence_ids: [],
    action: "Watch context assemble",
    narration: "Violet is declared structure, cyan is active context, and amber is durable human-confirmed memory.",
  },
  {
    id: "overview-timeline", surface: "timeline", target: "content", evidence_ids: [],
    action: "Follow the history",
    narration: "Sessions and durable records stay distinct, so you can see what happened without confusing chat with memory.",
  },
  {
    id: "overview-audit", surface: "audit", target: "content", evidence_ids: [],
    action: "The approval boundary",
    narration: "Models can draft pending proposals. Only your explicit browser action can confirm a durable write.",
  },
];

function afterPaint(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
}

export default function Page() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [surface, setSurface] = useState<Surface>("aria");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState("");
  const [timeline, setTimeline] = useState<Memory[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [graph, setGraph] = useState<GraphData>({nodes: [], edges: []});
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [handoffs, setHandoffs] = useState<Handoff[]>([]);
  const [activeHandoffId, setActiveHandoffId] = useState("");
  const [selected, setSelected] = useState<Memory | DeclaredDocument | null>(null);
  const [evidenceIds, setEvidenceIds] = useState<string[]>([]);
  const [palette, setPalette] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [pairCode, setPairCode] = useState("");
  const [pairError, setPairError] = useState("");
  const [credentialPanel, setCredentialPanel] = useState(false);
  const [providerCredential, setProviderCredential] =
    useState<ProviderCredentialStatus | null>(null);
  const [tourStep, setTourStep] = useState<number | null>(null);
  const tourStepRef = useRef<number | null>(null);
  const [tourScript, setTourScript] = useState<TourScript | null>(null);
  const tourScriptRef = useRef<TourScript | null>(null);
  const tourFocusRef = useRef<HTMLElement | null>(null);
  const handoffControllerRef = useRef<HandoffController | null>(null);

  const refresh = useCallback(async () => {
    try {
      await api("/api/v1/status");
      setAuthenticated(true);
      const [
        sessionData, timeData, auditData, graphData, capabilityData, handoffData,
        credentialData,
      ] = await Promise.all([
        api<{items: Session[]}>("/api/v1/sessions"),
        api<{items: Memory[]}>("/api/v1/timeline?limit=120"),
        api<{items: Audit[]}>("/api/v1/audit"),
        api<GraphData>("/api/v1/graph"),
        api<{items: Capability[]}>("/api/v1/capabilities"),
        api<{items: Handoff[]}>("/api/v1/handoffs"),
        api<ProviderCredentialStatus>("/api/v1/provider-credentials/openai/status"),
      ]);
      setSessions(sessionData.items);
      setTimeline(timeData.items);
      setAudit(auditData.items);
      setGraph(graphData);
      setCapabilities(capabilityData.items);
      setHandoffs(handoffData.items);
      setProviderCredential(credentialData);
      const activeDraft = handoffData.items.find((item) => item.status === "draft");
      if (activeDraft) setActiveHandoffId(activeDraft.id);
      if (!activeSession && sessionData.items[0]) setActiveSession(sessionData.items[0].id);
    } catch {
      setAuthenticated(false);
    }
  }, [activeSession]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPalette((value) => !value);
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);

  async function createSession() {
    const session = await api<Session>("/api/v1/sessions", {
      method: "POST", body: JSON.stringify({title: "Architecture synthesis"}),
    });
    setSessions((items) => [session, ...items]);
    setActiveSession(session.id);
    setSurface("aria");
  }

  async function startPairing() {
    setPairError("");
    try {
      const result = await api<{code: string; expires_in_seconds: number}>(
        "/api/v1/auth/pair/start", {method: "POST"},
      );
      setPairCode(result.code);
    } catch (reason) {
      setPairError(reason instanceof Error ? reason.message : "Could not create a pairing code.");
    }
  }

  async function openEvidence(id: string): Promise<boolean> {
    if (id.startsWith("adoc_") || id.startsWith("asec_")) {
      try {
        const response = await api<{
          result: {structuredContent: {
            entity_type: "architecture_document" | "architecture_section";
            evidence: Record<string, unknown>;
          }};
        }>("/mcp", {
          method: "POST",
          body: JSON.stringify({
            jsonrpc: "2.0", id: "browser-evidence", method: "tools/call",
            params: {name: "get_evidence", arguments: {source_id: id}},
          }),
        });
        const {entity_type: entityType, evidence} = response.result.structuredContent;
        const declaration = (evidence.declaration ?? {}) as Record<string, unknown>;
        const strings = (key: string) => (
          Array.isArray(declaration[key]) ? declaration[key] as string[] : []
        );
        setSelected({
          id: String(evidence.id),
          source_uri: String(evidence.source_uri ?? "versioned architecture section"),
          repository: String(
            declaration.repository ?? evidence.snapshot_id ?? "Architecture snapshot"
          ),
          title: String(
            evidence.title ?? evidence.heading
            ?? (entityType === "architecture_section" ? "Architecture section" : "Architecture document")
          ),
          body: String(evidence.body ?? ""),
          provides: strings("provides"),
          public_interfaces: strings("public_interfaces"),
          safe_edit_points: strings("safe_edit_points"),
          risk_areas: strings("risk_areas"),
          graph_rag_entities: strings("graph_rag_entities"),
          depends_on: strings("depends_on"),
          main_files: strings("main_files"),
          kind: String(declaration.kind ?? entityType),
          status: String(declaration.status ?? "versioned"),
          owner_area: String(declaration.owner_area ?? ""),
          audience: Array.isArray(declaration.audience)
            ? (declaration.audience as string[]).join(", ")
            : String(declaration.audience ?? ""),
          last_verified: evidence.last_verified
            ? String(evidence.last_verified) : undefined,
        });
        return true;
      } catch {
        setSelected(null);
        return false;
      }
    }
    if (id.startsWith("doc_")) {
      try {
        setSelected(await api<DeclaredDocument>(`/api/v1/documents/${id}`));
        return true;
      } catch {
        setSelected(null);
        return false;
      }
    }
    const local = timeline.find((item) => item.id === id);
    if (local) {
      setSelected(local);
      return true;
    }
    const kind = graph.nodes.find((item) => item.id === id)?.type === "episode"
      ? "episodes" : "facts";
    try {
      setSelected(await api<Memory>(`/api/v1/memories/${kind}/${id}`));
      return true;
    } catch {
      setSelected(null);
      return false;
    }
  }

  const voiceCommand = useCallback(async (command: AriaCommand) => {
    const navigate = async (next: Surface) => {
      setSurface(next);
      await afterPaint();
    };
    const dispatch = async (name: string, detail?: unknown) => {
      window.dispatchEvent(new CustomEvent(name, {detail}));
      await afterPaint();
    };
    const scrollContainer = () => (
      document.querySelector<HTMLElement>(".surface .conversation")
      ?? document.querySelector<HTMLElement>(".surface .results")
      ?? document.querySelector<HTMLElement>(".surface .chronology")
      ?? document.querySelector<HTMLElement>(".surface .audit-table")
      ?? document.scrollingElement
    );
    return executeAriaCommand(command, {
      navigate,
      scrollPage: async (direction, amount) => {
        const container = scrollContainer();
        if (!container) return;
        const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "auto" : "smooth";
        if (direction === "top" || direction === "bottom") {
          container.scrollTo({
            top: direction === "top" ? 0 : container.scrollHeight,
            behavior,
          });
        } else {
          const distance = amount === "small" ? 240 : Math.max(320, container.clientHeight * .82);
          container.scrollBy({top: direction === "down" ? distance : -distance, behavior});
        }
        await afterPaint();
      },
      scrollTo: async (target) => {
        document.querySelector<HTMLElement>(`[data-aria-target="${target}"]`)
          ?.scrollIntoView({behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "auto" : "smooth", block: "center"});
        await afterPaint();
      },
      openEvidence,
      closeEvidence: async () => {
        setSelected(null);
        await afterPaint();
      },
      graph: async (action, id) => {
        await dispatch("aria:graph-command", {action, id});
        return action !== "focus" || graph.nodes.some((node) =>
          node.id === id || node.evidence_id === id,
        );
      },
      selectSession: async (id) => {
        const exists = sessions.some((session) => session.id === id);
        if (exists) {
          setActiveSession(id);
          setSurface("aria");
          setRailOpen(false);
          await afterPaint();
        }
        return exists;
      },
      runRecall: async (query) => {
        await navigate("recall");
        await dispatch("aria:run-recall", {query});
      },
      setDeepSynthesis: async (enabled) => {
        await dispatch("aria:set-deep", {enabled});
      },
      openContextPacket: async () => {
        await afterPaint();
        const packet = document.querySelector<HTMLDetailsElement>("[data-aria-target='context-packet']");
        if (!packet) return false;
        packet.open = true;
        packet.scrollIntoView({behavior: "smooth", block: "center"});
        await afterPaint();
        return true;
      },
      tour: async (action, mode = "overview") => {
        if (action === "stop") {
          document.querySelector(".aria-tour-highlight")
            ?.classList.remove("aria-tour-highlight");
          tourStepRef.current = null;
          setTourStep(null);
          tourFocusRef.current?.focus();
          return;
        }
        let script = tourScriptRef.current;
        if (action === "start") {
          tourFocusRef.current = document.activeElement as HTMLElement | null;
          window.dispatchEvent(new CustomEvent("aria:tour-started"));
          try {
            script = await api<TourScript>("/api/v1/tours/script", {
              method: "POST",
              body: JSON.stringify({
                mode,
                repository: "Command Center",
                handoff_id: mode === "redesign" && activeHandoffId
                  ? activeHandoffId : null,
              }),
            });
          } catch {
            script = {
              schema_version: "command-center-tour-script-v1",
              mode: "overview",
              model: "browser-overview-fallback-v1",
              steps: overviewTourSteps,
              generated_at: new Date().toISOString(),
              degraded: true,
              degraded_reasons: ["tour_endpoint_unavailable"],
            };
          }
          tourScriptRef.current = script;
          setTourScript(script);
        }
        const steps = script?.steps ?? overviewTourSteps;
        const current = tourStepRef.current;
        const next = action === "start" ? 0
          : action === "next" ? Math.min((current ?? -1) + 1, steps.length - 1)
            : action === "back" ? Math.max((current ?? 1) - 1, 0)
              : (current ?? 0);
        tourStepRef.current = next;
        setTourStep(next);
        await navigate(steps[next].surface);
        document.querySelector(".aria-tour-highlight")
          ?.classList.remove("aria-tour-highlight");
        const target = document.querySelector<HTMLElement>(
          `[data-aria-target="${steps[next].target}"]`,
        );
        target?.classList.add("aria-tour-highlight");
        target?.scrollIntoView({
          behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "auto" : "smooth",
          block: "center",
        });
      },
      draftProposal: async (title, content, rationale) => {
        const proposal = await api<Proposal>("/api/v1/proposals", {
          method: "POST",
          body: JSON.stringify({
            session_id: activeSession || null,
            operation: "record_fact",
            payload: {
              project: "Command Center",
              kind: "decision",
              status: "active",
              title,
              content,
              reason: rationale,
              tags: ["aria-voice", "pending-review"],
            },
            rationale,
            evidence_ids: evidenceIds,
          }),
        });
        await navigate("aria");
        await dispatch("aria:proposal-created", proposal);
        await refresh();
        return proposal.id;
      },
      startRedesignSession: async (repository, intent) => {
        await navigate("handoff");
        return handoffControllerRef.current?.startSession(repository, intent)
          ?? {ok: false, message: "Handoff Builder is still loading.", surface: "handoff"};
      },
      prepareRedesignHandoff: async () => {
        await navigate("handoff");
        return handoffControllerRef.current?.prepare()
          ?? {ok: false, message: "Handoff Builder is still loading.", surface: "handoff"};
      },
      selectHandoffCapability: async (capabilityRef) => {
        await navigate("handoff");
        return handoffControllerRef.current?.selectCapability(capabilityRef)
          ?? {ok: false, message: "Handoff Builder is still loading.", surface: "handoff"};
      },
      editOpenPlan: async (operation, index, text, destination) => {
        await navigate("handoff");
        return handoffControllerRef.current?.editPlan(
          operation, index, text, destination,
        ) ?? {ok: false, message: "Handoff Builder is still loading.", surface: "handoff"};
      },
      openHandoffPacket: async () => {
        await navigate("handoff");
        return handoffControllerRef.current?.openPacket()
          ?? {ok: false, message: "There is no visible handoff packet.", surface: "handoff"};
      },
      publishHandoff: async () => {
        await navigate("handoff");
        return handoffControllerRef.current?.publish()
          ?? {ok: false, message: "There is no draft handoff ready to publish.", surface: "handoff"};
      },
    });
  }, [activeHandoffId, activeSession, evidenceIds, graph.nodes, refresh, sessions, timeline]);

  if (authenticated === null) return <BootScreen />;
  if (!authenticated) return <Login onSuccess={() => void refresh()} />;

  return (
    <main className="shell">
      <header className="topbar">
        <button className="icon-button mobile-only" onClick={() => setRailOpen((value) => !value)}
          aria-label={railOpen ? "Close sessions" : "Open sessions"}><Menu /></button>
        <div className="brand-mark"><BrainCircuit /></div>
        <div className="brand"><strong>Command Center</strong><span>v3 / Aria</span></div>
        <button className="command-trigger" onClick={() => setPalette(true)}>
          <Command size={15} /><span>Jump to…</span><kbd>⌘ K</kbd>
        </button>
        <button className="pair-trigger" onClick={() => void startPairing()}>
          <Link2 size={14} /><span>Pair Codex</span>
        </button>
        <button
          className={`credential-trigger ${providerCredential?.configured ? "connected" : ""}`}
          onClick={() => setCredentialPanel(true)}
          aria-label={providerCredential?.configured ? "Manage OpenAI key" : "Connect OpenAI key"}
        >
          <KeyRound size={14} />
          <span>{providerCredential?.configured ? "OpenAI ready" : "Connect OpenAI"}</span>
        </button>
        <button className="tour-trigger" onClick={() =>
          void voiceCommand({name: "start_guided_tour", arguments: {}})
        }>
          <CircleHelp size={14} /><span>Tour</span>
        </button>
        <div className="system-state"><i /><span>Memory online</span></div>
      </header>

      {railOpen && <button className="rail-scrim mobile-only" aria-label="Close sessions"
        onClick={() => setRailOpen(false)} />}
      <aside className={`session-rail ${railOpen ? "open" : ""}`}>
        <div className="rail-heading">
          <span>Sessions</span>
          <button className="icon-button mobile-only" onClick={() => setRailOpen(false)}><X /></button>
        </div>
        <button className="new-session" onClick={() => void createSession()}><Plus /> New synthesis</button>
        <div className="session-list">
          {sessions.map((session) => (
            <button key={session.id}
              className={session.id === activeSession ? "active" : ""}
              onClick={() => {setActiveSession(session.id); setRailOpen(false);}}>
              <MessageSquareText />
              <span><strong>{session.title}</strong><small>{session.turn_count} turns</small></span>
            </button>
          ))}
          {!sessions.length && <p className="quiet">Create a session to begin.</p>}
        </div>
        <div className="rail-foot"><span className="aria-orb" /><div><strong>ARIA</strong><small>evidence agent</small></div></div>
      </aside>

      <section className="workspace">
        {surface === "aria" && <AriaSurface
          sessionId={activeSession} onCreateSession={createSession}
          onEvidence={(ids) => {setEvidenceIds(ids); if (ids[0]) void openEvidence(ids[0]);}}
          onRefresh={refresh}
          onPrepareRedesign={async (suggestion) => {
            setSurface("handoff");
            await afterPaint();
            await handoffControllerRef.current?.startSession(
              String(
                suggestion.repository_identity.repository
                ?? suggestion.repository_identity.requested
                ?? "Command Center"
              ),
              suggestion.original_intent,
            );
          }}
        />}
        {surface === "handoff" && <HandoffBuilder
          capabilities={capabilities} handoffs={handoffs}
          activeId={activeHandoffId} onActive={setActiveHandoffId}
          onRefresh={refresh}
          onController={(controller) => { handoffControllerRef.current = controller; }}
          onStartTour={() => void voiceCommand({
            name: "start_guided_tour", arguments: {mode: "redesign"},
          })}
        />}
        {surface === "capabilities" && <CapabilityLibrary items={capabilities} />}
        {surface === "recall" && <RecallSurface onEvidence={(hit) => {
          setSelected(hit.memory); setEvidenceIds((ids) => [...new Set([...ids, hit.memory.id])]);
        }} />}
        {surface === "graph" && <section className="surface graph-surface">
          <SurfaceTitle eyebrow="Relationships" title="Knowledge Graph"
            note={`${graph.nodes.length} semantic nodes · client-laid with Dagre`} />
          <MemoryGraph data={graph} activeIds={[
            ...evidenceIds,
            ...(activeHandoffId ? [`handoff:${activeHandoffId}`] : []),
          ]} onEvidence={(id) => void openEvidence(id)} />
        </section>}
        {surface === "timeline" && <TimelineSurface sessions={sessions} items={timeline}
          onEvidence={setSelected} />}
        {surface === "audit" && <AuditSurface items={audit} />}
      </section>

      <EvidenceDrawer memory={selected} onClose={() => setSelected(null)} />
      <AriaVoice execute={voiceCommand} />
      <InfiniteDock items={surfaces} activeId={surface} onSelect={setSurface} />
      {tourStep !== null && <GuidedTour
        step={tourStep}
        steps={tourScript?.steps ?? overviewTourSteps}
        degraded={Boolean(tourScript?.degraded)}
        onBack={() => void voiceCommand({name: "tour_back", arguments: {}})}
        onNext={() => void voiceCommand({name: "tour_next", arguments: {}})}
        onRepeat={() => void voiceCommand({name: "tour_repeat", arguments: {}})}
        onStop={() => void voiceCommand({name: "tour_stop", arguments: {}})}
      />}
      {palette && <CommandPalette onSelect={(id) => {setSurface(id); setPalette(false);}}
        onClose={() => setPalette(false)} />}
      {(pairCode || pairError) && <aside className="pair-panel">
        <button className="icon-button" onClick={() => {
          setPairCode(""); setPairError("");
        }}><X /></button>
        <span><Link2 /> CODEX PAIRING</span>
        {pairError ? <p className="form-error">{pairError}</p> : <>
          <p>Use this one-time code within five minutes so Codex proposals appear in this workspace.</p>
          <code>{pairCode}</code>
          <small>Set it as COMMAND_CENTER_PAIR_CODE before the plugin’s first call.</small>
        </>}
      </aside>}
      {credentialPanel && <ProviderCredentialPanel
        status={providerCredential}
        onStatus={setProviderCredential}
        onClose={() => setCredentialPanel(false)}
      />}
    </main>
  );
}

function BootScreen() {
  return <main className="boot"><span className="aria-orb large" /><p>Opening durable memory…</p></main>;
}

function Login({onSuccess}: {onSuccess: () => void}) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/v1/auth/demo", {method: "POST", body: JSON.stringify({code})});
      onSuccess();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Sign in failed"); }
  }
  return <main className="login">
    <section className="login-card">
      <div className="brand-mark hero"><BrainCircuit /></div>
      <p className="eyebrow">COMMAND CENTER V3</p>
      <h1>Memory you can inspect.</h1>
      <p>Aria connects development decisions to durable evidence—and asks before changing a thing.</p>
      <form onSubmit={submit}>
        <label>Demo access code<input type="password" value={code}
          onChange={(event) => setCode(event.target.value)} autoFocus /></label>
        {error && <p className="form-error">{error}</p>}
        <button type="submit">Enter workspace <span>→</span></button>
      </form>
      <small>Each demo browser receives an isolated workspace.</small>
    </section>
  </main>;
}

function ProviderCredentialPanel({
  status, onStatus, onClose,
}: {
  status: ProviderCredentialStatus | null;
  onStatus: (status: ProviderCredentialStatus) => void;
  onClose: () => void;
}) {
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function connect(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<ProviderCredentialStatus>(
        "/api/v1/provider-credentials/openai",
        {method: "POST", body: JSON.stringify({api_key: apiKey})},
      );
      setApiKey("");
      onStatus(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not connect the key.");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    setError("");
    try {
      const result = await api<ProviderCredentialStatus>(
        "/api/v1/provider-credentials/openai", {method: "DELETE"},
      );
      setApiKey("");
      onStatus(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not remove the key.");
    } finally {
      setBusy(false);
    }
  }

  return <aside className="credential-panel" aria-label="OpenAI credential">
    <button className="icon-button" onClick={onClose} aria-label="Close credential panel">
      <X />
    </button>
    <span><KeyRound /> BRING YOUR OWN KEY</span>
    <h2>{status?.configured ? "OpenAI is connected" : "Connect OpenAI"}</h2>
    <p>
      Your key powers Sol and Aria for this workspace. It is encrypted in an
      expiring browser-session cookie and is never saved to Command Center memory.
    </p>
    {status?.configured ? <>
      <div className="credential-receipt">
        <Check />
        <div><strong>Session credential active</strong>
          <small>{status.expires_at
            ? `Cryptographic expiry: ${new Date(status.expires_at).toLocaleString()}`
            : "Expires with this browser session"}</small></div>
      </div>
      <button className="credential-remove" disabled={busy} onClick={() => void disconnect()}>
        Remove key now
      </button>
    </> : <form onSubmit={connect}>
      <label>OpenAI API key
        <input
          type="password"
          value={apiKey}
          onChange={(event) => setApiKey(event.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder="sk-…"
          minLength={20}
          maxLength={512}
          required
          autoFocus
        />
      </label>
      <button type="submit" disabled={busy || apiKey.length < 20}>
        {busy ? "Connecting…" : "Connect for this session"}
      </button>
    </form>}
    {error && <p className="form-error">{error}</p>}
    <small>The key never enters handoffs, MCP packets, repositories, logs, SQLite, or PostgreSQL.</small>
  </aside>;
}

function SurfaceTitle({eyebrow, title, note}: {eyebrow: string; title: string; note: string}) {
  return <header className="surface-title" data-aria-target="heading"><div><p className="eyebrow">{eyebrow}</p>
    <h1>{title}</h1></div><span>{note}</span></header>;
}

function AriaSurface({
  sessionId, onCreateSession, onEvidence, onRefresh, onPrepareRedesign,
}: {
  sessionId: string; onCreateSession: () => Promise<void>;
  onEvidence: (ids: string[]) => void; onRefresh: () => Promise<void>;
  onPrepareRedesign: (suggestion: RedesignSuggestion) => Promise<void>;
}) {
  const [message, setMessage] = useState("");
  const [deep, setDeep] = useState(false);
  const [busy, setBusy] = useState(false);
  const [items, setItems] = useState<ChatItem[]>([]);
  const [render, setRender] = useState<RenderBlock | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [packet, setPacket] = useState<ContextPack | null>(null);
  const [architectureBrief, setArchitectureBrief] = useState<ArchitectureBrief | null>(null);
  const [redesignSuggestion, setRedesignSuggestion] =
    useState<RedesignSuggestion | null>(null);
  const [resolveError, setResolveError] = useState("");

  useEffect(() => {
    const setDeepFromAria = (event: Event) => {
      setDeep(Boolean((event as CustomEvent<{enabled: boolean}>).detail?.enabled));
    };
    const showProposal = (event: Event) => {
      setProposal((event as CustomEvent<Proposal>).detail);
    };
    window.addEventListener("aria:set-deep", setDeepFromAria);
    window.addEventListener("aria:proposal-created", showProposal);
    return () => {
      window.removeEventListener("aria:set-deep", setDeepFromAria);
      window.removeEventListener("aria:proposal-created", showProposal);
    };
  }, []);

  useEffect(() => {
    if (!sessionId) {
      setItems([]);
      return;
    }
    void Promise.all([
      api<{items: {
        role: "user" | "assistant"; content: string; evidence_ids: string[];
      }[]}>(
        `/api/v1/sessions/${sessionId}/turns`,
      ),
      api<{items: Proposal[]}>(`/api/v1/sessions/${sessionId}/proposals`),
      api<{items: Proposal[]}>("/api/v1/proposals?status=pending"),
    ]).then(([turns, proposals, pending]) => {
      setItems(turns.items.map((item) => ({role: item.role, text: item.content})));
      onEvidence([...new Set(turns.items.flatMap((item) => item.evidence_ids))]);
      setProposal(
        proposals.items[0]
        ?? pending.items.find((item) => !item.session_id)
        ?? pending.items[0]
        ?? null,
      );
      setResolveError("");
    }).catch(() => {
      setItems([]);
      setProposal(null);
    });
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    const poll = window.setInterval(() => {
      void api<{items: Proposal[]}>("/api/v1/proposals?status=pending")
        .then((result) => {
          if (result.items[0]) setProposal(result.items[0]);
        })
        .catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(poll);
  }, [sessionId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const text = message.trim();
    if (!text || busy) return;
    if (!sessionId) { await onCreateSession(); return; }
    setMessage("");
    setBusy(true);
    setItems((old) => [...old, {role: "user", text}]);
    try {
      const response = await fetch(apiUrl("/api/v1/chat/stream"), {
        method: "POST", credentials: "include",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({session_id: sessionId, message: text, deep_synthesis: deep}),
      });
      await readSSE(response, (type, raw) => {
        const data = raw as Record<string, unknown>;
        if (type === "evidence") {
          const evidence = data.items as {id: string}[];
          onEvidence(evidence.map((item) => item.id));
          setTrace(data.trace as Trace);
        }
        if (type === "context_pack") {
          const next = data as unknown as ContextPack;
          setPacket(next);
          onEvidence(next.sources.map((source) => source.id));
        }
        if (type === "architecture_brief") {
          const next = data as unknown as ArchitectureBrief;
          setArchitectureBrief(next);
          onEvidence(next.sources.map((source) => source.id));
        }
        if (type === "redesign_suggestion") {
          setRedesignSuggestion(data as unknown as RedesignSuggestion);
        }
        if (type === "render") setRender(data as RenderBlock);
        if (type === "proposal") setProposal(data as unknown as Proposal);
        if (type === "answer") setItems((old) => [...old, {
          role: "assistant", text: String(data.text),
        }]);
      });
    } catch (reason) {
      setItems((old) => [...old, {role: "assistant",
        text: reason instanceof Error ? reason.message : "The request failed."}]);
    } finally { setBusy(false); await onRefresh(); }
  }

  async function resolve(action: "confirm" | "reject") {
    if (!proposal) return;
    setResolveError("");
    try {
      const next = await api<Proposal>(
        `/api/v1/proposals/${proposal.id}/${action}`, {method: "POST"},
      );
      setProposal(next);
    } catch (reason) {
      const current = await api<{items: Proposal[]}>(
        `/api/v1/sessions/${sessionId}/proposals`,
      );
      setProposal(current.items.find((item) => item.id === proposal.id) ?? proposal);
      setResolveError(reason instanceof Error ? reason.message : "The write was refused.");
    }
    await onRefresh();
  }

  return <section className="surface aria-surface">
    <SurfaceTitle eyebrow="Evidence-backed development memory" title="Ask Aria"
      note={deep ? "GPT-5.6 Sol · deep synthesis" : "GPT-5.6 Terra · low reasoning"} />
    <div className="conversation" data-aria-target="content">
      {!items.length && <div className="empty-chat">
        <span className="aria-orb large" />
        <h2>What should we remember?</h2>
        <p>Ask across projects, inspect the supporting evidence, then decide what becomes durable.</p>
        <button onClick={() => setMessage("Which projects can power a fast, private mobile assistant? Propose a decision.")}>
          Explore the private mobile stack <span>↗</span>
        </button>
      </div>}
      {items.map((item, index) => <article key={index} className={`chat-bubble ${item.role}`}>
        <span>{item.role === "assistant" ? "ARIA" : "YOU"}</span>
        <Markdown text={item.text} />
      </article>)}
      {architectureBrief && <ArchitectureBriefCard
        brief={architectureBrief} onEvidence={(id) => onEvidence([id])} />}
      {redesignSuggestion && <article className="redesign-suggestion">
        <header><span><Workflow /> REDESIGN WORKFLOW</span>
          <b>{redesignSuggestion.degraded ? "DEGRADED" : "EVIDENCE READY"}</b></header>
        <h3>{redesignSuggestion.primary_capability.name}</h3>
        <p>Taste is pinned at v{redesignSuggestion.primary_capability.version}
          {" · "}{redesignSuggestion.primary_capability.content_hash.slice(0, 12)}</p>
        <div className="suggestion-receipts">
          {redesignSuggestion.selection_reasons.map((reason) =>
            <code key={reason}>{reason}</code>)}
          {redesignSuggestion.evidence_ids.map((id) => <code key={id}>{id}</code>)}
        </div>
        <button onClick={() => void onPrepareRedesign(redesignSuggestion)}>
          <Workflow /> {redesignSuggestion.action.label}
        </button>
      </article>}
      {packet && <ContextPacketCard packet={packet} onEvidence={(id) => onEvidence([id])} />}
      {render && <article className="render-block">
        <div><span><GitBranch /> RENDERED ARCHITECTURE</span><small>Evidence-bound</small></div>
        <h3>{render.title}</h3><p>{render.summary}</p>
        <div className="project-chain">{(render.projects ?? []).map((project) =>
          <b key={project}>{project}</b>)}</div>
      </article>}
      {proposal && <article className={`proposal-card ${proposal.status}`}>
        <div><span><ShieldCheck /> WRITE PROPOSAL</span><b>{proposal.status}</b></div>
        <h3>{String(proposal.payload.title ?? proposal.operation)}</h3>
        <p>{proposal.rationale}</p>
        {(proposal.error || resolveError) && <p className="proposal-refusal">
          <strong>Write refused:</strong> {proposal.error ?? resolveError}
        </p>}
        {proposal.status === "pending" && <footer>
          <button className="secondary" onClick={() => void resolve("reject")}>Reject</button>
          <button onClick={() => void resolve("confirm")}>Confirm memory write</button>
        </footer>}
      </article>}
    </div>
    <form className="composer" data-aria-target="composer" onSubmit={submit}>
      <textarea value={message} onChange={(event) => setMessage(event.target.value)}
        placeholder="Ask across your development memory…"
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
          }
        }} />
      <div>
        <label className="deep-toggle"><input type="checkbox" checked={deep}
          onChange={(event) => setDeep(event.target.checked)} />
          <Sparkles /> Deep Synthesis</label>
        {trace && <span className="trace-summary"><Activity /> {trace.query_ms}ms · {trace.embedding_provider}
          {trace.degraded ? " · degraded" : ""}</span>}
        <button type="submit" className="send" disabled={!message.trim() || busy}>
          {busy ? <span className="spinner" /> : <Send />}
        </button>
      </div>
    </form>
  </section>;
}

function CapabilityLibrary({items}: {items: Capability[]}) {
  const [query, setQuery] = useState("");
  const filtered = items.filter((item) => (
    `${item.name} ${item.description} ${item.triggers.join(" ")}`
      .toLowerCase().includes(query.toLowerCase())
  ));
  return <section className="surface capability-surface">
    <SurfaceTitle eyebrow="Portable, provider-neutral instructions" title="Capability Library"
      note={`${items.length} trusted capabilities · exact versions`} />
    <div className="capability-toolbar">
      <Search /><input value={query} onChange={(event) => setQuery(event.target.value)}
        placeholder="Search workflows, policies, templates…" />
    </div>
    <div className="capability-grid" data-aria-target="content">
      {filtered.map((item) => <article key={`${item.stable_id}@${item.version}`}>
        <header><span>{item.kind.replace("_", " ")}</span>
          <b>v{item.version}</b></header>
        <h2>{item.name}</h2>
        <p>{item.description}</p>
        <section><small>TRIGGERS</small><div>{item.triggers.map((trigger) =>
          <i key={trigger}>{trigger}</i>)}</div></section>
        <dl>
          <div><dt>Repositories</dt><dd>{item.repositories.join(", ")}</dd></div>
          <div><dt>Required tools</dt><dd>{item.required_tools.join(", ") || "None"}</dd></div>
          <div><dt>Trust</dt><dd>{item.trust_status}</dd></div>
          <div><dt>Activations</dt><dd>{item.activation_count}</dd></div>
        </dl>
        <footer><span>{item.provenance}</span>
          <code>{item.content_hash.slice(0, 12)}</code></footer>
      </article>)}
    </div>
  </section>;
}

async function imagePayload(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

function HandoffBuilder({
  capabilities, handoffs, activeId, onActive, onRefresh, onController, onStartTour,
}: {
  capabilities: Capability[]; handoffs: Handoff[]; activeId: string;
  onActive: (id: string) => void; onRefresh: () => Promise<void>;
  onController: (controller: HandoffController) => void;
  onStartTour: () => void;
}) {
  const [repository, setRepository] = useState("Command Center");
  const [intent, setIntent] = useState("Redesign the Command Center interface shown in this screenshot.");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [analysis, setAnalysis] = useState<ScreenshotAnalysis | null>(null);
  const [recommendations, setRecommendations] = useState<{
    capability: Capability; score: number; selection_reasons: string[];
  }[]>([]);
  const [selectedRef, setSelectedRef] = useState("");
  const [draft, setDraft] = useState<Handoff | null>(null);
  const [planText, setPlanText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [packetOpen, setPacketOpen] = useState(false);

  useEffect(() => {
    const current = handoffs.find((item) => item.id === activeId)
      ?? handoffs.find((item) => item.status === "draft")
      ?? null;
    if (current) {
      setDraft(current);
      setPlanText(current.open_plan.join("\n"));
      setRepository(current.repository);
      setIntent(current.original_request);
      setAnalysis(current.screenshot ?? null);
      setSelectedRef(current.capability_refs[0] ?? "");
    }
  }, [activeId, handoffs]);

  useEffect(() => {
    const published = (event: Event) => {
      const item = (event as CustomEvent<Handoff>).detail;
      setDraft(item);
      setPlanText(item.open_plan.join("\n"));
    };
    window.addEventListener("aria:handoff-published", published);
    return () => window.removeEventListener("aria:handoff-published", published);
  }, []);

  function chooseFile(next: File) {
    if (!["image/png", "image/jpeg", "image/webp"].includes(next.type)) {
      setError("Use a PNG, JPEG, or WebP screenshot.");
      return;
    }
    setFile(next);
    setPreview(URL.createObjectURL(next));
    setAnalysis(null);
    setError("");
  }

  async function prepare(): Promise<HandoffControllerResult> {
    if (!file || !intent.trim()) {
      const message = !file
        ? "Upload or paste a screenshot first; voice cannot upload files."
        : "Describe the desired redesign before preparing the handoff.";
      setError(message);
      return {ok: false, message, surface: "handoff"};
    }
    setBusy(true); setError("");
    try {
      const finding = await api<ScreenshotAnalysis>("/api/v1/screenshots/analyze", {
        method: "POST",
        body: JSON.stringify({
          repository, user_request: intent, image_base64: await imagePayload(file),
          mime_type: file.type, retain: false,
        }),
      });
      setAnalysis(finding);
      const result = await api<{items: {
        capability: Capability; score: number; selection_reasons: string[];
      }[]}>("/api/v1/capabilities/recommend", {
        method: "POST",
        body: JSON.stringify({
          request: intent, repository, screenshot_findings: finding.findings, limit: 3,
        }),
      });
      setRecommendations(result.items);
      const primary = result.items[0]?.capability ?? capabilities[0];
      const ref = primary ? `${primary.stable_id}@${primary.version}` : "";
      setSelectedRef(ref);
      const created = await api<Handoff>("/api/v1/handoffs", {
        method: "POST",
        body: JSON.stringify({
          repository, original_request: intent, screenshot: finding,
          capability_refs: ref ? [ref] : [],
        }),
      });
      setDraft(created);
      setPlanText(created.open_plan.join("\n"));
      onActive(created.id);
      await onRefresh();
      return {
        ok: true,
        message: `Prepared draft ${created.id}. ${created.planning_receipt.degraded
          ? `Sol degraded: ${created.planning_receipt.degraded_reasons.join(", ")}.`
          : `Sol planned with ${created.planning_receipt.model}.`} Taste and all receipts are visible.`,
        surface: "handoff",
      };
    } catch (reason) {
      const message = reason instanceof Error
        ? reason.message : "Could not prepare the handoff.";
      setError(message);
      return {ok: false, message, surface: "handoff"};
    } finally { setBusy(false); }
  }

  async function persistPlan(
    nextPlan: string[],
    capabilityRef = selectedRef,
  ): Promise<HandoffControllerResult> {
    if (!draft) {
      return {ok: false, message: "Prepare a draft handoff first.", surface: "handoff"};
    }
    if (draft.status !== "draft") {
      return {
        ok: false,
        message: "The visible handoff is published and immutable. Create a new version to revise it.",
        surface: "handoff",
      };
    }
    setBusy(true); setError("");
    try {
      const updated = await api<Handoff>(`/api/v1/handoffs/${draft.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          capability_refs: capabilityRef ? [capabilityRef] : draft.capability_refs,
          open_plan: nextPlan,
        }),
      });
      setDraft(updated);
      setPlanText(updated.open_plan.join("\n"));
      await onRefresh();
      return {
        ok: true,
        message: `Saved ${updated.open_plan.length} visible Open Plan steps for ${updated.id}.`,
        surface: "handoff",
        handoff: updated,
      };
    } catch (reason) {
      const message = reason instanceof Error
        ? reason.message : "Could not save the Open Plan.";
      setError(message);
      return {ok: false, message, surface: "handoff"};
    } finally { setBusy(false); }
  }

  async function savePlan(): Promise<HandoffControllerResult> {
    return persistPlan(
      planText.split("\n").map((line) => line.trim()).filter(Boolean),
    );
  }

  async function startSession(
    nextRepository: string,
    nextIntent: string,
  ): Promise<HandoffControllerResult> {
    setRepository(nextRepository.trim() || "Command Center");
    setIntent(nextIntent.trim());
    setDraft(null);
    setAnalysis(null);
    setRecommendations([]);
    setSelectedRef("");
    setPlanText("");
    setPacketOpen(false);
    setError("");
    await afterPaint();
    return {
      ok: true,
      message: "Opened Handoff Builder. Upload or paste the redesign screenshot, then ask me to prepare the handoff.",
      surface: "handoff",
    };
  }

  async function selectCapability(
    capabilityRef: string,
  ): Promise<HandoffControllerResult> {
    const visible = (
      recommendations.length
        ? recommendations.map((item) => item.capability)
        : capabilities.slice(0, 3)
    ).find((item) => `${item.stable_id}@${item.version}` === capabilityRef);
    if (!visible || !["verified", "workspace"].includes(visible.trust_status)) {
      return {
        ok: false,
        message: `Capability ${capabilityRef} is not a currently visible trusted recommendation.`,
        surface: "handoff",
      };
    }
    setSelectedRef(capabilityRef);
    if (!draft) {
      return {
        ok: true,
        message: `Selected visible capability ${capabilityRef}.`,
        surface: "handoff",
      };
    }
    return persistPlan(
      planText.split("\n").map((line) => line.trim()).filter(Boolean),
      capabilityRef,
    );
  }

  async function editPlan(
    operation: "append" | "replace" | "remove" | "reorder",
    index: number,
    text?: string,
    destination?: number,
  ): Promise<HandoffControllerResult> {
    if (!draft) {
      return {ok: false, message: "Prepare a draft handoff first.", surface: "handoff"};
    }
    if (draft.status !== "draft") {
      return {
        ok: false,
        message: "The visible handoff is published and immutable.",
        surface: "handoff",
      };
    }
    try {
      const current = planText.split("\n").map((line) => line.trim()).filter(Boolean);
      const next = editOpenPlan(current, operation, index, text, destination);
      setPlanText(next.join("\n"));
      return persistPlan(next);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The plan edit is invalid.";
      setError(message);
      return {ok: false, message, surface: "handoff"};
    }
  }

  async function openPacket(): Promise<HandoffControllerResult> {
    if (!draft) {
      return {ok: false, message: "Prepare a draft handoff first.", surface: "handoff"};
    }
    setPacketOpen(true);
    await afterPaint();
    document.querySelector<HTMLElement>("[data-aria-target='receipts']")
      ?.scrollIntoView({behavior: "smooth", block: "center"});
    return {
      ok: true,
      message: `Opened packet ${draft.id}: ${draft.evidence_sources.length} evidence receipts, ${draft.safe_edit_points.length} safe points, ${draft.risks.length} risks, planning model ${draft.planning_receipt.model}.`,
      surface: "handoff",
      handoff: draft,
    };
  }

  async function publish(): Promise<HandoffControllerResult> {
    if (!draft || draft.status !== "draft") {
      return {
        ok: false,
        message: draft?.status === "published"
          ? "The visible handoff is already published."
          : "There is no draft handoff ready to publish.",
        surface: "handoff",
      };
    }
    const saved = await savePlan();
    if (!saved.ok) return saved;
    try {
      const published = await api<Handoff>(
        `/api/v1/handoffs/${draft.id}/publish`, {method: "POST"},
      );
      setDraft(published);
      setPacketOpen(true);
      window.dispatchEvent(new CustomEvent("aria:handoff-published", {detail: published}));
      await onRefresh();
      return {
        ok: true,
        message: `Published handoff ${published.id}. The exact Codex command is visible and the packet is now immutable.`,
        surface: "handoff",
        handoff: published,
      };
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Could not publish the handoff.";
      setError(message);
      return {ok: false, message, surface: "handoff"};
    }
  }

  useEffect(() => {
    onController({
      startSession,
      prepare,
      selectCapability,
      editPlan,
      openPacket,
      publish,
    });
  });

  const draftArchitecture = draft?.architecture as Partial<ArchitectureBrief> | undefined;
  const snapshotReceipt = draftArchitecture?.snapshot_receipt;
  const healthSummary = draftArchitecture?.health_summary;

  return <section className="surface handoff-surface" onPaste={(event) => {
    const pasted = [...event.clipboardData.files].find((item) => item.type.startsWith("image/"));
    if (pasted) chooseFile(pasted);
  }}>
    <SurfaceTitle eyebrow="Prepare for Codex" title="Handoff Builder"
      note="GPT-5.6 Sol · bounded packet · voice-publishable" />
    <button className="redesign-tour-trigger" onClick={onStartTour}>
      <CircleHelp /> Start evidence-aware redesign tour
    </button>
    <div className="handoff-grid" data-aria-target="content">
      <section className="handoff-input">
        <label>Repository<input value={repository}
          onChange={(event) => setRepository(event.target.value)} /></label>
        <label>Desired change<textarea value={intent}
          onChange={(event) => setIntent(event.target.value)} /></label>
        <label className="screenshot-drop" data-aria-target="screenshot">
          <input type="file" accept="image/png,image/jpeg,image/webp"
            onChange={(event) => event.target.files?.[0] && chooseFile(event.target.files[0])} />
          {preview ? <img src={preview} alt="Screenshot preview" /> : <>
            <Upload /><strong>Upload or paste a screenshot</strong>
            <span>PNG, JPEG, or WebP · raw image is not retained</span>
          </>}
        </label>
        <button className="primary-action" disabled={busy} onClick={() => void prepare()}>
          <Sparkles /> {busy ? "Sol is preparing…" : "Analyze and prepare for Codex"}
        </button>
        {error && <p className="form-error">{error}</p>}
      </section>

      <section className="handoff-review">
        <article className="sol-findings">
          <header><span>01</span><div><small>SOL OBSERVATIONS</small>
            <strong>Screenshot-derived inferences</strong></div></header>
          {(analysis?.findings ?? []).map((finding) => <p key={finding}>{finding}</p>)}
          {!analysis && <p className="quiet">Upload a screenshot to begin the evidence-bound analysis.</p>}
          {analysis && <footer><code>{analysis.image_hash.slice(0, 16)}</code>
            <span>{analysis.width}×{analysis.height} · not retained</span></footer>}
        </article>

        <article className="workflow-choice" data-aria-target="recommendation">
          <header><span>02</span><div><small>RECOMMENDED WORKFLOW</small>
            <strong>One primary capability, visible alternatives</strong></div></header>
          {(recommendations.length ? recommendations : capabilities.slice(0, 3).map((capability) => ({
            capability, score: 0, selection_reasons: [],
          }))).map((item, index) => {
            const ref = `${item.capability.stable_id}@${item.capability.version}`;
            return <button key={ref} className={selectedRef === ref ? "selected" : ""}
              disabled={Boolean(draft && draft.status !== "draft")}
              onClick={() => void selectCapability(ref)}>
              <span>{index === 0 ? "PRIMARY" : "ALTERNATIVE"}</span>
              <strong>{item.capability.name}</strong>
              <small>v{item.capability.version} · {item.selection_reasons.join(" · ")}</small>
            </button>;
          })}
        </article>

        <article className="open-plan" data-aria-target="open-plan">
          <header><span>03</span><div><small>EDITABLE OPEN PLAN</small>
            <strong>Codex interviews before it edits</strong></div></header>
          <textarea value={planText} disabled={!draft || draft.status !== "draft"}
            onChange={(event) => setPlanText(event.target.value)}
            placeholder="One inspectable plan step per line" />
          {draft?.status === "draft" && <button onClick={() => void savePlan()}>Save Open Plan</button>}
        </article>

        {draft && <article className={`handoff-packet ${draft.status}`}
          data-handoff-packet data-aria-target="receipts">
          <header><span>04</span><div><small>EXACT BOUNDED PACKET</small>
            <strong>{draft.id} · v{draft.version} · {draft.status}</strong></div></header>
          <dl>
            <div><dt>Capability</dt><dd>{draft.capability_refs.join(", ")}</dd></div>
            <div><dt>Architecture snapshot</dt>
              <dd>{snapshotReceipt?.snapshot_id ?? "No registered snapshot"}</dd></div>
            <div><dt>Source revision</dt>
              <dd>{snapshotReceipt?.source_revision ?? "unknown"}</dd></div>
            <div><dt>Architecture coverage</dt>
              <dd>{Math.round((healthSummary?.coverage ?? 0) * 100)}%</dd></div>
            <div><dt>Evidence</dt><dd>{draft.evidence_sources.map((item) => item.id).join(", ")}</dd></div>
            <div><dt>Safe edit points</dt><dd>{draft.safe_edit_points.length}</dd></div>
            <div><dt>Risks</dt><dd>{draft.risks.length}</dd></div>
            <div><dt>Omitted candidates</dt><dd>{draft.omitted_candidates}</dd></div>
            <div><dt>Packet estimate</dt><dd>{draft.token_estimate} tokens</dd></div>
            <div><dt>Architecture state</dt><dd>{draftArchitecture?.degraded
              ? `degraded · ${(draftArchitecture.degraded_reasons ?? []).join(" · ")}`
              : "versioned and repository-scoped"}</dd></div>
            <div><dt>Planning model</dt><dd>{draft.planning_receipt.model}</dd></div>
            <div><dt>Planning state</dt><dd>{draft.planning_receipt.degraded
              ? `degraded · ${draft.planning_receipt.degraded_reasons.join(" · ")}`
              : "validated Sol plan"}</dd></div>
          </dl>
          <button className="packet-toggle" aria-expanded={packetOpen}
            onClick={() => setPacketOpen((value) => !value)}>
            {packetOpen ? "Hide exact receipts" : "Open exact packet and receipts"}
          </button>
          {packetOpen && <div className="handoff-receipts">
            <code>{draft.planning_receipt.capability_reference.stable_id}
              @{draft.planning_receipt.capability_reference.version}
              {" · "}{draft.planning_receipt.capability_reference.content_hash}</code>
            {draft.evidence_sources.map((source) => <code key={source.id}>
              {source.id} · {source.selection_reasons.join(" · ") || "bounded selection"}
            </code>)}
          </div>}
          <code className="codex-command">{draft.codex_command}</code>
          {draft.status === "draft" ? <button className="approve-handoff"
            data-aria-target="publication"
            onClick={() => void publish()}><Check /> Approve this handoff</button>
            : <p className="published-receipt" data-aria-target="publication">
              <Check /> Published and immutable. Codex can load it now.</p>}
        </article>}
      </section>
    </div>
  </section>;
}

function RecallSurface({onEvidence}: {onEvidence: (hit: RecallHit) => void}) {
  const [query, setQuery] = useState("private mobile assistant");
  const [hits, setHits] = useState<RecallHit[]>([]);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [busy, setBusy] = useState(false);
  const performSearch = useCallback(async (searchQuery: string) => {
    setBusy(true);
    try {
      const result = await api<{hits: RecallHit[]; trace: Trace}>("/api/v1/recall", {
        method: "POST", body: JSON.stringify({query: searchQuery, limit: 12}),
      });
      setHits(result.hits); setTrace(result.trace);
    } finally { setBusy(false); }
  }, []);
  async function search(event?: FormEvent) {
    event?.preventDefault();
    await performSearch(query);
  }
  useEffect(() => {
    const recallFromAria = (event: Event) => {
      const nextQuery = (event as CustomEvent<{query: string}>).detail?.query?.trim();
      if (!nextQuery) return;
      setQuery(nextQuery);
      void performSearch(nextQuery);
    };
    window.addEventListener("aria:run-recall", recallFromAria);
    return () => window.removeEventListener("aria:run-recall", recallFromAria);
  }, [performSearch]);
  return <section className="surface recall-surface">
    <SurfaceTitle eyebrow="Inspectable hybrid retrieval" title="Recall Explorer"
      note={trace ? `${trace.candidates} candidates · ${trace.query_ms}ms` : "BM25 · dense · structural"} />
    <form className="recall-search" onSubmit={search}><Search /><input value={query}
      onChange={(event) => setQuery(event.target.value)} /><button>{busy ? "Searching…" : "Recall"}</button></form>
    <div className="results" data-aria-target="results">
      {hits.map((hit, index) => <button key={hit.memory.id} onClick={() => onEvidence(hit)}>
        <span className="rank">{String(index + 1).padStart(2, "0")}</span>
        <div><small>{hit.memory.project} / {hit.memory.kind}</small>
          <h3>{hit.memory.title}</h3><p>{hit.memory.content}</p>
          <footer>{hit.provenance.map((item) => <i key={item}>{item}</i>)}</footer>
        </div><b>{hit.score.toFixed(3)}</b>
      </button>)}
      {!hits.length && <div className="empty-result"><Archive /><p>Run a recall to inspect ranked evidence.</p></div>}
    </div>
  </section>;
}

function TimelineSurface({sessions, items, onEvidence}: {
  sessions: Session[]; items: Memory[]; onEvidence: (memory: Memory) => void;
}) {
  const groups = useMemo(() => {
    const output = new Map<string, Memory[]>();
    items.forEach((item) => {
      const day = item.happened_at.slice(0, 10);
      output.set(day, [...(output.get(day) ?? []), item]);
    });
    return [...output.entries()];
  }, [items]);
  return <section className="surface timeline-surface" data-aria-target="content">
    <SurfaceTitle eyebrow="Durable chronology" title="Sessions / Timeline"
      note={`${sessions.length} sessions · ${items.length} memories`} />
    <div className="timeline-grid">
      <aside><h3>Aria sessions</h3>{sessions.map((session) => <article key={session.id}>
        <MessageSquareText /><div><strong>{session.title}</strong>
          <small>{session.turn_count} visible turns</small></div></article>)}</aside>
      <div className="chronology">{groups.map(([day, records]) => <section key={day}>
        <time>{new Date(`${day}T00:00:00`).toLocaleDateString(undefined, {
          month: "short", day: "numeric", year: "numeric",
        })}</time><div>{records.map((memory) => <button key={memory.id}
          onClick={() => onEvidence(memory)}><i className={memory.entity_type} />
          <span><small>{memory.project} · {memory.kind}</small><strong>{memory.title}</strong></span>
        </button>)}</div></section>)}</div>
    </div>
  </section>;
}

function AuditSurface({items}: {items: Audit[]}) {
  return <section className="surface audit-surface" data-aria-target="content">
    <SurfaceTitle eyebrow="Append-only accountability" title="Audit"
      note={`${items.length} visible events · no prompt bodies logged`} />
    <div className="audit-table">
      <header><span>Event</span><span>Actor</span><span>Reference</span><span>Time</span></header>
      {items.map((item) => <article key={item.id}>
        <span><i className={item.action.includes("confirmed") ? "confirmed" : ""} />
          <strong>{item.action}</strong><small>{String(item.detail.operation ?? "")}</small></span>
        <b data-label="Actor">{item.actor}</b>
        <code data-label="Reference">{item.memory_id ?? item.proposal_id ?? "—"}</code>
        <time data-label="Time">{new Date(item.created_at).toLocaleString()}</time>
      </article>)}
      {!items.length && <div className="empty-result"><ShieldCheck />
        <p>Confirmed and rejected writes will appear here.</p></div>}
    </div>
  </section>;
}

function EvidenceDrawer({
  memory, onClose,
}: {memory: Memory | DeclaredDocument | null; onClose: () => void}) {
  const isDocument = Boolean(memory && "source_uri" in memory);
  return <aside className={`evidence-drawer ${memory ? "open" : ""}`}>
    <header><span>EVIDENCE</span><button className="icon-button" onClick={onClose}><X /></button></header>
    {memory && <div className="evidence-body">
      <div className="evidence-id"><span>{isDocument ? "declared document" : (memory as Memory).entity_type}</span>
        <code>{memory.id}</code></div>
      <p className="eyebrow">{"repository" in memory ? memory.repository : memory.project} / {memory.kind}</p>
      <h2>{memory.title}</h2>
      <p className="memory-copy">{"body" in memory ? memory.body : memory.content}</p>
      {"reason" in memory && memory.reason && <section><small>WHY THIS WAS RECORDED</small>
        <p>{memory.reason}</p></section>}
      {"safe_edit_points" in memory && <section className="safe-points"><small>SAFE EDIT POINTS</small>
        {memory.safe_edit_points.map((point) => <code key={point}>{point}</code>)}</section>}
      {"risk_areas" in memory && <section className="risk-points"><small>RISK AREAS</small>
        {memory.risk_areas.map((risk) => <p key={risk}>{risk}</p>)}</section>}
      {"tags" in memory && <div className="tag-list">{memory.tags.map((tag) =>
        <span key={tag}>{tag}</span>)}</div>}
      <dl><div><dt>Status</dt><dd>{memory.status}</dd></div>
        <div><dt>{isDocument ? "Verified" : "Happened"}</dt>
          <dd>{isDocument
            ? ((memory as DeclaredDocument).last_verified ?? "not declared")
            : new Date((memory as Memory).happened_at).toLocaleDateString()}</dd></div></dl>
    </div>}
  </aside>;
}

function Markdown({text}: {text: string}) {
  function inline(value: string): ReactNode[] {
    return value.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[A-Za-z0-9_:-]+\])/g).map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={index}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return <code key={index}>{part.slice(1, -1)}</code>;
      }
      if (part.startsWith("[") && part.endsWith("]")) {
        return <code className="citation" key={index}>{part}</code>;
      }
      return part;
    });
  }
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      const content = inline(heading[2]);
      blocks.push(heading[1].length === 1
        ? <h2 key={index}>{content}</h2>
        : heading[1].length === 2
          ? <h3 key={index}>{content}</h3>
          : <h4 key={index}>{content}</h4>);
      index += 1;
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
        items.push(<li key={index}>{inline(lines[index].trim().replace(/^[-*]\s+/, ""))}</li>);
        index += 1;
      }
      blocks.push(<ul key={`list-${index}`}>{items}</ul>);
      continue;
    }
    if (/^>\s?/.test(line)) {
      blocks.push(<blockquote key={index}>{inline(line.replace(/^>\s?/, ""))}</blockquote>);
      index += 1;
      continue;
    }
    const paragraph: string[] = [];
    while (
      index < lines.length
      && lines[index].trim()
      && !/^(#{1,3})\s+|^[-*]\s+|^>\s?/.test(lines[index].trim())
    ) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push(<p key={`paragraph-${index}`}>{paragraph.map((value, lineIndex) =>
      <span key={lineIndex}>{inline(value)}{lineIndex < paragraph.length - 1 && <br />}</span>
    )}</p>);
  }
  return <div className="markdown">{blocks}</div>;
}

function ArchitectureBriefCard({
  brief, onEvidence,
}: {brief: ArchitectureBrief; onEvidence: (id: string) => void}) {
  const identity = brief.repository_identity;
  const snapshot = brief.snapshot_receipt;
  return <details className="context-packet architecture-packet"
    data-aria-target="architecture-packet">
    <summary><span><GitBranch /> SHARED ARCHITECTURE AWARENESS</span>
      <b>{brief.token_estimate} / {brief.token_budget} tokens</b></summary>
    <div className="packet-body">
      <header>
        <div><small>REPOSITORY</small>
          <strong>{identity.repository ?? identity.requested ?? "Unregistered"}</strong></div>
        <div><small>SNAPSHOT</small>
          <strong>{snapshot.snapshot_id ?? "No active snapshot"}</strong></div>
        <div><small>REVISION</small>
          <strong>{snapshot.source_revision ?? "unknown"}</strong></div>
        <div><small>COVERAGE</small>
          <strong>{Math.round((brief.health_summary.coverage ?? 0) * 100)}%</strong></div>
      </header>
      <p className="packet-explainer">
        Aria and Codex use this same versioned, repository-scoped architecture contract.
      </p>
      {brief.degraded && <p className="architecture-degraded">
        Degraded: {brief.degraded_reasons.join(" · ")}
      </p>}
      <div className="packet-sources">{brief.sources.map((source) =>
        <button key={source.id} onClick={() => onEvidence(source.id)}>
          <span>{source.entity_type.replace("architecture_", "")}</span>
          <strong>{source.source_uri}{source.section_anchor ? ` #${source.section_anchor}` : ""}</strong>
          <small>{source.selection_reasons.join(" · ") || source.evidence_class}</small>
          <code>{source.id} · {source.content_hash.slice(0, 12)}</code>
        </button>)}</div>
      <div className="packet-boundaries">
        <section><small>INTERFACES</small>{brief.interfaces.slice(0, 6).map((item) =>
          <code key={item}>{item}</code>)}</section>
        <section><small>SAFE EDIT POINTS</small>{brief.safe_edit_points.slice(0, 6).map((item) =>
          <code key={item}>{item}</code>)}</section>
        <section><small>RISK AREAS</small>{brief.risk_areas.slice(0, 6).map((item) =>
          <p key={item}>{item}</p>)}</section>
      </div>
      <footer>
        {brief.omitted_candidate_count} lower-ranked candidates omitted · trace {brief.trace_id}
      </footer>
    </div>
  </details>;
}

function ContextPacketCard({
  packet, onEvidence,
}: {packet: ContextPack; onEvidence: (id: string) => void}) {
  return <details className="context-packet" data-aria-target="context-packet">
    <summary><span><Activity /> CONTEXT PACKET INJECTED</span>
      <b>{packet.token_estimate} / {packet.token_budget} tokens</b></summary>
    <div className="packet-body">
      <header><div><small>REPOSITORY</small><strong>{packet.repository_identity.repository}</strong></div>
        <div><small>ROUTING</small><strong>{String(packet.routing.intent)} · {String(packet.routing.retrieval_mode)}</strong></div>
        <div><small>STATE</small><strong>{packet.degraded ? "degraded fallback" : "all signals ready"}</strong></div></header>
      <p className="packet-explainer">Aria and Codex received only these selected sources—not the full database.</p>
      <div className="packet-sources">{packet.sources.map((source) =>
        <button key={source.id} onClick={() => onEvidence(source.id)}>
          <span>{source.entity_type}</span><strong>{source.title}</strong>
          <small>{source.selection_reasons.join(" · ") || "bounded by relevance"}</small>
        </button>)}</div>
      <div className="packet-boundaries">
        <section><small>SAFE EDIT POINTS</small>{packet.safe_edit_points.slice(0, 5).map((point) =>
          <code key={point}>{point}</code>)}</section>
        <section><small>RISK AREAS</small>{packet.risk_areas.slice(0, 5).map((risk) =>
          <p key={risk}>{risk}</p>)}</section>
      </div>
      <footer>{packet.omitted_candidate_count} lower-ranked candidates omitted to stay bounded.</footer>
    </div>
  </details>;
}

function CommandPalette({onSelect, onClose}: {
  onSelect: (surface: Surface) => void; onClose: () => void;
}) {
  return <div className="palette-backdrop" onMouseDown={onClose}>
    <section className="palette" onMouseDown={(event) => event.stopPropagation()}>
      <header><Search /><input placeholder="Go to a surface…" autoFocus /><kbd>ESC</kbd></header>
      <p>COMMAND CENTER</p>
      {surfaces.map(({id, label, icon: Icon}) => <button key={id} onClick={() => onSelect(id)}>
        <Icon /><span>{label}</span><small>Open</small>
      </button>)}
    </section>
  </div>;
}

function GuidedTour({
  step, steps, degraded, onBack, onNext, onRepeat, onStop,
}: {
  step: number; steps: TourStep[]; degraded: boolean;
  onBack: () => void; onNext: () => void; onRepeat: () => void; onStop: () => void;
}) {
  const current = steps[step];
  return <aside className="guided-tour" role="dialog" aria-labelledby="guided-tour-title">
    <header>
      <span>ARIA GUIDED TOUR {degraded ? "· OFFLINE SCRIPT" : ""}</span>
      <button className="icon-button" aria-label="Stop guided tour" onClick={onStop}><X /></button>
    </header>
    <small>STEP {step + 1} OF {steps.length} · {current.id}</small>
    <h2 id="guided-tour-title">{current.action}</h2>
    <p>{current.narration}</p>
    {current.evidence_ids.length > 0 && <div className="tour-receipts">
      {current.evidence_ids.map((id) => <code key={id}>{id}</code>)}
    </div>}
    {current.pause_reason && <p className="tour-pause">
      <strong>Pause:</strong> {current.pause_reason}
    </p>}
    <footer>
      <button className="secondary" onClick={onBack} disabled={step === 0}>Back</button>
      <button className="secondary" onClick={onRepeat}>Repeat</button>
      {step < steps.length - 1
        ? <button onClick={onNext}>Next</button>
        : <button onClick={onStop}>Finish tour</button>}
    </footer>
  </aside>;
}
