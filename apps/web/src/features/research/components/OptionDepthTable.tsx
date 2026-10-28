import { fmtInt, fmtNum } from "../format";
import type { ChainRow } from "../types";

// The per-strike deep-dive that makes Option Intelligence different from the
// Live page's compact OI/LTP table -- IV, delta, volume, and the bid/ask
// spread, all real fields already captured per poll but never surfaced.
export function OptionDepthTable({ rows }: { rows: ChainRow[] }) {
  return (
    <section className="panel chain-panel">
      <h2>Option Chain Depth (around ATM)</h2>
      <table className="chain-table">
        <thead>
          <tr>
            <th>CE IV</th>
            <th>CE Delta</th>
            <th>CE Volume</th>
            <th>CE Bid/Ask</th>
            <th>Strike</th>
            <th>PE Bid/Ask</th>
            <th>PE Volume</th>
            <th>PE Delta</th>
            <th>PE IV</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.strike} className={row.is_atm ? "atm-row" : ""}>
              <td>{fmtNum(row.ce_iv)}</td>
              <td>{fmtNum(row.ce_delta, 3)}</td>
              <td>{fmtInt(row.ce_volume)}</td>
              <td>
                {row.ce_bid !== null || row.ce_ask !== null
                  ? `${fmtNum(row.ce_bid)} / ${fmtNum(row.ce_ask)}`
                  : "-"}
              </td>
              <td className="strike-cell">
                {fmtNum(row.strike, 0)}
                {row.is_atm && " (ATM)"}
              </td>
              <td>
                {row.pe_bid !== null || row.pe_ask !== null
                  ? `${fmtNum(row.pe_bid)} / ${fmtNum(row.pe_ask)}`
                  : "-"}
              </td>
              <td>{fmtInt(row.pe_volume)}</td>
              <td>{fmtNum(row.pe_delta, 3)}</td>
              <td>{fmtNum(row.pe_iv)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
