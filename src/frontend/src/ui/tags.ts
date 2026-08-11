// Tag parsing helpers shared by the create form and the item renderer. Pure and
// side-effect free to keep them independently unit-testable.

export function parseTags(raw: string): string[] {
  return raw
    .split(",")
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0);
}

export function formatTags(tags: string[]): string {
  return tags.join(", ");
}
