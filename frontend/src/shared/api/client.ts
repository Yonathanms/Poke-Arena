import { ApiErrorResponse } from "../types/api";
import {
  getPlatformAccessToken,
  invalidatePlatformAccessToken,
} from "../auth/session";

const BASE_URL = "/api/v1";

export class ApiClientError extends Error {
  public readonly code: string;
  public readonly details: unknown[];
  public readonly correlationId?: string;
  public readonly status: number;

  constructor(status: number, errorData: ApiErrorResponse["error"]) {
    super(errorData.message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = errorData.code;
    this.details = errorData.details;
    this.correlationId = errorData.correlation_id;
  }
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  idempotencyKey?: string
): Promise<T> {
  const url = `${BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const headers = new Headers(options.headers || {});
  const accessToken = await getPlatformAccessToken();
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  if (idempotencyKey) {
    headers.set("Idempotency-Key", idempotencyKey);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) invalidatePlatformAccessToken();
    let errorJson: ApiErrorResponse | null = null;
    try {
      errorJson = await response.json();
    } catch {
      // Si el backend no devolvió JSON válido
    }

    if (errorJson?.error) {
      throw new ApiClientError(response.status, errorJson.error);
    }

    throw new Error(`Error HTTP ${response.status}: ${response.statusText}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
