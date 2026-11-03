import {useId} from 'react';
import type {Payoff} from './types';
import {money,number} from './api';

export {InteractiveChart as Candles} from './InteractiveChart';

export function PayoffChart({points}:{points:Payoff[]}) {
 const id=useId();if(!points.length)return null;
 const minX=points[0].spot,maxX=points[points.length-1].spot;
 const minY=Math.min(0,...points.map(p=>p.pnl)),maxY=Math.max(1,...points.map(p=>p.pnl));
 const x=(v:number)=>30+(v-minX)/Math.max(1,maxX-minX)*590;
 const y=(v:number)=>20+(maxY-v)/Math.max(1,maxY-minY)*180;
 return <figure className="demo-chart"><svg viewBox="0 0 760 245" role="img" aria-labelledby={id}>
  <title id={id}>Illustrative expiry payoff after assumed round-trip costs</title>
  <desc>Maximum plotted profit {money(maxY)}, maximum plotted loss {money(-minY)}. Not a market forecast.</desc>
  <line x1="25" x2="625" y1={y(0)} y2={y(0)} className="demo-zero"/>
  <polyline points={points.map(p=>`${x(p.spot)},${y(p.pnl)}`).join(' ')} className="demo-payoff"/>
  <text x="635" y="25">{money(maxY)}</text><text x="635" y="202">{money(minY)}</text>
  <text x="25" y="230">{number(minX,0)} points</text><text x="535" y="230">{number(maxX,0)}</text>
 </svg><figcaption>Defined-risk expiry illustration with estimated exit spread, slippage and fees. Executable liquidation is shown separately in Paper Trading.</figcaption></figure>;
}
