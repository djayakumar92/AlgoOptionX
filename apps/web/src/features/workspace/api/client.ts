export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    `/api/${path}`,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const payload = await response.json();
  if (!response.ok)
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : "The request could not be completed. Check your inputs.",
    );
  return payload;
}
export function command(action: string, fields: object = {}) {
  return api("commands", { key: crypto.randomUUID(), action, ...fields });
}
