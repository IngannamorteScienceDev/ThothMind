import type { ArtifactFreshness, CuratedManifest } from "../shared/types/api";
import { getDataBasePath } from "./datasetMode";

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

async function safeFetchLastModified(path: string): Promise<string | null> {
  try {
    const response = await fetch(path, {
      method: "HEAD",
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    return response.headers.get("last-modified");
  } catch {
    return null;
  }
}

function buildPath(relative: string): string {
  const base = getDataBasePath();
  return `${base}${relative}`;
}

export async function loadSuiteRuns() {
  return safeFetchJson(buildPath("/index/all_results_index.json"), []);
}

export async function loadSuiteTickerResults() {
  return safeFetchJson(buildPath("/index/suite_ticker_results_index.json"), []);
}

export async function loadTopByReturn() {
  return safeFetchJson(buildPath("/showcase/top10_by_return.json"), []);
}

export async function loadTopDefenseReady() {
  return safeFetchJson(buildPath("/showcase/top10_defense_ready.json"), []);
}

export async function loadCuratedManifest(): Promise<CuratedManifest | null> {
  return safeFetchJson<CuratedManifest | null>(
    buildPath("/meta/curated_manifest.json"),
    null
  );
}

export async function loadArtifactFreshness(): Promise<ArtifactFreshness> {
  const [
    suiteIndexLastModified,
    tickerIndexLastModified,
    topReturnLastModified,
    topDefenseLastModified,
  ] = await Promise.all([
    safeFetchLastModified(buildPath("/index/all_results_index.json")),
    safeFetchLastModified(buildPath("/index/suite_ticker_results_index.json")),
    safeFetchLastModified(buildPath("/showcase/top10_by_return.json")),
    safeFetchLastModified(buildPath("/showcase/top10_defense_ready.json")),
  ]);

  return {
    suiteIndexLastModified,
    tickerIndexLastModified,
    topReturnLastModified,
    topDefenseLastModified,
  };
}