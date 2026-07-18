"use client";

import {FormEvent, useCallback, useEffect, useMemo, useState} from "react";
import {
  Activity, Archive, BrainCircuit, Clock3, Command, GitBranch, Menu,
  MessageSquareText, Plus, Search, Send, ShieldCheck, Sparkles, X,
} from "lucide-react";
import {api, apiUrl, readSSE} from "@/lib/api";
import type {Audit, GraphData, Memory, Proposal, RecallHit, Session, Trace} from "@/lib/types";
import {MemoryGraph} from "@/components/MemoryGraph";

type Surface = "aria" | "recall" | "graph" | "timeline" | "audit";
type ChatItem = {role: "user" | "assistant"; text: string};
type RenderBlock = {title: string; summary: string; evidence_ids?: string[]; projects?: string[]};

const surfaces: {id: Surface; label: string; icon: typeof Sparkles}[] = [
  {id: "aria", label: "Aria", icon: Sparkles},
  {id: "recall", label: "Recall Explorer", icon: Search},
  {id: "graph", label: "Knowledge Graph", icon: GitBranch},
  {id: "timeline", label: "Sessions / Timeline", icon: Clock3},
  {id: "audit", label: "Audit", icon: ShieldCheck},
];

export default function Page() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [surface, setSurface] = useState<Surface>("aria");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState("");
  const [timeline, setTimeline] = useState<Memory[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [graph, setGraph] = useState<GraphData>({nodes: [], edges: []});
  const [selected, setSelected] = useState<Memory | null>(null);
  const [evidenceIds, setEvidenceIds] = useState<string[]>([]);
  const [palette, setPalette] = useState(false);
  const [railOpen, setRailOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      await api("/api/v1/status");
      setAuthenticated(true);
      const [sessionData, timeData, auditData, graphData] = await Promise.all([
        api<{items: Session[]}>("/api/v1/sessions"),
        api<{items: Memory[]}>("/api/v1/timeline?limit=120"),
        api<{items: Audit[]}>("/api/v1/audit"),
        api<GraphData>("/api/v1/graph"),
      ]);
      setSessions(sessionData.items);
      setTimeline(timeData.items);
      setAudit(auditData.items);
      setGraph(graphData);
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

  async function openEvidence(id: string) {
    const local = timeline.find((item) => item.id === id);
    if (local) {
      setSelected(local);
      return;
    }
    const kind = graph.nodes.find((item) => item.id === id)?.type === "episode"
      ? "episodes" : "facts";
    try {
      setSelected(await api<Memory>(`/api/v1/memories/${kind}/${id}`));
    } catch {
      setSelected(null);
    }
  }

  if (authenticated === null) return <BootScreen />;
  if (!authenticated) return <Login onSuccess={() => void refresh()} />;

  return (
    <main className="shell">
      <header className="topbar">
        <button className="icon-button mobile-only" onClick={() => setRailOpen(true)}><Menu /></button>
        <div className="brand-mark"><BrainCircuit /></div>
        <div className="brand"><strong>Command Center</strong><span>v3 / Aria</span></div>
        <button className="command-trigger" onClick={() => setPalette(true)}>
          <Command size={15} /><span>Jump to…</span><kbd>⌘ K</kbd>
        </button>
        <div className="system-state"><i /><span>Memory online</span></div>
      </header>

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
        />}
        {surface === "recall" && <RecallSurface onEvidence={(hit) => {
          setSelected(hit.memory); setEvidenceIds((ids) => [...new Set([...ids, hit.memory.id])]);
        }} />}
        {surface === "graph" && <section className="surface graph-surface">
          <SurfaceTitle eyebrow="Relationships" title="Knowledge Graph"
            note={`${graph.nodes.length} semantic nodes · client-laid with Dagre`} />
          <MemoryGraph data={graph} activeIds={evidenceIds} onEvidence={(id) => void openEvidence(id)} />
        </section>}
        {surface === "timeline" && <TimelineSurface sessions={sessions} items={timeline}
          onEvidence={setSelected} />}
        {surface === "audit" && <AuditSurface items={audit} />}
      </section>

      <EvidenceDrawer memory={selected} onClose={() => setSelected(null)} />
      <nav className="dock">
        {surfaces.map(({id, label, icon: Icon}) => (
          <button key={id} className={surface === id ? "active" : ""} onClick={() => setSurface(id)}>
            <Icon /><span>{label}</span>
          </button>
        ))}
      </nav>
      {palette && <CommandPalette onSelect={(id) => {setSurface(id); setPalette(false);}}
        onClose={() => setPalette(false)} />}
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

function SurfaceTitle({eyebrow, title, note}: {eyebrow: string; title: string; note: string}) {
  return <header className="surface-title"><div><p className="eyebrow">{eyebrow}</p>
    <h1>{title}</h1></div><span>{note}</span></header>;
}

function AriaSurface({
  sessionId, onCreateSession, onEvidence, onRefresh,
}: {
  sessionId: string; onCreateSession: () => Promise<void>;
  onEvidence: (ids: string[]) => void; onRefresh: () => Promise<void>;
}) {
  const [message, setMessage] = useState("");
  const [deep, setDeep] = useState(false);
  const [busy, setBusy] = useState(false);
  const [items, setItems] = useState<ChatItem[]>([]);
  const [render, setRender] = useState<RenderBlock | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [trace, setTrace] = useState<Trace | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setItems([]);
      return;
    }
    void api<{items: {role: "user" | "assistant"; content: string}[]}>(
      `/api/v1/sessions/${sessionId}/turns`,
    ).then((result) => setItems(result.items.map((item) => ({
      role: item.role, text: item.content,
    })))).catch(() => setItems([]));
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
    const next = await api<Proposal>(`/api/v1/proposals/${proposal.id}/${action}`, {method: "POST"});
    setProposal(next);
    await onRefresh();
  }

  return <section className="surface aria-surface">
    <SurfaceTitle eyebrow="Evidence-backed development memory" title="Ask Aria"
      note={deep ? "GPT-5.6 Sol · deep synthesis" : "GPT-5.6 Terra · low reasoning"} />
    <div className="conversation">
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
        <p>{item.text}</p>
      </article>)}
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
        {proposal.status === "pending" && <footer>
          <button className="secondary" onClick={() => void resolve("reject")}>Reject</button>
          <button onClick={() => void resolve("confirm")}>Confirm memory write</button>
        </footer>}
      </article>}
    </div>
    <form className="composer" onSubmit={submit}>
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

