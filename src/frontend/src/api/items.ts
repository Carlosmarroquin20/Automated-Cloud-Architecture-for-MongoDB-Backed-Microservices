import type { Item, ItemCreate, ItemUpdate } from "../types/item";
import { httpClient } from "./client";
import { buildQuery } from "./query";
import type { ListParams } from "./query";

export interface ItemPage {
  items: Item[];
  total: number;
}

export async function listItems(params: ListParams = {}): Promise<ItemPage> {
  const response = await httpClient.send(`/items${buildQuery(params)}`);
  const items = (await response.json()) as Item[];
  // Total match count is advertised by the backend as a response header so the
  // array contract is preserved; it falls back to the page length when absent.
  const header = response.headers.get("X-Total-Count");
  const total = header === null ? items.length : Number(header);
  return { items, total: Number.isFinite(total) ? total : items.length };
}

export function createItem(data: ItemCreate): Promise<Item> {
  return httpClient.request<Item>("/items", { method: "POST", body: data });
}

export function updateItem(id: string, data: ItemUpdate): Promise<Item> {
  return httpClient.request<Item>(`/items/${id}`, { method: "PATCH", body: data });
}

export function deleteItem(id: string): Promise<void> {
  return httpClient.request<void>(`/items/${id}`, { method: "DELETE" });
}
