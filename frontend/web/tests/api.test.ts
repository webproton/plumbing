import { afterEach, describe, expect, it, vi } from "vitest";

import { Api, ApiError, toFieldErrors } from "~/lib/api.server";
import { sessionStorage } from "~/lib/session.server";

function json(status: number, body: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function makeApi(data: Record<string, unknown> = {}) {
  const session = await sessionStorage.getSession();
  for (const [k, v] of Object.entries(data)) session.set(k as never, v as never);
  return { session, api: new Api(session, "203.0.113.7") };
}

afterEach(() => vi.unstubAllGlobals());

describe("toFieldErrors", () => {
  it("flattens DRF errors", () => {
    expect(toFieldErrors({ email: ["Обязательное поле."], non_field_errors: ["Неверный пароль"] })).toEqual({
      email: "Обязательное поле.",
      form: "Неверный пароль",
    });
    expect(toFieldErrors({ detail: "Нет доступа", code: "x" })).toEqual({ form: "Нет доступа" });
  });
});

describe("Api", () => {
  it("sends bearer token and client IP", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(200, { ok: 1 }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await makeApi({ access: "A1" });
    await api.get("/products/", { query: { page: 2, empty: "" } });
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/products\/\?page=2$/);
    expect(init.headers.Authorization).toBe("Bearer A1");
    expect(init.headers["X-Real-IP"]).toBe("203.0.113.7");
  });

  it("refreshes expired access token once and stores the new one", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(401, { detail: "expired" }))
      .mockResolvedValueOnce(json(200, { access: "A2", refresh: "R2" }))
      .mockResolvedValueOnce(json(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    const { api, session } = await makeApi({ access: "A1", refresh: "R1" });
    await expect(api.get("/dj-rest-auth/profile/")).resolves.toEqual({ ok: true });
    expect(session.get("access")).toBe("A2");
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe("Bearer A2");
  });

  it("falls back to guest when the session is dead", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(401, {}))
      .mockResolvedValueOnce(json(401, { detail: "refresh expired" }))
      .mockResolvedValueOnce(json(200, []));
    vi.stubGlobal("fetch", fetchMock);
    const { api, session } = await makeApi({ access: "A1", refresh: "R1", user: { email: "a@b.c", name: "" } });
    await expect(api.get("/category/")).resolves.toEqual([]);
    expect(session.has("user")).toBe(false);
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBeUndefined();
  });

  it("throws ApiError with body on failure and 503 when unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(400, { detail: "x", code: "insufficient_stock" })));
    const { api } = await makeApi();
    const err = await api.post("/orders/order-create/", {}).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("insufficient_stock");

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("ECONNREFUSED")));
    expect((await api.get("/x/").catch((e) => e)).status).toBe(503);
  });
});
