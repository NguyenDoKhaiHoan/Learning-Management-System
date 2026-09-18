import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiRequestError } from "../../src/services/api/client";

const user = {
  id: "1",
  email: "test@example.test",
  username: "test",
  roles: ["STUDENT"],
};
const tokens = (n: number) => ({
  access_token: `access-${n}`,
  refresh_token: `refresh-${n}`,
  token_type: "bearer",
  expires_in: 900,
  refresh_expires_in: 3600,
});
const ok = (data: unknown) =>
  new Response(
    JSON.stringify({
      code: "OK",
      message: "Success",
      data,
      trace_id: "trace-test",
    }),
  );
const error = (status: number) =>
  new Response(
    JSON.stringify({
      code: "ERROR",
      message: "Denied",
      details: [],
      trace_id: "trace-test",
    }),
    { status },
  );
function fixture(
  handler: (path: string, init?: RequestInit) => Promise<Response>,
) {
  const fetcher = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = String(url);
    if (path.endsWith("/auth/login")) return ok(tokens(1));
    if (path.endsWith("/auth/me")) return ok(user);
    return handler(path, init);
  });
  return { client: new ApiClient(fetcher), fetcher };
}

describe("API client", () => {
  it("uses current bearer token, JSON body and success envelope", async () => {
    const { client, fetcher } = fixture(async () => ok({ id: "42" }));
    expect(await client.login("test", "password")).toEqual(user);
    expect(await client.request("/courses", "POST", { title: "Test" })).toEqual(
      { id: "42" },
    );
    expect(fetcher.mock.lastCall?.[1]).toMatchObject({
      method: "POST",
      headers: {
        Authorization: "Bearer access-1",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ title: "Test" }),
      credentials: "omit",
    });
  });

  it("shares one rotation across simultaneous 401 responses and retries once", async () => {
    let refreshes = 0;
    const { client } = fixture(async (path, init) => {
      if (path.endsWith("/auth/refresh")) {
        refreshes++;
        await new Promise((resolve) => setTimeout(resolve, 10));
        return ok(tokens(2));
      }
      return (init?.headers as Record<string, string>).Authorization ===
        "Bearer access-1"
        ? error(401)
        : ok("loaded");
    });
    await client.login("test", "password");
    expect(
      await Promise.all([
        client.request("/courses"),
        client.request("/enrollments/me"),
      ]),
    ).toEqual(["loaded", "loaded"]);
    expect(refreshes).toBe(1);
  });

  it("does not refresh or clear the session on 403 and preserves trace ID", async () => {
    const { client, fetcher } = fixture(async () => error(403));
    await client.login("test", "password");
    await expect(client.request("/courses")).rejects.toMatchObject({
      status: 403,
      traceId: "trace-test",
    });
    expect(client.authenticated).toBe(true);
    expect(
      fetcher.mock.calls.some(([url]) => String(url).endsWith("/auth/refresh")),
    ).toBe(false);
  });

  it("clears invalid refresh sessions and notifies the route guard", async () => {
    const { client } = fixture(async () => error(401));
    client.onSessionLost = vi.fn();
    await client.login("test", "password");
    await expect(client.request("/courses")).rejects.toMatchObject({
      status: 401,
    });
    expect(client.authenticated).toBe(false);
    expect(client.onSessionLost).toHaveBeenCalledOnce();
  });

  it("never loops if the replacement access token is also rejected", async () => {
    const { client, fetcher } = fixture(async (path) =>
      path.endsWith("/auth/refresh") ? ok(tokens(2)) : error(401),
    );
    await client.login("test", "password");
    await expect(client.request("/courses")).rejects.toMatchObject({
      status: 401,
    });
    expect(
      fetcher.mock.calls.filter(([url]) => String(url).endsWith("/courses")),
    ).toHaveLength(2);
    expect(client.authenticated).toBe(false);
  });

  it("cannot resurrect a logged-out session when rotation finishes late", async () => {
    let release!: (value: Response) => void;
    const { client } = fixture(async (path) => {
      if (path.endsWith("/auth/refresh"))
        return new Promise<Response>((resolve) => {
          release = resolve;
        });
      if (path.endsWith("/auth/logout")) return ok({ logged_out: true });
      return error(401);
    });
    await client.login("test", "password");
    const result = client.request("/courses").catch((error) => error);
    await vi.waitFor(() => expect(release).toBeDefined());
    await client.logout();
    release(ok(tokens(2)));
    expect(await result).toBeInstanceOf(ApiRequestError);
    expect(client.authenticated).toBe(false);
  });

  it("reports transport errors and malformed responses", async () => {
    const { client } = fixture(async (path) => {
      if (path === "/api/v1/network") throw new Error("offline");
      return new Response("null");
    });
    await client.login("test", "password");
    await expect(client.request("/network")).rejects.toMatchObject({
      code: "NETWORK_ERROR",
    });
    await expect(client.request("/invalid")).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
    });
  });

  it("does not send protected requests without login", async () => {
    const { client, fetcher } = fixture(async () => ok(null));
    await expect(client.request("/courses")).rejects.toMatchObject({
      status: 401,
    });
    expect(fetcher).not.toHaveBeenCalled();
  });
});
