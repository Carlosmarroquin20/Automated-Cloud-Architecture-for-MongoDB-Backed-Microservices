import type { Item, ItemCreate } from "../types/item";
import { ApiError } from "../api/errors";
import { createItem, deleteItem, listItems, updateItem } from "../api/items";
import { el } from "./dom";
import {
  ICON_BOX,
  ICON_CHEVRON_LEFT,
  ICON_CHEVRON_RIGHT,
  ICON_MINUS,
  ICON_PLUS,
  ICON_TRASH,
  icon,
} from "./icons";
import { parseTags } from "./tags";

type StatusKind = "error" | "info" | "none";

interface FormApi {
  element: HTMLFormElement;
  reset: () => void;
  setBusy: (busy: boolean) => void;
}

interface Field {
  field: HTMLElement;
  input: HTMLInputElement;
}

const PAGE_SIZE = 8;
const SEARCH_DEBOUNCE_MS = 250;

export function mountItemsView(root: HTMLElement): void {
  const status = el("p", { class: "status", role: "status", "aria-live": "polite" });
  const listContainer = el("div", { class: "item-list", "aria-busy": "false" });
  const statsContainer = el("div", { class: "stats" });
  const form = buildForm(onCreate);

  const searchInput = el("input", {
    class: "search",
    type: "search",
    placeholder: "Search by name",
    "aria-label": "Search items by name",
  });
  const spinner = el("span", { class: "spinner", "aria-hidden": "true" });

  const rangeLabel = el("span", { class: "pagination__range" });
  const prevButton = iconButton(ICON_CHEVRON_LEFT, "Previous page", "btn btn--icon");
  const nextButton = iconButton(ICON_CHEVRON_RIGHT, "Next page", "btn btn--icon");
  const pagination = el("div", { class: "pagination" }, [
    rangeLabel,
    el("div", { class: "pagination__controls" }, [prevButton, nextButton]),
  ]);

  const itemsPanel = el("section", { class: "panel" }, [
    el("div", { class: "panel__header" }, [
      panelTitle("Items", ICON_BOX),
      el("div", { class: "toolbar" }, [searchInput, spinner]),
    ]),
    status,
    listContainer,
    pagination,
  ]);

  root.append(
    statsContainer,
    el("section", { class: "panel" }, [panelTitle("Create item", ICON_PLUS), form.element]),
    itemsPanel,
  );

  let query = "";
  let skip = 0;
  let total = 0;
  let debounceTimer = 0;

  searchInput.addEventListener("input", () => {
    query = searchInput.value.trim();
    skip = 0;
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(() => {
      void reload();
    }, SEARCH_DEBOUNCE_MS);
  });

  prevButton.addEventListener("click", () => {
    if (skip === 0) {
      return;
    }
    skip = Math.max(0, skip - PAGE_SIZE);
    void reload();
  });
  nextButton.addEventListener("click", () => {
    if (skip + PAGE_SIZE >= total) {
      return;
    }
    skip += PAGE_SIZE;
    void reload();
  });

  function setStatus(message: string, kind: StatusKind): void {
    status.textContent = message;
    status.className = kind === "none" ? "status" : `status status--${kind}`;
  }

  function setLoading(busy: boolean): void {
    listContainer.setAttribute("aria-busy", String(busy));
    itemsPanel.classList.toggle("is-loading", busy);
  }

  function renderStats(items: Item[], totalCount: number): void {
    const totalUnits = items.reduce((sum, item) => sum + item.quantity, 0);
    const distinctTags = new Set(items.flatMap((item) => item.tags)).size;
    statsContainer.replaceChildren(
      statTile("Items", String(totalCount)),
      statTile("Units (page)", String(totalUnits)),
      statTile("Tags (page)", String(distinctTags)),
    );
  }

  function renderPagination(): void {
    const from = total === 0 ? 0 : skip + 1;
    const to = Math.min(skip + PAGE_SIZE, total);
    rangeLabel.textContent = `${String(from)}–${String(to)} of ${String(total)}`;
    prevButton.disabled = skip === 0;
    nextButton.disabled = skip + PAGE_SIZE >= total;
  }

  function renderList(items: Item[]): void {
    if (items.length === 0) {
      listContainer.replaceChildren(renderEmptyState(query.length > 0));
      return;
    }
    listContainer.replaceChildren(...items.map(renderItem));
  }

  function renderItem(item: Item): HTMLElement {
    const avatar = el("div", { class: "item__avatar", "aria-hidden": "true" }, [
      (item.name.trim()[0] ?? "?").toUpperCase(),
    ]);

    const bodyChildren: HTMLElement[] = [
      el("div", { class: "item__heading" }, [
        el("span", { class: "item__name" }, [item.name]),
        el("span", { class: "item__badge" }, [`${String(item.quantity)} in stock`]),
      ]),
    ];
    if (item.description) {
      bodyChildren.push(el("p", { class: "item__description" }, [item.description]));
    }
    if (item.tags.length > 0) {
      bodyChildren.push(
        el(
          "div",
          { class: "item__tags" },
          item.tags.map((tag) => el("span", { class: "chip" }, [tag])),
        ),
      );
    }

    const decrement = iconButton(ICON_MINUS, "Decrease quantity", "btn btn--icon");
    decrement.addEventListener("click", () => {
      void adjustQuantity(item, -1);
    });
    const increment = iconButton(ICON_PLUS, "Increase quantity", "btn btn--icon");
    increment.addEventListener("click", () => {
      void adjustQuantity(item, 1);
    });
    const remove = iconButton(ICON_TRASH, "Delete item", "btn btn--icon btn--danger");
    remove.addEventListener("click", () => {
      void onDelete(item);
    });

    return el("article", { class: "item" }, [
      el("div", { class: "item__lead" }, [avatar, el("div", { class: "item__body" }, bodyChildren)]),
      el("div", { class: "item__actions" }, [
        el("div", { class: "item__stepper" }, [decrement, increment]),
        remove,
      ]),
    ]);
  }

  async function reload(): Promise<void> {
    setLoading(true);
    try {
      const page = await listItems({ limit: PAGE_SIZE, skip, q: query || undefined });
      total = page.total;
      renderStats(page.items, page.total);
      renderList(page.items);
      renderPagination();
      if (page.total === 0) {
        setStatus(
          query ? "No items match your search." : "No items yet. Create the first one above.",
          "info",
        );
      } else {
        setStatus("", "none");
      }
    } catch (error) {
      total = 0;
      renderStats([], 0);
      listContainer.replaceChildren();
      renderPagination();
      setStatus(describeError(error), "error");
    } finally {
      setLoading(false);
    }
  }

  async function onCreate(data: ItemCreate): Promise<void> {
    form.setBusy(true);
    try {
      await createItem(data);
      form.reset();
      skip = 0;
      await reload();
    } catch (error) {
      setStatus(describeError(error), "error");
    } finally {
      form.setBusy(false);
    }
  }

  async function adjustQuantity(item: Item, delta: number): Promise<void> {
    try {
      await updateItem(item.id, { quantity: Math.max(0, item.quantity + delta) });
      await reload();
    } catch (error) {
      setStatus(describeError(error), "error");
    }
  }

  async function onDelete(item: Item): Promise<void> {
    try {
      await deleteItem(item.id);
      await reload();
    } catch (error) {
      setStatus(describeError(error), "error");
    }
  }

  void reload();
}

