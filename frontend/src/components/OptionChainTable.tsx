import { fmtInt, fmtNum } from "../format";
import type { ChainRow } from "../types";

export function OptionChainTable({ rows }: { rows: ChainRow[] }) {
  return (
    <section className="panel chain-panel">
      <h2>Option Chain (around ATM)</h2>
      <table className="chain-table">
        <thead>
          <tr>
            <th>CE OI</th>
            <th>CE LTP</th>
            <th>Strike</th>
            <th>PE LTP</th>
            <th>PE OI</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.strike} className={row.is_atm ? "atm-row" : ""}>
              <td>{fmtInt(row.ce_oi)}</td>
              <td>{fmtNum(row.ce_ltp)}</td>
              <td className="strike-cell">
                {fmtNum(row.strike, 0)}
                {row.is_atm && " (ATM)"}
              </td>
              <td>{fmtNum(row.pe_ltp)}</td>
              <td>{fmtInt(row.pe_oi)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
