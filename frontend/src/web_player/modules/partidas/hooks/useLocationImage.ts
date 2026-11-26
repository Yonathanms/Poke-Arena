/** Hooks autenticados para imágenes de estadios con caché por sesión y liberación segura. */

import { useEffect, useState, useSyncExternalStore } from "react";
import {
  getActiveSessionSnapshot,
  subscribeToSessionChanges,
} from "../../../../web_admin/modules/auth/services/session-store";
import { fetchLocationImage, fetchLocationThumbnail } from "../services/matches.api";

interface CachedLocationMedia {
  readonly controller: AbortController;
  consumers: number;
  url: string | null;
  readonly result: Promise<string | null>;
}

const fullImages = new WeakMap<object, Map<string, CachedLocationMedia>>();
const thumbnails = new WeakMap<object, Map<string, CachedLocationMedia>>();

function createLocationRetainer(
  store: WeakMap<object, Map<string, CachedLocationMedia>>,
  fetcher: (id: string, signal: AbortSignal) => Promise<Blob>,
) {
  return function retain(session: object, id: string) {
    let entries = store.get(session);
    if (!entries) {
      entries = new Map();
      store.set(session, entries);
    }
    const activeEntries = entries;
    let item = activeEntries.get(id);
    if (!item) {
      const controller = new AbortController();
      const entry: CachedLocationMedia = {
        controller,
        consumers: 0,
        url: null,
        result: fetcher(id, controller.signal)
          .then((blob) => {
            if (!controller.signal.aborted) {
              entry.url = URL.createObjectURL(blob);
            }
            return entry.url;
          })
          .catch(() => null),
      };
      activeEntries.set(id, entry);
      item = entry;
    }
    const entry = item;
    entry.consumers += 1;
    return {
      result: entry.result,
      release() {
        entry.consumers -= 1;
        if (entry.consumers === 0) {
          queueMicrotask(() => {
            if (entry.consumers !== 0 || activeEntries.get(id) !== entry) return;
            activeEntries.delete(id);
            entry.controller.abort();
            if (entry.url) URL.revokeObjectURL(entry.url);
          });
        }
      },
    };
  };
}

const retainLocationImage = createLocationRetainer(fullImages, fetchLocationImage);
const retainLocationThumbnail = createLocationRetainer(thumbnails, fetchLocationThumbnail);

function useRetainedLocationMedia(
  locationId: string,
  retain: ReturnType<typeof createLocationRetainer>,
): string | null {
  const session = useSyncExternalStore(
    subscribeToSessionChanges,
    getActiveSessionSnapshot,
    () => null,
  );
  const [media, setMedia] = useState<{ session: object; id: string; url: string | null }>();

  useEffect(() => {
    if (!locationId || !session) return;
    let active = true;
    const retained = retain(session, locationId);
    void retained.result.then((url) => {
      if (active) setMedia({ session, id: locationId, url });
    });
    return () => {
      active = false;
      retained.release();
    };
  }, [locationId, session, retain]);

  return media?.session === session && media.id === locationId ? media.url : null;
}

export function useLocationImage(locationId: string): string | null {
  return useRetainedLocationMedia(locationId, retainLocationImage);
}

export function useLocationThumbnail(locationId: string): string | null {
  return useRetainedLocationMedia(locationId, retainLocationThumbnail);
}
