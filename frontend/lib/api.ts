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
  if (!response.ok) {
    const errorMsg =
      (data && typeof data.detail === "string" && data.detail) ||
      (typeof data === "string" ? data : response.statusText || `Request failed with status ${response.status}`);
    throw new Error(errorMsg);
  }
  return data as T;
}
