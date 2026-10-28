export type LayoutId = "1" | "2-col" | "2-row" | "3-left" | "4-grid";

export interface LayoutOption {
  id: LayoutId;
  label: string;
  paneCount: number;
  gridClassName: string;
  // grid-area name per pane index -- only set for layouts with unequal panes
  areas?: string[];
}

export const LAYOUT_OPTIONS: LayoutOption[] = [
  { id: "1", label: "1 chart", paneCount: 1, gridClassName: "chart-grid-1" },
  { id: "2-col", label: "2 side by side", paneCount: 2, gridClassName: "chart-grid-2col" },
  { id: "2-row", label: "2 stacked", paneCount: 2, gridClassName: "chart-grid-2row" },
  { id: "3-left", label: "1 large + 2", paneCount: 3, gridClassName: "chart-grid-3left", areas: ["a", "b", "c"] },
  { id: "4-grid", label: "4 grid", paneCount: 4, gridClassName: "chart-grid-4" },
];
