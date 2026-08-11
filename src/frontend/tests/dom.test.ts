/** @vitest-environment happy-dom */
import { describe, expect, it } from "vitest";

import { el } from "../src/ui/dom";

describe("el", () => {
  it("assigns class, attributes, and text children", () => {
    const node = el("button", { class: "btn", type: "button", "aria-label": "Save" }, ["Save"]);
    expect(node.className).toBe("btn");
    expect(node.getAttribute("type")).toBe("button");
    expect(node.getAttribute("aria-label")).toBe("Save");
    expect(node.textContent).toBe("Save");
  });

  it("renders string children as text, preventing HTML injection", () => {
    const node = el("div", {}, ["<img src=x onerror=alert(1)>"]);
    expect(node.querySelector("img")).toBeNull();
    expect(node.textContent).toBe("<img src=x onerror=alert(1)>");
  });

  it("appends element children", () => {
    const parent = el("div", {}, [el("span", {}, ["child"])]);
    expect(parent.querySelector("span")?.textContent).toBe("child");
  });
});
