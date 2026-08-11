import type { Item, ItemCreate } from "../types/item";
import { ApiError } from "../api/errors";
import { createItem, deleteItem, listItems, updateItem } from "../api/items";
import { el } from "./dom";
import { formatTags, parseTags } from "./tags";

type StatusKind = "error" | "info" | "none";

interface FormApi {
  element: HTMLFormElement;
  reset: () => void;
}

interface Field {
  field: HTMLElement;
  input: HTMLInputElement;
}

export function mountItemsView(root: HTMLElement): void {
  const status = el("p", { class: "status", role: "status", "aria-live": "polite" });
  const listContainer = el("div", { class: "item-list" });
  const form = buildForm(onCreate);

  root.append(
    el("section", { class: "panel" }, [
      el("h2", { class: "panel__title" }, ["Create item"]),
      form.element,
      el("h2", { class: "panel__title" }, ["Items"]),
      status,
      listContainer,
    ]),
  );

  function setStatus(message: string, kind: StatusKind): void {
    status.textContent = message;
    status.className = kind === "none" ? "status" : `status status--${kind}`;
  }

  function renderList(items: Item[]): void {
    listContainer.replaceChildren(...items.map(renderItem));
  }

  function renderItem(item: Item): HTMLElement {
    const meta = el("div", { class: "item__meta" }, [
      el("span", { class: "item__name" }, [item.name]),
      el("span", { class: "item__badge" }, [`qty ${String(item.quantity)}`]),
    ]);

    const detailChildren: HTMLElement[] = [];
    if (item.description) {
      detailChildren.push(el("p", { class: "item__description" }, [item.description]));
    }
    if (item.tags.length > 0) {
      detailChildren.push(el("p", { class: "item__tags" }, [formatTags(item.tags)]));
    }

    const decrement = el(
      "button",
      { class: "btn btn--ghost", type: "button", "aria-label": "Decrease quantity" },
      ["−"],
    );
    decrement.addEventListener("click", () => {
      void adjustQuantity(item, -1);
    });

    const increment = el(
      "button",
      { class: "btn btn--ghost", type: "button", "aria-label": "Increase quantity" },
      ["+"],
    );
    increment.addEventListener("click", () => {
      void adjustQuantity(item, 1);
    });

    const remove = el("button", { class: "btn btn--danger", type: "button" }, ["Delete"]);
    remove.addEventListener("click", () => {
      void onDelete(item);
    });

    return el("article", { class: "item" }, [
      meta,
      el("div", { class: "item__details" }, detailChildren),
      el("div", { class: "item__actions" }, [decrement, increment, remove]),
    ]);
  }

  async function reload(): Promise<void> {
    try {
      const items = await listItems();
      renderList(items);
      if (items.length === 0) {
        setStatus("No items yet. Create the first one above.", "info");
      } else {
        setStatus("", "none");
      }
    } catch (error) {
      setStatus(describeError(error), "error");
    }
  }

  async function onCreate(data: ItemCreate): Promise<void> {
    try {
      await createItem(data);
      form.reset();
      await reload();
    } catch (error) {
      setStatus(describeError(error), "error");
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

function buildForm(onSubmit: (data: ItemCreate) => Promise<void>): FormApi {
  const name = inputField("name", "Name", "text", true);
  const description = inputField("description", "Description", "text", false);
  const quantity = inputField("quantity", "Quantity", "number", false);
  const tags = inputField("tags", "Tags (comma-separated)", "text", false);
  const submit = el("button", { class: "btn btn--primary", type: "submit" }, ["Create"]);

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
  };
}

function inputField(id: string, label: string, type: string, required: boolean): Field {
  const input = el("input", { id, name: id, type, class: "form__input" });
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
