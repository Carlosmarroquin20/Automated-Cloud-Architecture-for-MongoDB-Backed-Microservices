import { describe, expect, it } from "vitest";

import { formatTags, parseTags } from "../src/ui/tags";

describe("parseTags", () => {
  it("splits, trims, and drops empty entries", () => {
    expect(parseTags(" a, b ,,c ")).toEqual(["a", "b", "c"]);
  });

  it("returns an empty array for blank input", () => {
    expect(parseTags("   ")).toEqual([]);
  });
});

describe("formatTags", () => {
  it("joins tags with a comma and space", () => {
    expect(formatTags(["a", "b"])).toBe("a, b");
  });
});
