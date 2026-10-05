import { button, element } from "./dom";

export function actionForm(
  fields: HTMLElement[],
  label: string,
  action: (data: FormData) => Promise<unknown>,
  onError: (error: unknown) => void,
) {
  const node = element("form", "", "form-stack");
  const submit = element("button", label, "button");
  submit.type = "submit";
  node.append(...fields, submit);
  node.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submit.disabled || !node.reportValidity()) return;
    submit.disabled = true;
    node.setAttribute("aria-busy", "true");
    try {
      await action(new FormData(node));
    } catch (error) {
      onError(error);
    } finally {
      submit.disabled = false;
      node.removeAttribute("aria-busy");
    }
  });
  return node;
}

export function selectField(
  label: string,
  name: string,
  choices: [string, string][],
  value = "",
) {
  const wrap = element("label", label, "field");
  const select = element("select");
  select.name = name;
  select.setAttribute("aria-label", label);
  for (const [id, text] of choices) {
    const option = element("option", text);
    option.value = id;
    select.append(option);
  }
  if (value) select.value = value;
  wrap.append(select);
  return wrap;
}

export function prefill(wrap: HTMLElement, value: string | number | boolean) {
  const input = wrap.querySelector("input,textarea,select") as HTMLInputElement;
  if (input.type === "checkbox") input.checked = Boolean(value);
  else input.value = String(value);
  return wrap;
}

export function pagination(
  offset: number,
  limit: number,
  total: number,
  go: (offset: number) => void,
) {
  const nav = element("nav", "", "pagination");
  nav.setAttribute("aria-label", "Phân trang");
  const previous = button(
    "Trang trước",
    () => go(Math.max(0, offset - limit)),
    "button secondary",
  );
  const next = button(
    "Trang sau",
    () => go(offset + limit),
    "button secondary",
  );
  previous.disabled = offset === 0;
  next.disabled = offset + limit >= total;
  nav.append(
    previous,
    element(
      "span",
      total
        ? `${offset + 1}–${Math.min(offset + limit, total)} / ${total}`
        : "0 kết quả",
    ),
    next,
  );
  return nav;
}

export function statistics(items: [string, number][]) {
  const node = element("div", "", "dashboard-stats");
  for (const [label, value] of items) {
    const stat = element("div", "", "stat");
    stat.append(element("span", label), element("strong", String(value)));
    node.append(stat);
  }
  return node;
}

export interface PageActions {
  perform: (action: () => Promise<unknown>, success: string) => Promise<void>;
  error: (error: unknown) => void;
  navigate: (path: string) => void;
  current: () => boolean;
}
