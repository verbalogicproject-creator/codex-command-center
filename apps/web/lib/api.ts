export function apiUrl(path: string) {
  const configuredBase = process.env.NEXT_PUBLIC_API_BASE ?? "";
  if (!configuredBase) return path;

  const base = new URL(configuredBase);
  if (typeof window !== "undefined") {
    const loopback = new Set(["localhost", "127.0.0.1", "::1"]);
    if (loopback.has(base.hostname) && loopback.has(window.location.hostname)) {
      // Cookies are hostname-scoped. Keep the API on the same loopback name
      // the user opened, even when dev.sh supplied a different loopback alias.
      base.hostname = window.location.hostname;
    }
  }
  return new URL(path, base).toString();
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    credentials: "include",
    headers: {"Content-Type": "application/json", ...init?.headers},
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body?.error?.message ?? `Request failed (${response.status})`);
  }
  return body as T;
}

export async function readSSE(
  response: Response,
  onEvent: (type: string, data: unknown) => void,
) {
  if (!response.ok || !response.body) throw new Error("Chat stream unavailable");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, {stream: true});
    const packets = buffer.split("\n\n");
    buffer = packets.pop() ?? "";
    for (const packet of packets) {
      const type = packet.match(/^event: (.+)$/m)?.[1] ?? "message";
      const data = packet.match(/^data: (.+)$/m)?.[1];
      if (data) onEvent(type, JSON.parse(data));
    }
  }
}
