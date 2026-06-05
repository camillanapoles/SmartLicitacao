/**
 * @jest-environment node
 *
 * UX-434 / ENTITY-003: /api/alerts proxy route tests.
 * Now a proxy (createProxyRoute) instead of a stub — tests validate
 * auth gating, backend forwarding, and error handling.
 */
import { GET, POST } from "@/app/api/alerts/route";
import { NextRequest } from "next/server";

// Mock fetch globally
global.fetch = jest.fn();

const AUTH_HEADER = "Bearer test-token-ux434";

// Set BACKEND_URL for all tests
process.env.BACKEND_URL = "http://test-backend:8000";

/** Helper: create a mock fetch response */
function mockResponse(status: number, body: unknown) {
  const bodyStr = JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => bodyStr,
    headers: {
      get: (h: string) =>
        h.toLowerCase() === "content-type" ? "application/json" : null,
    },
  };
}

describe("GET /api/alerts (proxy)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns 401 when Authorization header is missing", async () => {
    const req = new NextRequest("http://localhost:3000/api/alerts");
    const res = await GET(req);
    expect(res.status).toBe(401);
    // Auth check happens before fetch — fetch should never be called
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("returns 200 with backend data when authenticated", async () => {
    const backendData = [{ id: "1", name: "Alerta Teste" }];
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      mockResponse(200, backendData)
    );

    const req = new NextRequest("http://localhost:3000/api/alerts", {
      headers: { Authorization: AUTH_HEADER },
    });
    const res = await GET(req);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body).toEqual(backendData);

    // Verify backend was called with auth header
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/v1/alerts"),
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: AUTH_HEADER,
        }),
      })
    );
  });

  it("returns 200 with empty array when backend returns empty", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      mockResponse(200, [])
    );

    const req = new NextRequest("http://localhost:3000/api/alerts", {
      headers: { Authorization: AUTH_HEADER },
    });
    const res = await GET(req);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body).toHaveLength(0);
  });

  it("proxies backend 404 status", async () => {
    // Proxy forwards backend response including 404 (unlike old stub)
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      mockResponse(404, { message: "Not found" })
    );

    const req = new NextRequest("http://localhost:3000/api/alerts", {
      headers: { Authorization: AUTH_HEADER },
    });
    const res = await GET(req);
    expect(res.status).toBe(404); // Proxy forwards backend status
  });

  it("returns 503 on network error", async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(
      new Error("connect ECONNREFUSED")
    );

    const req = new NextRequest("http://localhost:3000/api/alerts", {
      headers: { Authorization: AUTH_HEADER },
    });
    const res = await GET(req);
    // Network errors are sanitized to 503
    expect(res.status).toBe(503);
  });
});

describe("POST /api/alerts (proxy)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns 401 when Authorization header is missing", async () => {
    const req = new NextRequest("http://localhost:3000/api/alerts", {
      method: "POST",
      body: JSON.stringify({ name: "Alerta Teste" }),
    });
    const res = await POST(req);
    expect(res.status).toBe(401);
    // Auth check happens before fetch
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("returns 200 when authenticated and backend responds", async () => {
    const backendResponse = { id: "new-1", name: "Alerta Teste" };
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      mockResponse(201, backendResponse)
    );

    const req = new NextRequest("http://localhost:3000/api/alerts", {
      method: "POST",
      headers: { Authorization: AUTH_HEADER },
      body: JSON.stringify({ name: "Alerta Teste" }),
    });
    const res = await POST(req);
    expect(res.status).toBe(201);

    // Verify backend was called with correct method and body
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/v1/alerts"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Authorization": AUTH_HEADER,
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({ name: "Alerta Teste" }),
      })
    );
  });

  it("proxies backend 404 status for POST", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      mockResponse(404, { message: "Not found" })
    );

    const req = new NextRequest("http://localhost:3000/api/alerts", {
      method: "POST",
      headers: { Authorization: AUTH_HEADER },
      body: JSON.stringify({}),
    });
    const res = await POST(req);
    expect(res.status).toBe(404); // Proxy forwards backend status
  });

  it("returns 503 on network error", async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(
      new Error("connect ECONNREFUSED")
    );

    const req = new NextRequest("http://localhost:3000/api/alerts", {
      method: "POST",
      headers: { Authorization: AUTH_HEADER },
      body: JSON.stringify({ name: "Alerta Teste" }),
    });
    const res = await POST(req);
    expect(res.status).toBe(503);
  });
});
