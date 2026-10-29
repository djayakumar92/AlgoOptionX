# Versioned decisions and read-only analytics shadow

Implemented work: **OBS-01 and OBS-02**. The intelligence core provides strict records and a deterministic composer; the research-owned adapter reuses existing analytics against completed, available data. This batch produces reports, not orders, model promotion or changed trading behavior.

## See the output

From the repository with its existing dependencies installed:

```bash
uv run python -m algooptionx.research.shadow --demo
# Save a new report; existing paths are never overwritten:
uv run python -m algooptionx.research.shadow --demo --output /tmp/algooptionx-shadow-report.json
# Export the actual runtime schemas:
uv run python -m algooptionx.research.shadow --schema
uv run python -m algooptionx.research.shadow --schema input
# Evaluate a validated input JSON with explicit candles/session/chain metadata:
uv run python -m algooptionx.research.shadow --input shadow-input.json
```

The demo constructs a separate, deterministic **synthetic OHLCV engineering fixture**, not traded data reconstructed from the paper engine's spot marks. Its current report is NO_TRADE because the completed 5-minute structure is BULLISH while the completed 30-minute structure is UNCLEAR. The record includes source kind/hash, rule/version, all observations, availability times, limitations, reason codes and expiry; candidate is null and shadow is true. This is not an evaluated profitable model or a live prediction.

`ShadowInput.model_dump_json()` serializes an input; JSON parsing and typed Python construction have intentionally strict boundaries. In Python, pass actual `Session`/`Candle` objects; in JSON, use their exported schema with offset-aware ISO timestamps. The CLI accepts at most20MiB,1440 source bars and2048 option rows. Malformed payloads return a nonzero status with sanitized error type, without echoing input values. A valid diagnostic INSUFFICIENT_DATA record is not a test pass or a trade signal.

## Runtime records and invariants

`algooptionx.intelligence.contracts` contains frozen, strict `Source`, `Strategy`, `Observation`, `Uncertainty`, `Candidate` and `Decision` models. Unknown fields, naive timestamps, bools/floats masquerading as integer metadata, nonfinite measurements, mismatched units and duplicate observations fail validation. Tuples and frozen nested records prevent ordinary mutation; records are revalidated when used by the adapter.

The runtime shadow-v1 envelope extends the archived planning draft with metric/timeframe/reason fields, limitations, shadow flag and explicit candidate instrument identity. The generated runtime schema is authoritative for this implementation; the original planning JSON Schema remains an unchanged proposal snapshot. Cross-field/time/approval limitations also need runtime validators; JSON Schema export alone cannot enforce them all.

States are BULLISH, BEARISH, SIDEWAYS, NO_TRADE and INSUFFICIENT_DATA. Every state other than INSUFFICIENT_DATA requires all current required observations: completed5/30-minute windows, sufficient confirmed structure at both intervals, a known regime and a valid current chain. Missing or invalid required evidence cannot be relabeled NO_TRADE. Adequate opposing/unclear structure gives NO_TRADE; UNCLEAR alone does not establish SIDEWAYS without an existing RANGING regime. Directional states must match both structure observations. Optional unknown inputs retain their own explicit status.

`Decision.available_at` equals the latest observation availability and must not exceed as-of. Observation event time cannot follow availability. TTL is positive and at most five minutes; the adapter also caps expiry at the next completed5-minute boundary and session close. The decision ID hashes as-of, resolved expiry, source envelope, strategy identity, state and evidence, so changing source/observations/TTL changes its identity.

Rule probabilities and model versions stay null. Uncertainty has a reserved structural model format, but the current Decision validator rejects **all calibrated-model/model-version claims** until actual trusted registry, calibration and promotion bindings are implemented in the later model tasks. Arbitrary IDs do not constitute approved calibration. Candidate validation supports only strict positive-integer long-buy proposals with matching CE/PE direction and stop<entry<target; the composer always returns candidate null. Nothing in this schema confers execution permission.

## Actual research reuse and point-in-time handling

`algooptionx.research.shadow` invokes retained `market_structure.find_swings/classify_structure/classify_day_type/choppiness_index`, `trend.summarize`, `regime.summarize` and `sentiment.summarize`. Original functions and their consumers are not modified. The adapter converts integer paise to the rupee floats expected by those legacy research functions, not to the paper account's accounting representation.

Only completed contiguous5/30-minute outputs from `aggregate_completed` are analyzed. A missing/late minute prevents reuse of an older window as current confirmation. Structure requires at least seven completed bars at each timeframe; having the first30-minute candle does not imply enough confirmed swing history. Legacy fractal pivots need right-hand neighbors: observations are conservatively available at the latest contributing completed bar's receipt, not backdated to the earlier pivot. The adapter does not expose the legacy resampler's partial1-hour/daily views.

Future/unreceived candles and snapshots are invisible, including in provenance hashes; future perturbations cannot rewrite earlier reports. Available invalid/mixed metadata is reported as invalid/insufficient rather than silently sorted or guessed. Source hashes bind the available raw input and observation inputs; they are local content identity, not provider authenticity, data rights or externally signed approval.

Chain snapshots require coherent event/receive times, effective underlying/source/data/calendar/instrument versions, unexpired metadata, both option rights, unique instrument/strike/right identities and noncrossed positive-integer quotes. The current chain-age allowance is at most one minute. IV, quantities and prices have explicit adapter limits to keep legacy float/NumPy calculations meaningful: paise≤2**53−1, per-row/source-minute units≤10**12 and quoted IV≤1000percent. Pure `Candle` integer contracts are not weakened; only eligible inputs are bounded before legacy conversion. Out-of-range eligible source bars become INVALID_DATA/INSUFFICIENT_DATA, while unreceived future values stay invisible.

A regime rule score is labeled `rule-score`, never probability. No historical daily dataset or observed dealer inventory is supplied by the single-session adapter. Legacy business-day/expiry assumptions and hypotheses still need separately versioned exchange/calendar evidence before financial use. Output limitations preserve these gaps; PCR is an observed ratio, not proof of seller or institutional intent.

## Authority, validation and rollout

The intelligence core imports no research runtime, paper engine, storage or network client. The research adapter imports pure signals and data contracts; it does not read account state, call providers, start workers, write a ledger or submit a command. CLI file output is explicit and exclusive, so it cannot overwrite an existing input/report/database path. Reports can be inspected independently of the application.

Tests cover all five states, strict schema and numeric metadata, future/pivot availability, TTL identity, missing/conflicting/stale/malformed inputs, model-claim refusal, actual legacy reuse, JSON roundtrip, source changes, future-perturbation properties, no database/network calls, exclusive output and sanitized errors. Source-bound full evidence and a distinct validator handoff are required before merge. Existing API/UI, paper strategies, risk limits, costs and economic event semantics are preserved.

Roll back by removing/disabling the additive shadow modules/CLI use and keep old APIs/data intact. No database migration is part of this rollout. Later PAPER-01 must recheck source/session/TTL/policy/kill and accounting inside its economic transaction; accepting a record or passing shadow tests is not permission to trade. Broader UI, patterns, models and live/hosted activation remain separate roadmap items.