function panelTitle(text: string, iconPath: string): HTMLElement {
  return el("h2", { class: "panel__title" }, [
    el("span", { class: "panel__icon", "aria-hidden": "true" }, [icon(iconPath, 16)]),
    text,
  ]);
}

function statTile(label: string, value: string): HTMLElement {
  return el("div", { class: "stat" }, [
    el("span", { class: "stat__value" }, [value]),
    el("span", { class: "stat__label" }, [label]),
  ]);
}

function iconButton(iconPath: string, label: string, className: string): HTMLButtonElement {
  return el("button", { class: className, type: "button", "aria-label": label, title: label }, [
    icon(iconPath, 16),
  ]);
}

function renderEmptyState(searching: boolean): HTMLElement {
  return el("div", { class: "empty" }, [
    el("div", { class: "empty__icon", "aria-hidden": "true" }, [icon(ICON_BOX, 40)]),
    el("p", { class: "empty__text" }, [
      searching ? "No items match your search." : "No items yet — create one to see it here.",
    ]),
  ]);
}

function buildForm(onSubmit: (data: ItemCreate) => Promise<void>): FormApi {
  const name = inputField("name", "Name", "text", true, "e.g. Fibre spool");
  const description = inputField("description", "Description", "text", false, "Optional details");
  const quantity = inputField("quantity", "Quantity", "number", false, "0");
  const tags = inputField("tags", "Tags", "text", false, "comma, separated");
  const submit = el("button", { class: "btn btn--primary", type: "submit" }, [
    icon(ICON_PLUS, 16),
    el("span", {}, ["Create item"]),
  ]);

  const form = el("form", { class: "form" }, [
    name.field,
    description.field,
    quantity.field,
    tags.field,
    el("div", { class: "form__actions" }, [submit]),
  ]);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const payload: ItemCreate = {
      name: name.input.value.trim(),
      description: description.input.value.trim() || null,
      quantity: quantity.input.value ? Number(quantity.input.value) : 0,
      tags: parseTags(tags.input.value),
    };
    void onSubmit(payload);
  });

  return {
    element: form,
    reset: () => {
      form.reset();
    },
    setBusy: (busy: boolean) => {
      submit.disabled = busy;
    },
  };
}

function inputField(
  id: string,
  label: string,
  type: string,
  required: boolean,
  placeholder: string,
): Field {
  const input = el("input", { id, name: id, type, class: "form__input", placeholder });
  if (required) {
    input.required = true;
  }
  if (type === "number") {
    input.min = "0";
  }
  const field = el("div", { class: "form__field" }, [
    el("label", { class: "form__label", for: id }, [label]),
    input,
  ]);
  return { field, input };
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.status === 0 ? error.message : `${error.message} (${error.code})`;
  }
  return "An unexpected error occurred";
}
