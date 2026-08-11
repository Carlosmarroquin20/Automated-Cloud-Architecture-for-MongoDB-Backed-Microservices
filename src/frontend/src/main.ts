import "./styles/main.css";
import { el } from "./ui/dom";
import { mountHealthView } from "./ui/health-view";
import { mountItemsView } from "./ui/items-view";

function bootstrap(): void {
  const root = document.querySelector<HTMLDivElement>("#app");
  if (!root) {
    throw new Error("application root element '#app' is missing");
  }

  const titles = el("div", { class: "app-header__titles" }, [
    el("h1", { class: "app-header__title" }, ["MongoDB Microservice Console"]),
    el("p", { class: "app-header__subtitle" }, ["Reference client for the items API"]),
  ]);
  const healthMount = el("div", { class: "health" });
  const header = el("header", { class: "app-header" }, [titles, healthMount]);
  const main = el("main", { class: "app-main" });

  root.append(header, main);
  mountHealthView(healthMount);
  mountItemsView(main);
}

bootstrap();
