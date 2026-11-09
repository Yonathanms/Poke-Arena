/**
 * Tipos de datos del perfil de jugador y estado recuperado de la base de datos SQL.
 */

import type { PlatformRole } from "../../../../web_admin/modules/auth/types/auth.types";

export interface PlayerProfileDTO {
  readonly user_id: string;
  readonly email: string | null;
  readonly role: PlatformRole;
  readonly elo: number;
  readonly cubes: number;
  readonly has_received_initial_collection: boolean;
  readonly created_at: string | null;
}

export interface PlayerProfileState {
  readonly profile: PlayerProfileDTO | null;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly reload: () => Promise<void>;
}
