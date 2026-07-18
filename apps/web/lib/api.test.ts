import {afterEach, describe, expect, it, vi} from "vitest";
import {api, apiUrl} from "./api";

describe("api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("returns typed JSON and sends same-origin credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({memories: 46}),
    });
    vi.stubGlobal("fetch", fetchMock);
    await expect(api<{memories: number}>("/api/v1/status")).resolves.toEqual({memories: 46});
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/status", expect.objectContaining({
      credentials: "include",
    }));
  });

  it("keeps loopback API requests on the browser hostname for cookie continuity", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://127.0.0.1:8000");
    expect(apiUrl("/api/v1/status")).toBe("http://localhost:8000/api/v1/status");
  });

  it("unwraps structured API errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({error: {code: "unauthorized", message: "Sign in required"}}),
    }));
    await expect(api("/api/v1/status")).rejects.toThrow("Sign in required");
  });
});
