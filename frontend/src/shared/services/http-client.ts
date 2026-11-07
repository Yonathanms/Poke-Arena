/**
 * Cliente HTTP centralizado para Poké-Arena (`fetch` nativo + RFC 7807 Problem Details).
 *
 * Responsabilidades:
 * 1. Construir URLs hacia `/api/v1` e inyectar `Authorization: Bearer <token>` cuando la
 *    ruta requiere autenticación.
 * 2. Aceptar una clave `Idempotency-Key` explícitamente provista por el llamador, sin
 *    generarla ni rotarla internamente.
 * 3. Preservar el envío de `FormData` sin fijar `Content-Type` manual para que el navegador
 *    añada el boundary multipart correspondiente.
 * 4. Traducir errores HTTP al contrato RFC 7807 (`application/problem+json`), preservando
 *    `status`, `code`, `detail`, `correlation_id` y `Retry-After`, e invalidando la sesión
 *    en memoria ante respuestas `401 Unauthorized`.
 */

/** Proveedor de lectura del token Bearer actual. */
export type HttpAccessTokenProvider = () => string | null;

/**
 * Callback ejecutado cuando una ruta protegida responde `401 Unauthorized`.
 * Recibe el token exacto usado en esa solicitud para que el almacén de sesión
 * solo invalide si ese token sigue siendo la sesión activa (evitando condiciones
 * de carrera con respuestas 401 tardías tras una reautenticación).
 */
export type HttpUnauthorizedHandler = (rejectedToken?: string | null) => void;

const DEFAULT_API_PREFIX = "/api/v1";
const IDEMPOTENCY_KEY_PATTERN = /^[!-+\x2D-~]{1,128}$/;

let defaultTokenProvider: HttpAccessTokenProvider = () => null;
let defaultUnauthorizedHandler: HttpUnauthorizedHandler = () => {};

/**
 * Configura los ganchos por defecto de lectura e invalidación de sesión para
 * el cliente HTTP sin acoplar este módulo a una ruta de archivo específica.
 */
export function configureHttpClientSessionHooks(hooks: {
  readonly getAccessToken: HttpAccessTokenProvider;
  readonly onUnauthorized: HttpUnauthorizedHandler;
}): void {
  defaultTokenProvider = hooks.getAccessToken;
  defaultUnauthorizedHandler = hooks.onUnauthorized;
}

/**
 * Estructura estándar devuelta por el backend en errores (`application/problem+json`).
 * Ver `backend/src/shared/errores-rfc7807/respuestas.py`.
 */
export interface Rfc7807ProblemDetails {
  readonly type: string;
  readonly title: string;
  readonly status: number;
  readonly detail: string;
  readonly code: string;
  readonly correlation_id: string;
}

/**
 * Error tipado de la capa HTTP que conserva la semántica de negocio y correlación
 * del backend o clasifica fallos de red/transporte.
 */
export class ApiHttpError extends Error {
  public readonly status: number;
  public readonly code: string;
  public readonly detail: string;
  public readonly title: string;
  public readonly type: string;
  public readonly correlationId: string | null;
  public readonly retryAfterSeconds: number | null;
  public readonly isNetworkError: boolean;

  constructor(params: {
    readonly status: number;
    readonly code: string;
    readonly detail: string;
    readonly title?: string;
    readonly type?: string;
    readonly correlationId?: string | null;
    readonly retryAfterSeconds?: number | null;
    readonly isNetworkError?: boolean;
  }) {
    super(params.detail);
    this.name = "ApiHttpError";
    this.status = params.status;
    this.code = params.code;
    this.detail = params.detail;
    this.title = params.title ?? "HTTP Error";
    this.type = params.type ?? "about:blank";
    this.correlationId = params.correlationId ?? null;
    this.retryAfterSeconds = params.retryAfterSeconds ?? null;
    this.isNetworkError = params.isNetworkError ?? false;
  }

