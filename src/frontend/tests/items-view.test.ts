/** @vitest-environment happy-dom */
import { afterEach, describe, expect, it, vi } from "vitest";

import { mountItemsView } from "../src/ui/items-view";

interface RawItem {
  id: string;
  name: string;
  description: string | null;
  quantity: number;
  tags: string[];
  created_at: string;
  updated_at: string;
}

function jsonResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

const sampleItem: RawItem = {
  id: "0".repeat(24),
  name: "Widget",
  description: null,
  quantity: 2,
  tags: ["x"],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("mountItemsView", () => {
  it("renders items returned by the API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([sampleItem])));
    const root = document.createElement("div");

    mountItemsView(root);

    await vi.waitFor(() => {
      expect(root.querySelector(".item__name")?.textContent).toBe("Widget");
    });
  });

  it("surfaces an error status when the API fails", async () => {
    const body = { error: { code: "internal_error", message: "boom" } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(body, 500)));
    const root = document.createElement("div");

    mountItemsView(root);

    await vi.waitFor(() => {
      const status = root.querySelector(".status");
      expect(status?.className).toContain("status--error");
      expect(status?.textContent).toContain("boom");
    });
  });

  it("issues a POST request when the create form is submitted", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ ...sampleItem, name: "New" }, 201))
      .mockResolvedValueOnce(jsonResponse([{ ...sampleItem, name: "New" }]));
    vi.stubGlobal("fetch", fetchMock);
    const root = document.createElement("div");

    mountItemsView(root);
    await vi.waitFor(() => {
      expect(root.querySelector(".status")?.textContent).toContain("No items yet");
    });

    const nameInput = root.querySelector<HTMLInputElement>("#name");
    const form = root.querySelector("form");
    if (!nameInput || !form) {
      throw new Error("form elements are missing");
    }
    nameInput.value = "New";
    form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));

    await vi.waitFor(() => {
      expect(root.querySelector(".item__name")?.textContent).toBe("New");
    });

    const methods = fetchMock.mock.calls.map((call) => {
      const init = call[1] as RequestInit | undefined;
      return init?.method ?? "GET";
    });
    expect(methods).toContain("POST");
  });

  it("advances to the next page when Next is clicked", async () => {
    const pageItems = Array.from({ length: 8 }, (_unused, index) => ({
      ...sampleItem,
      id: String(index).padStart(24, "0"),
      name: `Item ${String(index)}`,
    }));
    const fetchMock = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(jsonResponse(pageItems, 200, { "X-Total-Count": "20" })),
      );
    vi.stubGlobal("fetch", fetchMock);
    const root = document.createElement("div");

    mountItemsView(root);
    await vi.waitFor(() => {
      expect(root.querySelectorAll(".item")).toHaveLength(8);
    });

    const next = root.querySelector<HTMLButtonElement>('button[aria-label="Next page"]');
    if (!next) {
      throw new Error("next button is missing");
    }
    next.dispatchEvent(new Event("click", { bubbles: true }));

    await vi.waitFor(() => {
      const advanced = fetchMock.mock.calls.some((call) => String(call[0]).includes("skip=8"));
      expect(advanced).toBe(true);
    });
  });
});
