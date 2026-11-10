import { useEffect, useState, useSyncExternalStore } from "react";
import {
  getActiveSessionSnapshot,
  subscribeToSessionChanges,
} from "../../../../web_admin/modules/auth/services/session-store";
import { fetchCardImage, fetchCardThumbnail } from "../services/cards.api";

type CachedImage = {
  controller: AbortController;
  consumers: number;
  url: string | null;
  result: Promise<string | null>;
};

const thumbnails = new WeakMap<object, Map<string, CachedImage>>();
const largeImages = new WeakMap<object, Map<string, CachedImage>>();

function createRetainer(
  map: WeakMap<object, Map<string, CachedImage>>,
  fetcher: (id: string, signal: AbortSignal) => Promise<Blob>
) {
  return function retain(session: object, id: string) {
    let images = map.get(session);
    if (!images) {
      images = new Map();
      map.set(session, images);
    }
    const activeImages = images;
    let item = activeImages.get(id);
    if (!item) {
      const controller = new AbortController();
      const entry: CachedImage = {
        controller,
        consumers: 0,
        url: null,
        result: fetcher(id, controller.signal)
          .then((blob) => {
            if (!controller.signal.aborted) entry.url = URL.createObjectURL(blob);
            return entry.url;
          })
          .catch(() => null),
      };
      activeImages.set(id, entry);
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
            if (entry.consumers !== 0 || activeImages.get(id) !== entry) return;
            activeImages.delete(id);
            entry.controller.abort();
            if (entry.url) URL.revokeObjectURL(entry.url);
          });
        }
      },
    };
  };
}

/** Comparte la solicitud y la URL mientras la tarjeta o la tabla las usan. */
export const retainThumbnail = createRetainer(thumbnails, fetchCardThumbnail);
export const retainCardImage = createRetainer(largeImages, fetchCardImage);

export function useCardThumbnail(id: string): string | null {
  const session = useSyncExternalStore(subscribeToSessionChanges, getActiveSessionSnapshot, () => null);
  const [image, setImage] = useState<{ session: object; id: string; url: string | null }>();

  useEffect(() => {
    if (!id || !session) return;
    let active = true;
    const thumbnail = retainThumbnail(session, id);
    void thumbnail.result.then((url) => {
      if (active) setImage({ session, id, url });
    });
    return () => {
      active = false;
      thumbnail.release();
    };
  }, [id, session]);

  return image?.session === session && image.id === id ? image.url : null;
}

export function useCardImage(id: string): string | null {
  const session = useSyncExternalStore(subscribeToSessionChanges, getActiveSessionSnapshot, () => null);
  const [image, setImage] = useState<{ session: object; id: string; url: string | null }>();

  useEffect(() => {
    if (!id || !session) return;
    let active = true;
    const largeImage = retainCardImage(session, id);
    void largeImage.result.then((url) => {
      if (active) setImage({ session, id, url });
    });
    return () => {
      active = false;
      largeImage.release();
    };
  }, [id, session]);

  return image?.session === session && image.id === id ? image.url : null;
}