  /**
   * Indica si el resultado de una mutación es incierto o está en curso, por lo que
   * el llamador DEBE conservar la misma `Idempotency-Key` para un posible reintento.
   */
  public get shouldPreserveIdempotencyKey(): boolean {
    if (this.isNetworkError) {
      return true;
    }
    if (this.status === 500 || this.status === 503) {
      return true;
    }
    return this.status === 409 && this.code === "en_curso";
  }
}

/** Opciones de solicitud para `requestApi`. */
export interface ApiRequestOptions {
  readonly method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  readonly body?: BodyInit | Record<string, unknown> | null;
  readonly headers?: Record<string, string>;
  /** Si es `true` (por defecto), adjunta el Bearer activo e invalida la sesión en `401`. */
  readonly requiresAuth?: boolean;
  /** Clave de idempotencia provista por el llamador; el cliente valida formato pero nunca la genera. */
  readonly idempotencyKey?: string;
  readonly signal?: AbortSignal;
  /** Permite inyectar una implementación de `fetch` en pruebas unitarias sin tocar la red. */
  readonly fetchImpl?: typeof fetch;
  /** Prefijo base opcional (por defecto `/api/v1`). */
  readonly baseUrl?: string;
  /** Proveedor opcional de token Bearer para esta solicitud (por defecto usa el configurado). */
  readonly tokenProvider?: HttpAccessTokenProvider;
  /** Callback opcional de invalidación ante `401 Unauthorized`. */
  readonly onUnauthorized?: HttpUnauthorizedHandler;
}

/** Metadatos y cuerpo parseado de una respuesta HTTP exitosa. */
export interface ApiResponse<T> {
  readonly status: number;
  readonly data: T;
  readonly correlationId: string | null;
}

function buildUrl(endpoint: string, baseUrl: string): string {
  const normalizedBase = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  const normalizedPath = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  return `${normalizedBase}${normalizedPath}`;
}

function isFormDataBody(body: unknown): body is FormData {
  return typeof FormData !== "undefined" && body instanceof FormData;
}

function isPlainJsonRecord(body: unknown): body is Record<string, unknown> {
  if (typeof body !== "object" || body === null) {
    return false;
  }
  if (isFormDataBody(body)) {
    return false;
  }
  if (typeof Blob !== "undefined" && body instanceof Blob) {
    return false;
  }
  if (typeof URLSearchParams !== "undefined" && body instanceof URLSearchParams) {
    return false;
  }
  if (typeof ArrayBuffer !== "undefined" && (body instanceof ArrayBuffer || ArrayBuffer.isView(body))) {
    return false;
  }
  return true;
}

function parseRetryAfterHeader(headerValue: string | null): number | null {
  if (!headerValue) {
    return null;
  }
  const parsed = Number.parseInt(headerValue.trim(), 10);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return null;
  }
  return parsed;
}

function isRfc7807Payload(payload: unknown): payload is Rfc7807ProblemDetails {
  if (typeof payload !== "object" || payload === null) {
    return false;
  }
  const candidate = payload as Record<string, unknown>;
  return (
    typeof candidate.code === "string" &&
    typeof candidate.detail === "string" &&
    typeof candidate.status === "number"
  );
}

