export { money, number } from "../../../shared/lib/format";

export const contractName = (id: string) => {
  const parts = id.split("-");
  return `NIFTY ${parts[2]} ${parts[3]}`;
};
