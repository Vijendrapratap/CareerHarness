export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  const text = await response.text();
  let data: any = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (response.status === 401 && !["/login", "/register"].includes(window.location.pathname)) {
    window.location.assign("/login");
  }
  if (!response.ok) {
    const errorMsg =
      (data && typeof data.detail === "string" && data.detail) ||
      (typeof data === "string" ? data : response.statusText || `Request failed with status ${response.status}`);
    throw new Error(errorMsg);
  }
  return data as T;
}

// To-dos and email are optional side steps; once counsel is done the candidate lives on Jobs.
const STAGE_PAGE: Record<string, string> = {
  counsel: "/counsel",
  todos: "/jobs",
  mailbox: "/jobs",
  hunt: "/jobs",
  active: "/applications",
};

export function pageForStage(stage: string): string {
  return STAGE_PAGE[stage] ?? "/counsel";
}

/** Sends the candidate to the page for their current journey stage. */
export async function goToCurrentStage(): Promise<void> {
  const { stage } = await api<{ stage: string }>("/api/journey");
  window.location.assign(pageForStage(stage));
}
