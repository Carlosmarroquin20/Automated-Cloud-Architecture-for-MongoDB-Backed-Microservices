import { describe, expect, it } from "vitest";

import { buildQuery } from "../src/api/query";

describe("buildQuery", () => {
  it("returns an empty string when no parameters are set", () => {
    expect(buildQuery({})).toBe("");
  });

  it("serializes pagination and filter parameters", () => {
    expect(buildQuery({ limit: 8, skip: 16, tag: "net", q: "spool" })).toBe(
      "?limit=8&skip=16&tag=net&q=spool",
    );
  });

  it("omits blank tag and query values", () => {
    expect(buildQuery({ limit: 8, tag: "", q: "" })).toBe("?limit=8");
  });
});
