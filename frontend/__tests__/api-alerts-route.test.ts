/**
 * @jest-environment node
 *
 * ENTITY-003 / UX-434: /api/alerts proxy route tests.
 * Now uses createProxyRoute (real proxy to backend), not a stub.
 */
import { GET, POST } from "../app/api/alerts/route";
import { NextRequest } from "next/server";

// Mock fetch globally
global.fetch = jest.fn();

const AUTH = "Bearer test-token-123";

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

describe("/api/alerts route handlers", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("GET /api/alerts", () => {
    it("returns 200 with backend data when authenticated", async () => {
      const backendData = [{ id: "1", name: "Teste" }];
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse(200, backendData)
      );

      const req = new NextRequest("http://localhost:3000/api/alerts", {
        headers: { Authorization: AUTH },
      });
      const res = await GET(req);
      expect(res.status).toBe(200);
      const data = await res.json();
      expect(Array.isArray(data)).toBe(true);
      expect(data).toEqual(backendData);

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/v1/alerts"),
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({ Authorization: AUTH }),
        })
      );
    });

    it("returns 401 when no authorization header", async () => {
      const req = new NextRequest("http://localhost:3000/api/alerts");
      const res = await GET(req);
      const data = await res.json();
      expect(res.status).toBe(401);
      expect(data.message).toBeDefined();
      // Auth check happens before fetch
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it("proxies backend status (no hardcoded 404 handling)", async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse(404, { message: "Not found" })
      );

      const req = new NextRequest("http://localhost:3000/api/alerts", {
        headers: { Authorization: AUTH },
      });
      const res = await GET(req);
      expect(res.status).toBe(404); // Proxy forwards backend status
    });
  });

  describe("POST /api/alerts", () => {
    it("returns backend status when authenticated", async () => {
      const backendResponse = { id: "new-1", name: "Alerta Teste" };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse(201, backendResponse)
      );

      const req = new NextRequest("http://localhost:3000/api/alerts", {
        method: "POST",
        headers: { Authorization: AUTH },
        body: JSON.stringify({ name: "Alerta Teste" }),
      });
      const res = await POST(req);
      expect(res.status).toBe(201);

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/v1/alerts"),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            "Authorization": AUTH,
            "Content-Type": "application/json",
          }),
          body: JSON.stringify({ name: "Alerta Teste" }),
        })
      );
    });

    it("returns 401 for POST without auth header", async () => {
      const req = new NextRequest("http://localhost:3000/api/alerts", {
        method: "POST",
        body: JSON.stringify({ name: "Test" }),
      });
      const res = await POST(req);
      const data = await res.json();
      expect(res.status).toBe(401);
      expect(data.message).toBeDefined();
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it("proxies backend status for POST", async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse(404, { message: "Not found" })
      );

      const req = new NextRequest("http://localhost:3000/api/alerts", {
        method: "POST",
        headers: { Authorization: AUTH },
        body: JSON.stringify({}),
      });
      const res = await POST(req);
      expect(res.status).toBe(404); // Proxy forwards backend status
    });
  });
});
