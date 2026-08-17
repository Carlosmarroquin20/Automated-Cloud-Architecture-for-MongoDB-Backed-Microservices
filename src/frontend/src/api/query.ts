// Query-string construction for the item listing. Kept free of browser globals
// so it can be unit-tested in isolation.

export interface ListParams {
  limit?: number;
  skip?: number;
  tag?: string;
  q?: string;
}

export function buildQuery(params: ListParams): string {
  const search = new URLSearchParams();
  if (params.limit !== undefined) {
    search.set("limit", String(params.limit));
  }
  if (params.skip !== undefined) {
    search.set("skip", String(params.skip));
  }
  if (params.tag) {
    search.set("tag", params.tag);
  }
  if (params.q) {
    search.set("q", params.q);
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}
