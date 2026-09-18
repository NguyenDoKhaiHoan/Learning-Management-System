export function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  text = "",
  className = "",
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
}

export function button(text: string, action: () => void, className = "button") {
  const node = element("button", text, className);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}

export function field(
  label: string,
  name: string,
  type = "text",
  required = true,
) {
  const wrap = element("label", label, "field");
  const input = element("input");
  input.name = name;
  input.type = type;
  input.required = required;
  wrap.append(input);
  return wrap;
}