function RecallSurface({onEvidence}: {onEvidence: (hit: RecallHit) => void}) {
  const [query, setQuery] = useState("private mobile assistant");
  const [hits, setHits] = useState<RecallHit[]>([]);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [busy, setBusy] = useState(false);
  async function search(event?: FormEvent) {
    event?.preventDefault();
    setBusy(true);
    try {
      const result = await api<{hits: RecallHit[]; trace: Trace}>("/api/v1/recall", {
        method: "POST", body: JSON.stringify({query, limit: 12}),
      });
      setHits(result.hits); setTrace(result.trace);
    } finally { setBusy(false); }
  }
  return <section className="surface recall-surface">
    <SurfaceTitle eyebrow="Inspectable hybrid retrieval" title="Recall Explorer"
      note={trace ? `${trace.candidates} candidates · ${trace.query_ms}ms` : "BM25 · dense · structural"} />
    <form className="recall-search" onSubmit={search}><Search /><input value={query}
      onChange={(event) => setQuery(event.target.value)} /><button>{busy ? "Searching…" : "Recall"}</button></form>
    <div className="results">
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
  return <section className="surface timeline-surface">
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
  return <section className="surface audit-surface">
    <SurfaceTitle eyebrow="Append-only accountability" title="Audit"
      note={`${items.length} visible events · no prompt bodies logged`} />
    <div className="audit-table">
      <header><span>Event</span><span>Actor</span><span>Reference</span><span>Time</span></header>
      {items.map((item) => <article key={item.id}>
        <span><i className={item.action.includes("confirmed") ? "confirmed" : ""} />
          <strong>{item.action}</strong><small>{String(item.detail.operation ?? "")}</small></span>
        <b>{item.actor}</b>
        <code>{item.memory_id ?? item.proposal_id ?? "—"}</code>
        <time>{new Date(item.created_at).toLocaleString()}</time>
      </article>)}
      {!items.length && <div className="empty-result"><ShieldCheck />
        <p>Confirmed and rejected writes will appear here.</p></div>}
    </div>
  </section>;
}

function EvidenceDrawer({memory, onClose}: {memory: Memory | null; onClose: () => void}) {
  return <aside className={`evidence-drawer ${memory ? "open" : ""}`}>
    <header><span>EVIDENCE</span><button className="icon-button" onClick={onClose}><X /></button></header>
    {memory && <div className="evidence-body">
      <div className="evidence-id"><span>{memory.entity_type}</span><code>{memory.id}</code></div>
      <p className="eyebrow">{memory.project} / {memory.kind}</p>
      <h2>{memory.title}</h2><p className="memory-copy">{memory.content}</p>
      {memory.reason && <section><small>WHY THIS WAS RECORDED</small><p>{memory.reason}</p></section>}
      <div className="tag-list">{memory.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
      <dl><div><dt>Status</dt><dd>{memory.status}</dd></div>
        <div><dt>Happened</dt><dd>{new Date(memory.happened_at).toLocaleDateString()}</dd></div></dl>
    </div>}
  </aside>;
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
