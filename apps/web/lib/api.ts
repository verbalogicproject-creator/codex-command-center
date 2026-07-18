export function apiUrl(path: string) {
  return `${process.env.NEXT_PUBLIC_API_BASE ?? ""}${path}`;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    credentials: "same-origin",
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