function prepareHeadersAndBody(options: ApiRequestOptions): {
  readonly headers: Headers;
  readonly body: BodyInit | undefined;
  readonly usedAccessToken: string | null;
} {
  const headers = new Headers();
  let usedAccessToken: string | null = null;

  if (options.headers) {
    for (const [key, value] of Object.entries(options.headers)) {
      headers.set(key, value);
    }
  }

  const requiresAuth = options.requiresAuth ?? true;
  if (requiresAuth) {
    const resolveToken = options.tokenProvider ?? defaultTokenProvider;
    const token = resolveToken();
    if (!token) {
      throw new ApiHttpError({
        status: 401,
        code: "sesion_requerida",
        detail: "Se requiere una sesión activa de administrador para realizar esta operación.",
        title: "Unauthorized",
      });
    }
    usedAccessToken = token;
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (options.idempotencyKey !== undefined) {
    if (!IDEMPOTENCY_KEY_PATTERN.test(options.idempotencyKey)) {
      throw new ApiHttpError({
        status: 422,
        code: "idempotencia_invalida",
        detail: "La clave de idempotencia debe tener entre 1 y 128 caracteres ASCII visibles sin comas.",
        title: "Unprocessable Entity",
      });
    }
    headers.set("Idempotency-Key", options.idempotencyKey);
  }

  const rawBody = options.body;
  if (rawBody === undefined || rawBody === null) {
    return { headers, body: undefined, usedAccessToken };
  }

  if (isFormDataBody(rawBody)) {
    // Nunca fijar Content-Type manualmente en FormData: el navegador debe generar el boundary.
    headers.delete("Content-Type");
    return { headers, body: rawBody, usedAccessToken };
  }

  if (isPlainJsonRecord(rawBody)) {
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    return { headers, body: JSON.stringify(rawBody), usedAccessToken };
  }

  return { headers, body: rawBody as BodyInit, usedAccessToken };
}

async function parseErrorResponse(response: Response): Promise<ApiHttpError> {
  const headerCorrelation = response.headers.get("X-Correlation-ID");
  const retryAfterSeconds = parseRetryAfterHeader(response.headers.get("Retry-After"));

  let parsedBody: unknown = null;
  try {
    parsedBody = await response.json();
  } catch {
    parsedBody = null;
  }

  if (isRfc7807Payload(parsedBody)) {
    return new ApiHttpError({
      status: response.status,
      code: parsedBody.code,
      detail: parsedBody.detail,
      title: parsedBody.title,
      type: parsedBody.type,
      correlationId: parsedBody.correlation_id || headerCorrelation,
      retryAfterSeconds,
    });
  }

  return new ApiHttpError({
    status: response.status,
    code: "http_error",
    detail: `La solicitud no se completó (HTTP ${response.status}).`,
    title: response.statusText || "HTTP Error",
    correlationId: headerCorrelation,
    retryAfterSeconds,
  });
}

/**
 * Ejecuta una petición HTTP hacia la API de Poké-Arena y devuelve cuerpo + metadatos.
 */
export async function requestApiWithMeta<T>(
  endpoint: string,
  options: ApiRequestOptions = {}
): Promise<ApiResponse<T>> {
  const fetchFn = options.fetchImpl ?? globalThis.fetch;
  const baseUrl = options.baseUrl ?? DEFAULT_API_PREFIX;
  const url = buildUrl(endpoint, baseUrl);
  const requiresAuth = options.requiresAuth ?? true;
  const { headers, body, usedAccessToken } = prepareHeadersAndBody(options);

  let response: Response;
  try {
    response = await fetchFn(url, {
      method: options.method ?? "GET",
      headers,
      body,
      signal: options.signal,
    });
  } catch (cause) {
    const isAborted = cause instanceof Error && cause.name === "AbortError";
    throw new ApiHttpError({
      status: 0,
      code: isAborted ? "solicitud_cancelada" : "error_red",
      detail: isAborted
        ? "La solicitud fue cancelada antes de recibir respuesta."
        : "No se pudo establecer comunicación con el servidor. Verifica tu conexión.",
      title: "Network Error",
      isNetworkError: true,
    });
  }

  if (!response.ok) {
    if (response.status === 401 && requiresAuth) {
      const handleUnauthorized = options.onUnauthorized ?? defaultUnauthorizedHandler;
      handleUnauthorized(usedAccessToken);
    }
    throw await parseErrorResponse(response);
  }

  const correlationId = response.headers.get("X-Correlation-ID");
  if (response.status === 204) {
    return {
      status: 204,
      data: undefined as T,
      correlationId,
    };
  }

  const data = (await response.json()) as T;
  return {
    status: response.status,
    data,
    correlationId,
  };
}

/**
 * Ejecuta una petición HTTP hacia la API de Poké-Arena y devuelve directamente el payload tipado.
 */
export async function requestApi<T>(
  endpoint: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const result = await requestApiWithMeta<T>(endpoint, options);
  return result.data;
}
