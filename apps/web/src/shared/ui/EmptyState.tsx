import { Icon } from "./Icon";

export function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="ax-empty">
      <Icon name="wallet" size={28} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
