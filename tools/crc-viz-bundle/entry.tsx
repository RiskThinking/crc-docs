import { createRoot, type Root } from "react-dom/client";
import { CRCMap } from "@climateriskcommons/crc-viz/maps";
import "./styles.css";

type Props = Parameters<typeof CRCMap>[0];

const roots = new WeakMap<Element, Root>();

export function mountHazardMap(el: Element, props: Props) {
  const root = roots.get(el) ?? createRoot(el);
  roots.set(el, root);
  root.render(<CRCMap height="100%" {...props} />);
}

export function unmountHazardMap(el: Element) {
  roots.get(el)?.unmount();
  roots.delete(el);
}
