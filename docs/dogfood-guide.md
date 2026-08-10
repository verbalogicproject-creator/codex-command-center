# Aria Command Center Dogfood Guide

```yaml
ai_card:
  id: command-center.dogfood-guide
  repository: Command Center
  title: Aria Command Center Dogfood Guide
  kind: verification_guide
  audience: [creator, evaluator, tester]
  status: active
  owner_area: release verification
  main_files: [apps/web/app/page.tsx, apps/web/components/AriaVoice.tsx, services/memory/aria_memory/aria_registry.py]
  public_interfaces: [Aria, global voice orb, /atlas/index.html, DevHub]
  provides: [manual expectations, dogfood sequence, defect severity rubric, release receipt template]
  depends_on: [command-center.aria-voice, command-center.architecture-exhibit, command-center.security-privacy]
  safe_edit_points: [manual observations and sanitized release results]
  risk_areas: [recording credentials, treating fallback as live-model proof, claiming unperformed checks]
  graph_rag_entities: [dogfood, Aria, DevHub, Take a step back]
  last_verified: 2026-07-20
```

## What to expect now

After signing in, the default surface is **Aria**. The microphone orb remains
fixed above every surface:

- selecting it while idle requests microphone access and starts Realtime;
- selecting it while connected returns to Aria's Conversation tab;
- navigating, opening a drawer, or starting a tour does not intentionally end
  the voice transport;
- the Aria page owns Start/Reconnect, Mute, Stop, connection status, profiles,
  transcript history, and DevHub inspection.

Conversation combines text and stored voice transcript turns chronologically.
Voice turns are labelled **VOICE**. Raw audio is not stored. A missing
user-owned OpenAI credential, rejected microphone permission, unsupported
WebRTC browser, or network error should produce a visible degraded/error state
without breaking typed Aria, retrieval, handoffs, MCP, or the deterministic
tour.

**Voice & Persona** lists the default workspace profile and permits named
profiles, supported voice selection, bounded tone/directness/verbosity/
initiative dials, eligible-command enablement, and collision-checked spoken
aliases. The default profile cannot be deleted. The active selection is
browser-local.

**DevHub** shows the effective command catalog, registry-projection coverage
and safety classification, recent voice sessions, correlated transcript/call
IDs, and sanitized command executions. It deliberately does not label this as
coverage of every interactive DOM control.
Arguments and results may be truncated or redacted. No audio, SDP, provider
credential, authorization value, or unrestricted model output should appear.

The header's **Take a step back** link opens the static architecture exhibit at
`/atlas/index.html`. It does not disconnect Aria because it opens a separate
page. The explicit filename is intentional: Next's development server does not
treat a public subdirectory as an automatic index route.

## Twenty-minute release path

Use a clean browser session and one synthetic repository/task:

1. Sign in, create a synthesis, send a typed Aria message, reload, and verify
   the session and turn return.
2. Start voice, navigate through Aria, Handoff, Toolbox, Recall, Graph,
   Timeline, and Audit, then return to Conversation using the orb.
3. Mute, unmute, interrupt speech, stop, and reconnect. Confirm status text is
   understandable without color.
4. Run the overview tour while voice remains connected.
5. Create and rename a profile, adjust every bounded dial, change a supported
   voice, select it, reload, and verify the browser-local selection.
6. Add an alias, then try a normalized duplicate and
   `Approve this handoff.` as an alias. Both invalid cases must be rejected.
   Use the valid alias in voice and verify Realtime routes it to the declared
   semantic command.
7. Inspect DevHub. Correlate one transcript event, call ID, command, arguments,
   result, duration, and status.
8. Disconnect the OpenAI key or deny microphone permission and verify the
   deterministic typed path still works with visible degradation.
9. Prepare a role-labelled screenshot comparison. Verify hashes, dimensions,
   labelled findings, and `retained=false`; raw pixels must not return after
   reload.
10. Ask voice to confirm durable memory. It must leave a pending proposal for a
    human tap.
11. Try partial and wrong-case handoff approval. Only the exact phrase
    **Approve this handoff.** may publish the prepared draft.
12. Load the published handoff from Codex and inspect its activation receipt.
13. Open **Take a step back**, follow one featured claim into source and test,
    reverse into Source lens, and inspect modules, routes, tables, and tests.
14. Delete a non-default profile. Then type the exact phrase
    `Delete Aria voice history.` and verify only stored voice turns, sessions,
    and correlated execution receipts are removed.
15. Repeat the essential path at 375, 768, 1024, and 1440 CSS pixels with
    keyboard-only navigation and reduced motion.

## Severity rubric

| Severity | Meaning | Examples |
|---|---|---|
| Blocker | Judge path or safety boundary fails | Cannot sign in; handoff cannot load; secret/audio retained; memory or publication gate bypassed |
| High | Major promised capability fails | Orb disconnects on navigation; transcript lost; profiles corrupt; atlas unavailable |
| Medium | Workaround exists but confidence drops | DevHub correlation unclear; focus not restored; reconnect guidance weak |
| Low | Presentation defect | Copy, spacing, nonessential animation, or isolated visual polish |

Fix blockers and high-severity defects before regenerating the final atlas
snapshot or recording the submission. Record medium/low issues honestly as
known follow-up unless the fix is small and low-risk.

## Sanitized dogfood receipt

Do not commit credentials, access codes, personal transcripts, raw images,
workspace tokens, or private repository data. A public receipt may contain:

```text
Date/time:
Release commit:
Deployment:
Browser/device:
Viewport:
Path completed:
Live OpenAI features used:
Deterministic fallback checked:
Safety gates checked:
Atlas claim/source trace checked:
Blocker/high defects:
Known medium/low defects:
Decision: pass / conditional pass / fail
```

The receipt remains **pending human verification** until the creator performs
the path. Automated tests do not replace microphone, mobile browser, live
Realtime, clean Codex installation, or judge-URL dogfood.
