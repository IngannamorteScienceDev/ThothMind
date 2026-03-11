export type DatasetMode = "demo" | "research";

const STORAGE_KEY = "thothmind_dataset_mode";

export function resolveDatasetMode(): DatasetMode {
  if (typeof window === "undefined") {
    return "research";
  }

  const urlMode = new URLSearchParams(window.location.search).get("dataset");
  if (urlMode === "demo" || urlMode === "research") {
    localStorage.setItem(STORAGE_KEY, urlMode);
    return urlMode;
  }

  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "demo" || stored === "research") {
    return stored;
  }

  const host = window.location.hostname.toLowerCase();

  // GitHub Pages / static showcase -> demo by default
  if (host.includes("github.io")) {
    return "demo";
  }

  // local dev / thesis demo -> research by default
  return "research";
}

export function getDataBasePath(mode?: DatasetMode): string {
  const resolved = mode ?? resolveDatasetMode();
  return `/data/${resolved}`;
}

export function setDatasetMode(mode: DatasetMode): void {
  if (typeof window === "undefined") {
    return;
  }

  localStorage.setItem(STORAGE_KEY, mode);

  const url = new URL(window.location.href);
  url.searchParams.set("dataset", mode);
  window.location.href = url.toString();
}