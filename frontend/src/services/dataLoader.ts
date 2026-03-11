import type { CuratedManifest } from "../shared/types/api";

async function safeFetchJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) {
      return fallback;
    }
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export async function loadSuiteRuns() {
  return safeFetchJson("/data/index/all_results_index.json", []);
}

export async function loadSuiteTickerResults() {
  return safeFetchJson("/data/index/suite_ticker_results_index.json", []);
}

export async function loadTopByReturn() {
  return safeFetchJson("/data/showcase/top10_by_return.json", []);
}

export async function loadTopDefenseReady() {
  return safeFetchJson("/data/showcase/top10_defense_ready.json", []);
}

export async function loadCuratedManifest(): Promise<CuratedManifest | null> {
  return safeFetchJson<CuratedManifest | null>(
    "/data/meta/curated_manifest.json",
    null
  );
}