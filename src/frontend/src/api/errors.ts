// Transport-agnostic error model. Isolated from configuration and browser
// globals so that error mapping is unit-testable in a Node environment.

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details: unknown = undefined) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function parseApiError(status: number, payload: unknown): ApiError {
  if (isApiErrorBody(payload)) {
    return new ApiError(status, payload.error.code, payload.error.message, payload.error.details);
  }
  return new ApiError(status, "unknown_error", `Request failed with status ${String(status)}`);
}

function isApiErrorBody(payload: unknown): payload is ApiErrorBody {
  if (typeof payload !== "object" || payload === null || !("error" in payload)) {
    return false;
  }
  const candidate = (payload as { error: unknown }).error;
  return typeof candidate === "object" && candidate !== null;
}
