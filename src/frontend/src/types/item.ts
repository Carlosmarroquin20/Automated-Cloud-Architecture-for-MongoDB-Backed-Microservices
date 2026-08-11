// Client-side mirror of the backend item contract. Field names and nullability
// match the API response schema exactly to keep the boundary type-safe.

export interface Item {
  id: string;
  name: string;
  description: string | null;
  quantity: number;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface ItemCreate {
  name: string;
  description?: string | null;
  quantity?: number;
  tags?: string[];
}

export interface ItemUpdate {
  name?: string;
  description?: string | null;
  quantity?: number;
  tags?: string[];
}
