import {afterEach, describe, expect, it, vi} from "vitest";
import {api} from "./api";

describe("api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns typed JSON and sends same-origin credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({memories: 46}),
    });
    vi.stubGlobal("fetch", fetchMock);
    await expect(api<{memories: number}>("/api/v1/status")).resolves.toEqual({memories: 46});
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/status", expect.objectContaining({
      credentials: "same-origin",
    }));
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
