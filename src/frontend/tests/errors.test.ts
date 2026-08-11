import { describe, expect, it } from "vitest";

import { ApiError, parseApiError } from "../src/api/errors";

describe("parseApiError", () => {
  it("maps the backend error envelope", () => {
    const error = parseApiError(404, { error: { code: "not_found", message: "missing" } });
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(404);
    expect(error.code).toBe("not_found");
    expect(error.message).toBe("missing");
  });

  it("falls back for an unrecognized payload", () => {
    const error = parseApiError(500, null);
    expect(error.code).toBe("unknown_error");
    expect(error.status).toBe(500);
  });
});
