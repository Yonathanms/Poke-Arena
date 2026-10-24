import assert from "node:assert/strict";
import { test } from "node:test";

import {
  clearPlatformAccessToken,
  getPlatformAccessToken,
  invalidatePlatformAccessToken,
  setPlatformAccessToken,
} from "../src/shared/auth/session.ts";
import {
  createGooglePlatformSession,
  createLocalTestPlatformSession,
  IdentityApiError,
} from "../src/modules/identity/api/identity.ts";

test("stores the platform bearer in memory and clears it on logout", async () => {
  setPlatformAccessToken("platform-access", 900);
  assert.equal(await getPlatformAccessToken(), "platform-access");

  clearPlatformAccessToken();
  assert.equal(await getPlatformAccessToken(), null);
});

test("does not return an expired platform bearer", async () => {
  setPlatformAccessToken("expired-token", -1);
  assert.equal(await getPlatformAccessToken(), null);
});

test("invalidates the bearer when the API rejects the platform session", async () => {
  setPlatformAccessToken("revoked-token", 900);
  invalidatePlatformAccessToken();
  assert.equal(await getPlatformAccessToken(), null);
});

test("exchanges a Google ID token for the platform session contract", async () => {
  let requestUrl = "";
  let requestOptions: RequestInit | undefined;
  const request: typeof fetch = async (input, init) => {
    requestUrl = String(input);
    requestOptions = init;
    return new Response(
      JSON.stringify({
        access_token: "opaque-platform-token",
        token_type: "Bearer",
        expires_in: 900,
        user_id: "user-1",
        role: "PLATFORM_ADMIN",
      }),
      { status: 201, headers: { "Content-Type": "application/json" } }
    );
  };

  const session = await createGooglePlatformSession("google-id-token", request);

  assert.equal(requestUrl, "/api/v1/identity/google/session");
  assert.equal(requestOptions?.method, "POST");
  assert.deepEqual(JSON.parse(String(requestOptions?.body)), {
    google_id_token: "google-id-token",
  });
  assert.equal(session.access_token, "opaque-platform-token");
  assert.equal(session.role, "PLATFORM_ADMIN");
});

test("surfaces backend authentication errors without accepting a session", async () => {
  const request: typeof fetch = async () =>
    new Response(
      JSON.stringify({ error: { code: "UNAUTHORIZED", message: "Credencial inválida." } }),
      { status: 401, headers: { "Content-Type": "application/json" } }
    );

  await assert.rejects(
    createGooglePlatformSession("invalid-google-token", request),
    (error: unknown) =>
      error instanceof IdentityApiError &&
      error.status === 401 &&
      error.code === "UNAUTHORIZED"
  );
});

test("requests the fixed local administrator session without a client supplied role", async () => {
  let requestUrl = "";
  let requestOptions: RequestInit | undefined;
  const request: typeof fetch = async (input, init) => {
    requestUrl = String(input);
    requestOptions = init;
    return new Response(
      JSON.stringify({
        access_token: "local-platform-token",
        token_type: "Bearer",
        expires_in: 900,
        user_id: "local-user",
        role: "PLATFORM_ADMIN",
      }),
      { status: 201, headers: { "Content-Type": "application/json" } }
    );
  };

  const session = await createLocalTestPlatformSession("local-admin", request);

  assert.equal(requestUrl, "/api/v1/identity/test-session");
  assert.deepEqual(JSON.parse(String(requestOptions?.body)), { user_id: "local-admin" });
  assert.equal(session.role, "PLATFORM_ADMIN");
});

test("rejects a local session response that is not an administrator", async () => {
  const request: typeof fetch = async () =>
    new Response(
      JSON.stringify({
        access_token: "local-player-token",
        token_type: "Bearer",
        expires_in: 900,
        user_id: "local-user",
        role: "PLAYER",
      }),
      { status: 201, headers: { "Content-Type": "application/json" } }
    );
  await assert.rejects(
    createLocalTestPlatformSession("local-admin", request),
    (error: unknown) => error instanceof IdentityApiError && error.code === "INVALID_IDENTITY_RESPONSE"
  );
});
