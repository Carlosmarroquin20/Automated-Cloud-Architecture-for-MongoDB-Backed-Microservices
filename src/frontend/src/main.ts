import "./styles/main.css";
import { el } from "./ui/dom";
import { mountHealthView } from "./ui/health-view";
import { brandMark } from "./ui/icons";
import { mountItemsView } from "./ui/items-view";

function bootstrap(): void {
  const root = document.querySelector<HTMLDivElement>("#app");
  if (!root) {
    throw new Error("application root element '#app' is missing");
  }

  const brand = el("div", { class: "brand" }, [
    el("span", { class: "brand__mark", "aria-hidden": "true" }, [brandMark()]),
    el("div", { class: "brand__text" }, [
      el("h1", { class: "brand__title" }, ["MongoDB Microservice Console"]),
      el("p", { class: "brand__subtitle" }, ["Reference client for the items API"]),
    ]),
  ]);
  const healthMount = el("div", { class: "health" });
  const header = el("header", { class: "app-header" }, [brand, healthMount]);
  const main = el("main", { class: "app-main" });
  const footer = el("footer", { class: "app-footer" }, [
    el("span", {}, ["Automated Cloud Architecture · FastAPI + MongoDB Atlas"]),
  ]);

  root.append(header, main, footer);
  mountHealthView(healthMount);
  mountItemsView(main);
}

bootstrap();
