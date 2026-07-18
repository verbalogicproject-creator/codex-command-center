"use client";

import {useCallback, useEffect, useRef, useState} from "react";
import {Mic, Minimize2, Square, Volume2} from "lucide-react";
import {api} from "@/lib/api";
import {
  ariaRealtimeSessionUpdate, AriaCommand, CommandResult,
  parseAriaCommand,
} from "@/lib/aria/commands";

type VoiceState = "idle" | "connecting" | "listening" | "thinking" | "speaking" | "error";

type RealtimeEvent = {
  type: string;
  transcript?: string;
  delta?: string;
  error?: {message?: string};
  response?: {
    output?: {
      type?: string; name?: string; call_id?: string; arguments?: string;
    }[];
  };
};

type TokenResponse = {value: string; expires_at: number};

export function AriaVoice({
  execute,
}: {
  execute: (command: AriaCommand) => Promise<CommandResult>;
}) {
  const [state, setState] = useState<VoiceState>("idle");
  const [open, setOpen] = useState(false);
  const [userTranscript, setUserTranscript] = useState("");
  const [ariaTranscript, setAriaTranscript] = useState("");
  const [error, setError] = useState("");
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const channelRef = useRef<RTCDataChannel | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const executeRef = useRef(execute);

  useEffect(() => {
    executeRef.current = execute;
  }, [execute]);

  const send = useCallback((event: Record<string, unknown>) => {
    const channel = channelRef.current;
    if (channel?.readyState === "open") channel.send(JSON.stringify(event));
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

  const stop = useCallback(() => {
    disconnectTransport();
    setState("idle");
  }, [disconnectTransport]);

  const returnToolResult = useCallback((callId: string, result: CommandResult) => {
    send({
      type: "conversation.item.create",
      item: {
        type: "function_call_output",
        call_id: callId,
        output: JSON.stringify(result),
      },
    });
  }, [send]);

  const handleEvent = useCallback(async (event: RealtimeEvent) => {
    if (event.type === "input_audio_buffer.speech_started") {
      setState("listening");
      setUserTranscript("");
      setAriaTranscript("");
    }
    if (event.type === "input_audio_buffer.speech_stopped") setState("thinking");
    if (event.type === "conversation.item.input_audio_transcription.completed") {
      setUserTranscript(event.transcript ?? "");
    }
    if (
      event.type === "response.output_audio_transcript.delta"
      || event.type === "response.audio_transcript.delta"
    ) {
      setState("speaking");
      setAriaTranscript((value) => value + (event.delta ?? ""));
    }
    if (event.type === "response.done") {
      const calls = (event.response?.output ?? []).filter((item) =>
        item.type === "function_call" && item.name && item.call_id,
      );
      if (!calls.length) {
        setState("listening");
        return;
      }
      setState("thinking");
      for (const call of calls) {
        try {
          const command = parseAriaCommand(call.name!, call.arguments ?? "{}");
          const result = await executeRef.current(command);
          if (command.name === "start_guided_tour") setOpen(false);
          returnToolResult(call.call_id!, result);
        } catch (reason) {
          returnToolResult(call.call_id!, {
            ok: false,
            message: reason instanceof Error ? reason.message : "The command failed.",
          });
        }
      }
      send({type: "response.create"});
    }
    if (event.type === "error") {
      disconnectTransport();
      setError(event.error?.message ?? "Realtime voice reported an error.");
      setState("error");
    }
  }, [disconnectTransport, returnToolResult, send]);

  const connect = useCallback(async () => {
    if (state !== "idle" && state !== "error") return;
    setOpen(true);
    setError("");
    setUserTranscript("");
    setAriaTranscript("");
    setState("connecting");
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.RTCPeerConnection) {
        throw new Error("This browser does not support secure microphone voice sessions.");
      }
      const token = await api<TokenResponse>("/api/v1/realtime/token", {method: "POST"});
      const peer = new RTCPeerConnection();
      const audio = document.createElement("audio");
      audio.autoplay = true;
      peer.ontrack = (event) => {
        audio.srcObject = event.streams[0];
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
        channel.send(JSON.stringify(ariaRealtimeSessionUpdate()));
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
          setState("idle");
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
        headers: {
          Authorization: `Bearer ${token.value}`,
          "Content-Type": "application/sdp",
        },
      });
      if (!response.ok) throw new Error(`Voice connection failed (${response.status}).`);
      await peer.setRemoteDescription({
        type: "answer",
        sdp: await response.text(),
      });
    } catch (reason) {
      disconnectTransport();
      setOpen(true);
      setError(reason instanceof Error ? reason.message : "Could not start Aria voice.");
      setState("error");
    }
  }, [disconnectTransport, handleEvent, state]);

  useEffect(() => stop, [stop]);
  useEffect(() => {
    const minimizeForTour = () => setOpen(false);
    window.addEventListener("aria:tour-started", minimizeForTour);
    return () => window.removeEventListener("aria:tour-started", minimizeForTour);
  }, []);

  const label = state === "idle" ? "Start voice"
    : state === "connecting" ? "Connecting"
      : state === "listening" ? "Listening"
        : state === "thinking" ? "Thinking"
          : state === "speaking" ? "Speaking" : "Voice error";

  return <>
    <button
      className={`voice-orb ${state}`}
      aria-label={state === "idle" || state === "error"
        ? "Start Aria voice"
        : open ? "Hide Aria transcript" : "Show Aria transcript"}
      aria-expanded={state !== "idle" && state !== "error" ? open : undefined}
      onClick={() => state === "idle" || state === "error"
        ? void connect()
        : setOpen((visible) => !visible)}
    >
      <span className="voice-rings" aria-hidden="true" />
      {state === "speaking" ? <Volume2 /> : <Mic />}
      <small>{label}</small>
    </button>
    {open && <aside className={`voice-panel ${state}`} data-aria-target="voice">
      <header>
        <span><i /> ARIA VOICE</span>
        <button className="icon-button" aria-label="Hide Aria transcript"
          onClick={() => setOpen(false)}><Minimize2 /></button>
      </header>
      <div className="voice-status" role="status" aria-live="polite">
        <strong>{label}</strong>
        <small>OpenAI Realtime · browser microphone</small>
      </div>
      {userTranscript && <p><b>YOU</b>{userTranscript}</p>}
      {ariaTranscript && <p><b>ARIA</b>{ariaTranscript}</p>}
      {error && <p className="voice-error">{error}</p>}
      <footer>
        <div><span>Voice may navigate, draft, and publish bounded handoffs.</span>
          <strong>Memory confirmation always requires a tap.</strong></div>
        <button className="voice-stop" onClick={() => {
          stop();
          setOpen(false);
        }}><Square /> Stop voice</button>
      </footer>
    </aside>}
  </>;
}
