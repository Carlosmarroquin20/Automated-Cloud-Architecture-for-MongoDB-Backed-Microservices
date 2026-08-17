import { config } from "../config";
import { ApiError, parseApiError } from "./errors";

interface RequestOptions {
  method?: string;
  body?: unknown;
}

// Bounds every request so a stalled connection cannot hang the UI.
const REQUEST_TIMEOUT_MS = 10_000;

async function send(path: string, options: RequestOptions = {}): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => {
    controller.abort();
  }, REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${config.apiBaseUrl}${path}`, {
      method: options.method ?? "GET",
      headers: { "Content-Type": "application/json" },
      body: options.body === undefined ? null : JSON.stringify(options.body),
      signal: controller.signal,
    });
    if (!response.ok) {
      const payload: unknown = await response.json().catch(() => null);
      throw parseApiError(response.status, payload);
    }
    return response;
  } catch (error) {
    throw normalizeError(error);
  } finally {
    window.clearTimeout(timer);
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(path, options);
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function normalizeError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }
  if (error instanceof DOMException && error.name === "AbortError") {
    return new ApiError(0, "timeout", "The request timed out");
  }
  return new ApiError(0, "network_error", "The service is unreachable");
}

// `send` returns the raw response so callers can read headers (for example the
// total count); `request` layers JSON parsing on top for the common case.
export const httpClient = { send, request };
