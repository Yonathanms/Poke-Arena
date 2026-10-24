export type PlatformRole = "PLAYER" | "PLATFORM_ADMIN";

export interface PlatformSessionDTO {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  user_id: string;
  role: PlatformRole;
}

interface IdentityErrorBody {
  error?: {
    message?: string;
    code?: string;
  };
}

export class IdentityApiError extends Error {
  public readonly status: number;
  public readonly code: string;

  constructor(
    message: string,
    status: number,
    code: string
  ) {
    super(message);
    this.name = "IdentityApiError";
    this.status = status;
    this.code = code;
  }
}

export async function createGooglePlatformSession(
  googleIdToken: string,
  request: typeof fetch = fetch
): Promise<PlatformSessionDTO> {
  const response = await request("/api/v1/identity/google/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ google_id_token: googleIdToken }),
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as IdentityErrorBody | null;
    throw new IdentityApiError(
      errorBody?.error?.message ?? `No se pudo iniciar sesión (HTTP ${response.status}).`,
      response.status,
      errorBody?.error?.code ?? "IDENTITY_LOGIN_FAILED"
    );
  }

  const session = (await response.json()) as PlatformSessionDTO;
  if (
    !session.access_token ||
    session.token_type !== "Bearer" ||
    !Number.isInteger(session.expires_in) ||
    session.expires_in <= 0 ||
    !session.user_id ||
    !["PLAYER", "PLATFORM_ADMIN"].includes(session.role)
  ) {
    throw new IdentityApiError(
      "Identity devolvió una sesión con formato inválido.",
      502,
      "INVALID_IDENTITY_RESPONSE"
    );
  }
  return session;
}

export async function createLocalTestPlatformSession(
  userId = "local-admin",
  request: typeof fetch = fetch
): Promise<PlatformSessionDTO> {
  const response = await request("/api/v1/identity/test-session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as IdentityErrorBody | null;
    throw new IdentityApiError(
      errorBody?.error?.message ?? `No se pudo iniciar sesión local (HTTP ${response.status}).`,
      response.status,
      errorBody?.error?.code ?? "IDENTITY_LOCAL_LOGIN_FAILED"
    );
  }
  const session = (await response.json()) as PlatformSessionDTO;
  if (
    !session.access_token ||
    session.token_type !== "Bearer" ||
    !Number.isInteger(session.expires_in) ||
    session.expires_in <= 0 ||
    !session.user_id ||
    session.role !== "PLATFORM_ADMIN"
  ) {
    throw new IdentityApiError(
      "Identity devolvió una sesión local con formato inválido.",
      502,
      "INVALID_IDENTITY_RESPONSE"
    );
  }
  return session;
}
