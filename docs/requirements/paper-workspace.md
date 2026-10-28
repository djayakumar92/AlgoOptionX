# AlgoOptionX acceptance traceability

These criteria cover the implemented local slice, not the entire enterprise roadmap.

| Requirement | Acceptance | Evidence-producing test |
|---|---|---|
| SIM-01 | Synthetic startup requires no broker credentials | `test_api_offline_commands_replay_and_security` |
| MONEY-01 | Virtual account funded once; exact cash/fee arithmetic | `test_funding_restart_and_idempotency`, `test_round_trip_exact_money_and_history` |
| MONEY-02 | Cash + cost basis = initial funding + realized P&L after mixed commands | `test_accounting_conservation` (Hypothesis sequences) |
| RISK-01 | Duplicates, invalid size, daily loss and unsupported contracts rejected | `test_limits_and_failed_command_rollback` |
| RISK-02 | Concurrent entries cannot exceed account limits | `test_concurrent_entry_limit` |
| RISK-03 | Kill flattens and blocks new entries | `test_kill_flattens_and_blocks_entries`; browser emergency-exit journey |
| EXEC-01 | Retry has one economic effect; changed request with same key rejected | `test_funding_restart_and_idempotency` |
| EXEC-02 | Autonomous decisions produce entries/exits; restart pauses; session close flattens | `test_autonomous_exits_restart_and_session_close` |
| AUDIT-01 | Stored hashes reconstruct the account event chain | `test_hash_chain_reconstructs`; browser export journey |
| REPLAY-01 | Same replay has same economic output; active account untouched | `test_api_offline_commands_replay_and_security`; browser replay journey |
| TIME-01 | Future fixture evaluation cannot mutate earlier quotes | `test_future_market_calls_cannot_change_past` |
| API-01 | Strict inputs, bounded replay, unknown routes and traversal denied | `test_api_offline_commands_replay_and_security` |
| UI-01 | Buy → position → close → audit is functional in browser | `buy, mark, close and export a virtual trade` |
| UI-02 | All routes fit 1440/1024/390 widths; navigation works on mobile | `responsive routes and candidate screenshots` |

Run artifacts: pytest JUnit, Playwright HTML report, traces on failure and screenshot candidates. CI retains reports. There is no approved visual baseline or externally verified independent QA attestation yet.

Remaining roadmap: realistic option paths/partial fills, licensed historical datasets, walk-forward and leakage validation for learned models, complete archived-session browsing, destructive legacy research migration replacement, authenticated hosted APIs, tenant isolation, subscription/broker adapters, immutable externally anchored evidence and human-only release enforcement. Existing test skips must remain visible. None of those future capabilities is implied by this acceptance matrix.
