import { config } from "../config";
import { ApiError, parseApiError } from "./errors";

interface RequestOptions {
  method?: string;
  body?: unknown;
}

// Bounds every request to prevent a stalled connection from hanging the UI.
const REQUEST_TIMEOUT_MS = 10_000;

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
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

    if (response.status === 204) {
      return undefined as T;
    }

    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      throw parseApiError(response.status, payload);
    }
    return payload as T;
  } catch (error) {
    throw normalizeError(error);
  } finally {
    window.clearTimeout(timer);
  }
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

export const httpClient = { request };
