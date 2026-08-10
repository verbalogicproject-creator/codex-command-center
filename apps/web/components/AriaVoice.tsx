"use client";

import {useCallback, useEffect, useRef, useState} from "react";
import {Mic, Volume2} from "lucide-react";
import {api} from "@/lib/api";
import {
  ariaRealtimeSessionUpdate, ariaStateDelta, AriaCommand, AriaContextState,
  CommandResult, parseAriaCommand, RegistryCommand,
} from "@/lib/aria/commands";

export type VoiceState =
  "idle" | "connecting" | "listening" | "thinking" | "speaking" | "error";

export type VoiceStatus = {
  state: VoiceState;
  muted: boolean;
  error: string;
  voiceSessionId: string;
};

type RealtimeEvent = {
  type: string;
  transcript?: string;
  delta?: string;
  error?: {message?: string};
  response?: {output?: {
    type?: string; name?: string; call_id?: string; arguments?: string;
  }[]};
};

type TokenResponse = {value: string; expires_at: number};
type Profile = {
  id: string; voice: string; preset: string; tone: number; directness: number;
  verbosity: number; initiative: number;
};

function emitStatus(status: VoiceStatus) {
  window.dispatchEvent(new CustomEvent("aria:voice-status", {detail: status}));
}

export function AriaVoice({
  execute, onOpenAria, conversationSessionId, ensureConversationSession, context, profileId,
}: {
  execute: (command: AriaCommand) => Promise<CommandResult>;
  onOpenAria: () => void;
  conversationSessionId: string;
  ensureConversationSession: () => Promise<string>;
  context: AriaContextState;
  profileId: string;
}) {
  const [state, setState] = useState<VoiceState>("idle");
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState("");
  const [voiceSessionId, setVoiceSessionId] = useState("");
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const channelRef = useRef<RTCDataChannel | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const executeRef = useRef(execute);
  const contextRef = useRef(context);
  const voiceSessionRef = useRef("");
  const projectionRequestRef = useRef(0);

  useEffect(() => { executeRef.current = execute; }, [execute]);
  useEffect(() => { voiceSessionRef.current = voiceSessionId; }, [voiceSessionId]);
  useEffect(() => {
    emitStatus({state, muted, error, voiceSessionId});
  }, [error, muted, state, voiceSessionId]);
  useEffect(() => {
    const report = () => emitStatus({state, muted, error, voiceSessionId});
    window.addEventListener("aria:voice-status-request", report);
    return () => window.removeEventListener("aria:voice-status-request", report);
  }, [error, muted, state, voiceSessionId]);

  const send = useCallback((event: Record<string, unknown>) => {
    if (channelRef.current?.readyState === "open") {
      channelRef.current.send(JSON.stringify(event));
    }
  }, []);

  const disconnectTransport = useCallback(() => {
    const channel = channelRef.current;
    const peer = peerRef.current;
    const stream = streamRef.current;
    const audio = audioRef.current;
    channelRef.current = null;
    peerRef.current = null;
    streamRef.current = null;
    audioRef.current = null;
    channel?.close();
    peer?.close();
    stream?.getTracks().forEach((track) => track.stop());
    if (audio) {
      audio.pause();
      audio.srcObject = null;
    }
  }, []);

  const stop = useCallback(async () => {
    disconnectTransport();
    const id = voiceSessionRef.current;
    if (id) {
      await api(`/api/v1/aria/voice-sessions/${id}/end`, {method: "POST"})
        .catch(() => undefined);
    }
    setVoiceSessionId("");
    setState("idle");
    setMuted(false);
  }, [disconnectTransport]);

  const persistTranscript = useCallback((role: "user" | "assistant", content: string) => {
    const id = voiceSessionRef.current;
    if (!id || !content.trim()) return;
    void api(`/api/v1/aria/voice-sessions/${id}/transcript`, {
      method: "POST",
      body: JSON.stringify({role, content, metadata: {transport: "openai-realtime"}}),
    }).then(() => {
      window.dispatchEvent(new CustomEvent("aria:transcript-stored"));
    }).catch(() => undefined);
  }, []);

  const returnToolResult = useCallback((callId: string, result: CommandResult) => {
    send({
      type: "conversation.item.create",
      item: {type: "function_call_output", call_id: callId, output: JSON.stringify(result)},
    });
  }, [send]);

  const handleEvent = useCallback(async (event: RealtimeEvent) => {
    if (event.type === "input_audio_buffer.speech_started") setState("listening");
    if (event.type === "input_audio_buffer.speech_stopped") setState("thinking");
    if (event.type === "conversation.item.input_audio_transcription.completed") {
      persistTranscript("user", event.transcript ?? "");
    }
    if (
      event.type === "response.output_audio_transcript.delta"
      || event.type === "response.audio_transcript.delta"
    ) setState("speaking");
    if (
      event.type === "response.output_audio_transcript.done"
      || event.type === "response.audio_transcript.done"
    ) persistTranscript("assistant", event.transcript ?? "");
    if (event.type === "response.done") {
      const calls = (event.response?.output ?? []).filter(
        (item) => item.type === "function_call" && item.name && item.call_id,
      );
      if (!calls.length) {
        setState("listening");
        return;
      }
      setState("thinking");
      for (const call of calls) {
        const started = performance.now();
        let result: CommandResult;
        let commandId = call.name!;
        let failure = "";
        try {
          const command = parseAriaCommand(call.name!, call.arguments ?? "{}");
          commandId = command.name;
          result = await executeRef.current(command);
          returnToolResult(call.call_id!, result);
        } catch (reason) {
          failure = reason instanceof Error ? reason.message : "The command failed.";
          result = {
            ok: false,
            message: failure,
          };
          returnToolResult(call.call_id!, result);
        }
        void api("/api/v1/aria/executions", {
          method: "POST",
          body: JSON.stringify({
            voice_session_id: voiceSessionRef.current,
            call_id: call.call_id,
            command_id: commandId,
            surface: contextRef.current.surface,
            arguments: (() => {
              try { return JSON.parse(call.arguments ?? "{}"); } catch { return {}; }
            })(),
            result,
            status: failure ? "failed" : result.ok ? "succeeded" : "refused",
            duration_ms: Math.round(performance.now() - started),
            error: failure || undefined,
          }),
        }).then(() => {
          window.dispatchEvent(new CustomEvent("aria:execution-stored"));
        }).catch(() => undefined);
      }
      send({type: "response.create"});
    }
    if (event.type === "error") {
      disconnectTransport();
      const message = event.error?.message ?? "Realtime voice reported an error.";
      const id = voiceSessionRef.current;
      if (id) {
        void api(
          `/api/v1/aria/voice-sessions/${id}/end?degraded_reason=${encodeURIComponent(message)}`,
          {method: "POST"},
        ).catch(() => undefined);
      }
      voiceSessionRef.current = "";
      setVoiceSessionId("");
      setError(message);
      setState("error");
    }
  }, [disconnectTransport, persistTranscript, returnToolResult, send]);

  const connect = useCallback(async () => {
    if (state !== "idle" && state !== "error") return;
    setError("");
    setState("connecting");
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.RTCPeerConnection) {
        throw new Error("This browser does not support secure microphone voice sessions.");
      }
      const [{items: commands}, {items: profiles}, token] = await Promise.all([
        api<{items: RegistryCommand[]}>(
          `/api/v1/aria/commands?surface=${context.surface}&profile_id=${profileId}`,
        ),
        api<{items: Profile[]}>("/api/v1/aria/profiles"),
        api<TokenResponse>("/api/v1/realtime/token", {method: "POST"}),
      ]);
      const transcriptSessionId = conversationSessionId || await ensureConversationSession();
      const voiceSession = await api<{id: string}>("/api/v1/aria/voice-sessions", {
        method: "POST",
        body: JSON.stringify({
          profile_id: profileId,
          conversation_session_id: transcriptSessionId,
        }),
      });
      setVoiceSessionId(voiceSession.id);
      voiceSessionRef.current = voiceSession.id;
      const profile = profiles.find((item) => item.id === profileId) ?? profiles[0];
      const peer = new RTCPeerConnection();
      const audio = document.createElement("audio");
      audio.autoplay = true;
      peer.ontrack = (trackEvent) => {
        audio.srcObject = trackEvent.streams[0];
        setState("speaking");
      };
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true},
      });
      const track = stream.getAudioTracks()[0];
      if (!track) throw new Error("No microphone audio track was available.");
      peer.addTrack(track, stream);
      const channel = peer.createDataChannel("oai-events");
      channel.addEventListener("open", () => {
        channel.send(JSON.stringify(ariaRealtimeSessionUpdate({
          commands, persona: profile, state: context,
        })));
        void api(`/api/v1/aria/voice-sessions/${voiceSession.id}/state?state=active`, {
          method: "POST",
        }).catch(() => undefined);
        setState("listening");
      });
      channel.addEventListener("message", (message) => {
        try {
          void handleEvent(JSON.parse(message.data) as RealtimeEvent);
        } catch {
          setError("Aria received an unreadable voice event.");
          setState("error");
        }
      });
      channel.addEventListener("close", () => {
        if (channelRef.current === channel) {
          disconnectTransport();
          const id = voiceSessionRef.current;
          const message = "Realtime voice disconnected. Reconnect to continue.";
          voiceSessionRef.current = "";
          if (id) {
            void api(
              `/api/v1/aria/voice-sessions/${id}/end?degraded_reason=${encodeURIComponent(message)}`,
              {method: "POST"},
            ).catch(() => undefined);
          }
          setVoiceSessionId("");
          setError(message);
          setState("error");
        }
      });
      peerRef.current = peer;
      channelRef.current = channel;
      streamRef.current = stream;
      audioRef.current = audio;
      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      const response = await fetch("https://api.openai.com/v1/realtime/calls", {
        method: "POST",
        body: offer.sdp,
        headers: {Authorization: `Bearer ${token.value}`, "Content-Type": "application/sdp"},
      });
      if (!response.ok) throw new Error(`Voice connection failed (${response.status}).`);
      await peer.setRemoteDescription({type: "answer", sdp: await response.text()});
    } catch (reason) {
      disconnectTransport();
      const message = reason instanceof Error ? reason.message : "Could not start Aria voice.";
      const id = voiceSessionRef.current;
      if (id) {
        void api(
          `/api/v1/aria/voice-sessions/${id}/end?degraded_reason=${encodeURIComponent(message)}`,
          {method: "POST"},
        ).catch(() => undefined);
      }
      voiceSessionRef.current = "";
      setVoiceSessionId("");
      setError(message);
      setState("error");
    }
  }, [
    context, conversationSessionId, disconnectTransport, ensureConversationSession,
    handleEvent, profileId, state,
  ]);

  useEffect(() => () => {
    disconnectTransport();
    const id = voiceSessionRef.current;
    voiceSessionRef.current = "";
    if (id) {
      void api(`/api/v1/aria/voice-sessions/${id}/end`, {method: "POST"})
        .catch(() => undefined);
    }
  }, [disconnectTransport]);
  useEffect(() => {
    const previous = contextRef.current;
    contextRef.current = context;
    if (channelRef.current?.readyState === "open") send(ariaStateDelta(previous, context));
  }, [context, send]);
  const refreshProjection = useCallback(async () => {
    if (channelRef.current?.readyState !== "open") return;
    const request = ++projectionRequestRef.current;
    const current = contextRef.current;
    const [{items: commands}, {items: profiles}] = await Promise.all([
      api<{items: RegistryCommand[]}>(
        `/api/v1/aria/commands?surface=${current.surface}`
        + `&profile_id=${profileId}`
        + (current.workflow ? `&workflow=${encodeURIComponent(current.workflow)}` : ""),
      ),
      api<{items: Profile[]}>("/api/v1/aria/profiles"),
    ]);
    if (request !== projectionRequestRef.current) return;
    const profile = profiles.find((item) => item.id === profileId) ?? profiles[0];
    send(ariaRealtimeSessionUpdate({commands, persona: profile, state: current}));
  }, [profileId, send]);
  useEffect(() => {
    void refreshProjection().catch(() => undefined);
  }, [context.surface, context.workflow, profileId, refreshProjection]);
  useEffect(() => {
    const refresh = () => void refreshProjection().catch(() => undefined);
    window.addEventListener("aria:registry-updated", refresh);
    return () => window.removeEventListener("aria:registry-updated", refresh);
  }, [refreshProjection]);
  useEffect(() => {
    const control = (event: Event) => {
      const action = (event as CustomEvent<{action: string}>).detail?.action;
      if (action === "start" || action === "reconnect") void connect();
      if (action === "stop") void stop();
      if (action === "mute") {
        const track = streamRef.current?.getAudioTracks()[0];
        if (track) {
          track.enabled = !track.enabled;
          setMuted(!track.enabled);
        }
      }
    };
    window.addEventListener("aria:voice-control", control);
    return () => window.removeEventListener("aria:voice-control", control);
  }, [connect, stop]);

  const label = state === "idle" ? "Start voice"
    : state === "connecting" ? "Connecting"
      : state === "listening" ? "Listening"
        : state === "thinking" ? "Thinking"
          : state === "speaking" ? "Speaking" : "Voice error";

  return <button
    className={`voice-orb ${state}`}
    aria-label={state === "idle" || state === "error"
      ? "Start Aria voice" : "Open Aria conversation"}
    onClick={() => state === "idle" || state === "error" ? void connect() : onOpenAria()}
  >
    <span className="voice-rings" aria-hidden="true" />
    {state === "speaking" ? <Volume2 /> : <Mic />}
    <small>{label}</small>
  </button>;
}
