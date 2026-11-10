import test from "node:test";
import assert from "node:assert/strict";
import { setPlatformSession } from "../src/web_admin/modules/auth/services/session-store";
import { searchCards } from "../src/web_player/modules/catalogo/services/cards.api";

test("searchCards construye la URL con filtros combinados de tipo, costo y solo_propias", async () => {
  setPlatformSession({
    access_token: "mock-token-xyz-123",
    user_id: "user-player-1",
    expires_in: 3600,
    role: "PLAYER",
  });

  let requestedUrl = "";

  const mockFetch = (async (input: RequestInfo | URL) => {
    requestedUrl = String(input);
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "card-1",
            name: "Pikachu Test",
            code: "PKA-004",
            card_type: "ELE",
            rarity: "RARA",
            cost: 2,
            power: 120,
            hp: 140,
            ability_name: "Chispa",
            ability_code: "HAB-004",
            owned_copies: 2,
            is_owned: true,
          },
        ],
        total: 1,
        pagina: 1,
        limite: 15,
        total_paginas: 1,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }) as unknown as typeof fetch;

  const result = await searchCards(
    {
      q: "Pikachu",
      tipo: "ELE",
      costo: 2,
      solo_propias: true,
      pagina: 1,
      limite: 15,
    },
    { fetchImpl: mockFetch }
  );

  assert.ok(requestedUrl.includes("q=Pikachu"));
  assert.ok(requestedUrl.includes("tipo=ELE"));
  assert.ok(requestedUrl.includes("costo=2"));
  assert.ok(requestedUrl.includes("solo_propias=true"));

  assert.equal(result.data.items.length, 1);
  const card = result.data.items[0];
  assert.equal(card.name, "Pikachu Test");
  assert.equal(card.cost, 2);
  assert.equal(card.power, 120);
  assert.equal(card.hp, 140);
  assert.equal(card.type, "ELE");
  assert.equal(card.ability_name, "Chispa");
  assert.equal(card.owned_copies, 2);
  assert.equal(card.is_owned, true);
});
