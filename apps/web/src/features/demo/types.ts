export type Strategy = 'bull-put'|'bear-call'|'iron-condor';
export type Draft = {strategy:Strategy;lots:number;expiry:string;strikes:number[]};
export type Quote = {id:string;expiry:string;strike:number;right:'CE'|'PE';mark:number;ltp:number;bid:number;ask:number;spread:number;iv:number;oi:number;change_oi:number;volume:number;lot_size:number;liquidity_warning:boolean;delta:number|null;gamma:number|null;vega:number|null;theta:number|null;rho:number|null};
export type Leg = {right:'CE'|'PE';side:number;strike:number;instrument:string;expiry:string;quantity:number;entry:number;mark:number;exit?:number};
export type Payoff = {spot:number;pnl:number};
export type Preview = Draft & {quantity:number;legs:Leg[];premium:number;entry_fees:number;entry_net_credit:number;exit_fees:number;exit_friction:number;net_credit:number;max_profit:number;max_loss:number;reserve:number;expiry_max_loss_before_exit_costs:number;breakevens:number[];payoff:Payoff[];pricing_version:string;warning:string;quote_token:string;valid:boolean;errors:string[];session_id:string;tick:number;quote_tick:number;entry_reason?:string;exit_reason?:string;quote_source?:string};
export type Position = {id:string;account_id:string;data:Preview;status:'OPEN'|'CLOSED';opened_tick:number;closed_tick:number|null;pnl:number|null;note:string;category:string;liquidation_pnl?:number;scenario?:string};
export type Candle = {time:string;open:number;high:number;low:number;close:number;volume:number;minutes:number;ema9:number;ema_warmup:number;vwap:number|null};
export type AuditEvent = {seq:number;tick:number;kind:string;hash:string;previous_hash:string;payload:{message?:string;position_id?:string;pnl?:number;reason?:string;quote_source?:string}};
export type State = {
 mode:string;source:string;revision:string;pricing_version:string;
 session:{id:string;scenario:string;tick:number;quote_tick:number;connected:number;killed:number;kill_error:string;time:string;quote_time:string};
 scenarios:{id:string;label:string}[];spot:number;expiries:string[];contracts:Quote[];candles:Record<'5'|'30',Candle[]>;
 account:{capital:number;cash:number;equity:number;liquidation_equity:number;pnl:number;realized:number;unrealized:number;fees:number;reserve:number;available_risk_capital:number;daily_loss:number;open_count:number};
 limits:{max_positions:number;trade_reserve_limit:number;aggregate_reserve_limit:number;daily_loss_limit:number};
 analysis:{direction:string;structure:string;change_30m:number;confirmation_30m:number|null;support:number;resistance:number;gap:number;volume:number;iv:number;observations:string[];limitations:string};
 positions:Position[];journal:Position[];events:AuditEvent[];
 assumptions:{rate:number;iv:number;lot_size:number;fee_per_leg_fill:number;spread:number;slippage:number;disclaimer:string};
};
export type Segment={start_tick:number;end_tick:number;samples:number;pnl:number;costs:number;max_drawdown:number;curve:{tick:number;equity:number}[]};
export type Research={source:string;strategy:string;scenario:string;lots:number;version:string;split:number;in_sample:Segment;out_of_sample:Segment;folds:Segment[];assumptions:string;limitations:string};

export type ChartAnnotation={id:string;kind:'horizontal';price:number}|{id:string;kind:'trend';startTime:string;startPrice:number;endTime:string;endPrice:number};
