/** @vitest-environment happy-dom */
import { afterEach, describe, expect, it, vi } from "vitest";

import { listItems } from "../src/api/items";

interface RawItem {
  id: string;
  name: string;
  description: string | null;
  quantity: number;
  tags: string[];
  created_at: string;
  updated_at: string;
}

const sampleItem: RawItem = {
  id: "0".repeat(24),
  name: "Widget",
  description: null,
  quantity: 1,
  tags: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function jsonResponse(body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json", ...headers },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("listItems", () => {
  it("reads the total from the X-Total-Count header", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse([sampleItem], { "X-Total-Count": "42" })),
    );
    const page = await listItems({ limit: 8, skip: 0 });
    expect(page.total).toBe(42);
    expect(page.items).toHaveLength(1);
  });

  it("falls back to the item count when the header is absent", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([sampleItem])));
    const page = await listItems();
    expect(page.total).toBe(1);
  });

  it("passes search and pagination parameters in the query string", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);
    await listItems({ q: "abc", limit: 5, skip: 10 });
    const url = String(fetchMock.mock.calls[0]?.[0] ?? "");
    expect(url).toContain("q=abc");
    expect(url).toContain("limit=5");
    expect(url).toContain("skip=10");
  });
});
