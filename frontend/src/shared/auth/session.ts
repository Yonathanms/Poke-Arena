/** Identity supplies an in-memory token provider after authenticating the session. */
export type AccessTokenProvider = () => string | null | Promise<string | null>;
export const PLATFORM_SESSION_INVALIDATED_EVENT = "pokearena:platform-session-invalidated";

let accessToken: string | null = null;
let accessTokenExpiresAt: number | null = null;
let accessTokenProvider: AccessTokenProvider = () => accessToken;

export function configureAccessTokenProvider(provider: AccessTokenProvider): void {
  accessTokenProvider = provider;
}

/** Store a short-lived platform credential in memory; never persist it in browser storage. */
export function setPlatformAccessToken(token: string, expiresInSeconds = 900): void {
  if (!token || expiresInSeconds <= 0) {
    clearPlatformAccessToken();
    return;
  }
  accessToken = token;
  accessTokenExpiresAt = Date.now() + expiresInSeconds * 1000;
  accessTokenProvider = () => accessToken;
}

/** Clear the in-memory credential on logout or after an unrecoverable auth failure. */
export function clearPlatformAccessToken(): void {
  accessToken = null;
  accessTokenExpiresAt = null;
  accessTokenProvider = () => accessToken;
}

export function invalidatePlatformAccessToken(): void {
  clearPlatformAccessToken();
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(PLATFORM_SESSION_INVALIDATED_EVENT));
  }
}

export async function getPlatformAccessToken(): Promise<string | null> {
  if (accessTokenExpiresAt !== null && Date.now() >= accessTokenExpiresAt) {
    clearPlatformAccessToken();
  }
  return accessTokenProvider();
}
