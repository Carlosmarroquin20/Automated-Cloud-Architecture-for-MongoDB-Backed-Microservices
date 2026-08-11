// Inline SVG icons. Rendered as namespaced DOM nodes rather than injected markup
// so the icon set adds no external requests and no HTML-parsing surface.

const SVG_NS = "http://www.w3.org/2000/svg";

export const ICON_PLUS = "M12 5v14M5 12h14";
export const ICON_MINUS = "M5 12h14";
export const ICON_TRASH = "M4 7h16M9 7V4h6v3M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13M10 11v6M14 11v6";
export const ICON_BOX = "M21 8l-9-5-9 5 9 5 9-5M3 8v8l9 5 9-5V8M12 13v10";

export function icon(pathData: string, size = 18): SVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", pathData);
  svg.append(path);
  return svg;
}

export function brandMark(): SVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", "22");
  svg.setAttribute("height", "22");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  const ellipse = document.createElementNS(SVG_NS, "ellipse");
  ellipse.setAttribute("cx", "12");
  ellipse.setAttribute("cy", "5");
  ellipse.setAttribute("rx", "8");
  ellipse.setAttribute("ry", "3");
  const body = document.createElementNS(SVG_NS, "path");
  body.setAttribute("d", "M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3");
  svg.append(ellipse, body);
  return svg;
}
