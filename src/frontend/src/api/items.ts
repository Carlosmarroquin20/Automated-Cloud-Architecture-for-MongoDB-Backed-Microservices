import type { Item, ItemCreate, ItemUpdate } from "../types/item";
import { httpClient } from "./client";

export function listItems(): Promise<Item[]> {
  return httpClient.request<Item[]>("/items");
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
