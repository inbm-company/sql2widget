/**
 * State rules:
 * 1. Server fetch → useSWR (via useSWR export / fetch helpers)
 * 2. Global UI slots → useStore (SWR cache wrapper, no Provider)
 * 3. Immediate local UI → useState in components
 */
import useSWR, { mutate as swrMutate } from "swr";

export { useSWR };

const CLIENT_KEYS = {
  ui: "store:ui",
};

const clientInitial = {
  [CLIENT_KEYS.ui]: {
    stageOpen: true,
    saveStatus: "idle",
  },
};

function resolveFetcher(key, fetcher) {
  if (typeof fetcher === "function") return fetcher;
  if (typeof key === "string" && key.startsWith("store:")) {
    return async () => clientInitial[key] ?? null;
  }
  return fetcher;
}

export function useStore(key, fetcher, options = {}) {
  const isClient = typeof key === "string" && key.startsWith("store:");
  const { data, error, isLoading, isValidating } = useSWR(
    key,
    resolveFetcher(key, fetcher),
    {
      revalidateOnFocus: !isClient,
      shouldRetryOnError: !isClient,
      ...options,
    }
  );

  return {
    data,
    error,
    isLoading,
    isValidating,
    set: (updater) =>
      swrMutate(
        key,
        (current) => {
          const base = current ?? clientInitial[key] ?? null;
          return typeof updater === "function" ? updater(base) : updater;
        },
        { revalidate: false }
      ),
    refresh: () => swrMutate(key),
  };
}

export function setStore(key, updater) {
  return swrMutate(
    key,
    (current) => {
      const base = current ?? clientInitial[key] ?? null;
      return typeof updater === "function" ? updater(base) : updater;
    },
    { revalidate: false }
  );
}

export const storeKeys = {
  ...CLIENT_KEYS,
  me: "api:/auth/me",
  projects: "api:/projects",
  conversations: (projectId) => (projectId ? `api:/conversations/${projectId}` : null),
  conversation: (id) => (id ? `api:/conversations/${id}` : null),
  stage: (projectId) => (projectId ? `api:/stage/${projectId}` : null),
  connections: "api:/database-connections",
  graphSources: (projectId) => (projectId ? `api:/projects/${projectId}/graph-sources` : null),
  projectGraph: (projectId) => (projectId ? `api:/projects/${projectId}/graph` : null),
  projectEntities: (projectId) => (projectId ? `api:/projects/${projectId}/graph/entities` : null),
  graphDocument: (projectId, id) => (projectId && id ? `api:/projects/${projectId}/graph/documents/${id}` : null),
  questions: (connectionId) => (connectionId ? `api:/database-connections/${connectionId}/questions` : null),
};
