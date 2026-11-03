import { apiFetch } from "./http";
export async function resourceApi<T>(path: string, body?: unknown): Promise<T> {
  const response = await apiFetch(`/api/resources/${path}`, body === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Check the document fields and try again.");
  return result;
}
