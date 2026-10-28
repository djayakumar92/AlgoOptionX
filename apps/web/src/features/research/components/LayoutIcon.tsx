import { LAYOUT_OPTIONS, type LayoutId } from "../chartLayouts";

export function LayoutIcon({ id }: { id: LayoutId }) {
  const option = LAYOUT_OPTIONS.find((o) => o.id === id);
  if (!option) return null;

  return (
    <span className={`layout-icon ${option.gridClassName}-icon`}>
      {Array.from({ length: option.paneCount }).map((_, i) => (
        <span
          key={i}
          className="layout-icon-cell"
          style={option.areas ? { gridArea: option.areas[i] } : undefined}
        />
      ))}
    </span>
  );
}
