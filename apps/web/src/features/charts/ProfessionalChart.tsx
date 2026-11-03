import { useEffect, useRef, useState } from "react";
import { AreaSeries, BarSeries, CandlestickSeries, LineSeries, HistogramSeries, createChart, ColorType } from "lightweight-charts";
import type { IChartApi, ISeriesApi, Time, UTCTimestamp } from "lightweight-charts";
export type Bar = {time:string;open:number;high:number;low:number;close:number;volume:number;vwap:number|null;ema9:number;indicators:Record<string,number|null>};
export type Drawing = {id:string;pane:number;session_id:string;kind:string;time1:string;price1:number;time2?:string|null;price2?:number|null;text:string};
export type MarketBars = {source:string;session_id:string;interval:number;connected:boolean;bars:Bar[];notice:string;as_of:string};
export type ChartSync = {from:number;to:number;origin:number}|null;
export type Crosshair = {time:number;price:number;origin:number}|null;
const formatMarketTime=(time:Time)=>typeof time==='number'?new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(time*1000)):String(time);
const utc=(value:string)=>Math.floor(Date.parse(value)/1000) as UTCTimestamp;
function Oscillator({bars,keys,label}:{bars:Bar[];keys:string[];label:string}){
  const points=bars.flatMap(bar=>keys.map(key=>bar.indicators[key])).filter((value):value is number=>value!==null&&value!==undefined);
  const min=Math.min(0,...points),max=Math.max(1,...points);const colors=["#4338ca","#b45309","#067647"];
  return <figure className="chart-oscillator"><figcaption>{label} · {points.length?"Descriptive indicator":"Insufficient warm-up history"}</figcaption><svg viewBox="0 0 800 100" role="img" aria-label={label}>{keys.map((key,i)=>{const values=bars.map((bar,index)=>({value:bar.indicators[key],index})).filter(point=>point.value!==null&&point.value!==undefined);return <polyline key={key} fill="none" stroke={colors[i]} strokeWidth="1.5" points={values.map(point=>`${20+point.index/Math.max(1,bars.length-1)*740},${10+(max-point.value!)/Math.max(.0001,max-min)*70}`).join(" ")}/>;})}<text x="4" y="12" fontSize="9">{max.toFixed(2)}</text><text x="4" y="96" fontSize="9">{min.toFixed(2)}</text></svg></figure>;
}
export default function ProfessionalChart({data,type,indicators,drawings,pane,syncRange,onRange,crosshair,onCrosshair}:{data:MarketBars;type:string;indicators:string[];drawings:Drawing[];pane:number;syncRange:ChartSync;onRange:(value:ChartSync)=>void;crosshair:Crosshair;onCrosshair:(value:Crosshair)=>void}){
  const host=useRef<HTMLDivElement>(null),chart=useRef<IChartApi|null>(null),price=useRef<ISeriesApi<"Candlestick">|null>(null);
  const update=useRef<(bars:Bar[])=>void>(()=>{}),suppress=useRef(false),callbacks=useRef({onRange,onCrosshair});callbacks.current={onRange,onCrosshair};
  const [geometry,setGeometry]=useState(0),[visible,setVisible]=useState<{from:number;to:number}|null>(null);
  const appliedRange=useRef<{from:number;to:number}|null>(null),appliedCrosshair=useRef<{time:number;price:number}|null>(null);
  const viewport=useRef<{from:Time;to:Time}|null>(null),identity=useRef("");
  const indicatorKey=indicators.join(",");
  useEffect(()=>{
    if(!host.current)return;const api=createChart(host.current,{autoSize:true,height:340,layout:{background:{type:ColorType.Solid,color:"#ffffff"},textColor:"#475569"},grid:{vertLines:{color:"#edf1f7"},horzLines:{color:"#edf1f7"}},localization:{timeFormatter:formatMarketTime},timeScale:{timeVisible:true,secondsVisible:false,tickMarkFormatter:formatMarketTime},rightPriceScale:{borderVisible:false}});
    const candle=api.addSeries(CandlestickSeries,{upColor:"#067647",downColor:"#b42318",borderVisible:false,wickUpColor:"#067647",wickDownColor:"#b42318",visible:type==="candlestick"||type==="heikin"});
    const barSeries=api.addSeries(BarSeries,{upColor:"#067647",downColor:"#b42318",visible:type==="bar"});
    const line=api.addSeries(LineSeries,{color:"#4338ca",lineWidth:2,visible:type==="line"});
    const area=api.addSeries(AreaSeries,{lineColor:"#4338ca",topColor:"#818cf850",bottomColor:"#818cf805",visible:type==="area"});
    const volume=api.addSeries(HistogramSeries,{priceScaleId:"volume",priceFormat:{type:"volume"},priceLineVisible:false,lastValueVisible:false,visible:indicators.includes("Volume")});volume.priceScale().applyOptions({scaleMargins:{top:.83,bottom:0}});
    const overlays=[['SMA','sma20','#2563eb'],['EMA','ema20','#7c3aed'],['VWAP','vwap','#b45309'],['Bollinger','bollinger_upper','#64748b'],['Bollinger','bollinger_lower','#64748b'],['Supertrend','supertrend','#067647']].filter(([name])=>indicators.includes(name)).map(([name,key,color])=>({name,key,series:api.addSeries(LineSeries,{title:name,color,lineWidth:1,priceLineVisible:false})}));
    candle.priceScale().applyOptions({scaleMargins:{top:.08,bottom:indicators.includes("Volume")?.24:.08}});chart.current=api;price.current=candle;
    update.current=bars=>{const old=api.timeScale().getVisibleRange();let previousOpen=0,previousClose=0;
      const candles=bars.map((bar,i)=>{if(type!=="heikin")return {time:utc(bar.time),open:bar.open,high:bar.high,low:bar.low,close:bar.close};const close=(bar.open+bar.high+bar.low+bar.close)/4,open=i?(previousOpen+previousClose)/2:(bar.open+bar.close)/2;previousOpen=open;previousClose=close;return {time:utc(bar.time),open,close,high:Math.max(bar.high,open,close),low:Math.min(bar.low,open,close)};});
      candle.setData(candles);barSeries.setData(bars.map(bar=>({time:utc(bar.time),open:bar.open,high:bar.high,low:bar.low,close:bar.close})));const values=bars.map(bar=>({time:utc(bar.time),value:bar.close}));line.setData(values);area.setData(values);volume.setData(bars.map(bar=>({time:utc(bar.time),value:bar.volume,color:bar.close>=bar.open?"#06764755":"#b4231855"})));
      overlays.forEach(({key,series})=>series.setData(bars.filter(bar=>(key==='vwap'?bar.vwap:bar.indicators[key])!==null).map(bar=>({time:utc(bar.time),value:key==='vwap'?bar.vwap!:bar.indicators[key]!}))));
      const current=`${data.session_id}:${data.interval}`;if(identity.current!==current){identity.current=current;viewport.current=null;api.timeScale().fitContent();}else if(old)api.timeScale().setVisibleRange(old);else if(viewport.current)api.timeScale().setVisibleRange(viewport.current);else api.timeScale().fitContent();setGeometry(value=>value+1);
    };
    const range=()=>{const value=api.timeScale().getVisibleRange();if(value&&typeof value.from==='number'&&typeof value.to==='number'){viewport.current=value;setVisible({from:value.from,to:value.to});if(!suppress.current && !(appliedRange.current?.from===value.from && appliedRange.current?.to===value.to))callbacks.current.onRange({from:value.from,to:value.to,origin:pane});}setGeometry(value=>value+1);};
    const cursor=(event:{time?:Time;point?:{x:number;y:number}})=>{if(suppress.current||typeof event.time!=="number"||!event.point)return;const value=candle.coordinateToPrice(event.point.y);if(value!==null && !(appliedCrosshair.current?.time===event.time && Math.abs(appliedCrosshair.current.price-value)<.0001))callbacks.current.onCrosshair({time:event.time,price:value,origin:pane});};
    api.timeScale().subscribeVisibleTimeRangeChange(range);api.subscribeCrosshairMove(cursor);const observer=new ResizeObserver(()=>setGeometry(value=>value+1));observer.observe(host.current);
    update.current(data.bars);
    return()=>{viewport.current=api.timeScale().getVisibleRange();observer.disconnect();api.timeScale().unsubscribeVisibleTimeRangeChange(range);api.unsubscribeCrosshairMove(cursor);api.remove();chart.current=null;price.current=null;};
  },[type,indicatorKey,data.session_id,data.interval,pane]);
  useEffect(()=>{update.current(data.bars);},[data.bars]);
  useEffect(()=>{if(!syncRange||syncRange.origin===pane||!chart.current)return;const old=chart.current.timeScale().getVisibleRange();if(old&&Number(old.from)===syncRange.from&&Number(old.to)===syncRange.to)return;appliedRange.current={from:syncRange.from,to:syncRange.to};suppress.current=true;try{chart.current.timeScale().setVisibleRange({from:syncRange.from as UTCTimestamp,to:syncRange.to as UTCTimestamp});}finally{suppress.current=false;}},[syncRange,pane]);
  useEffect(()=>{if(!crosshair||crosshair.origin===pane||!chart.current||!price.current)return;appliedCrosshair.current={time:crosshair.time,price:crosshair.price};suppress.current=true;try{chart.current.setCrosshairPosition(crosshair.price,crosshair.time as UTCTimestamp,price.current);}finally{suppress.current=false;}},[crosshair,pane]);
  const active=drawings.filter(drawing=>drawing.pane===pane&&drawing.session_id===data.session_id);
  const plotted=data.bars.filter(bar=>!visible||(utc(bar.time)>=visible.from&&utc(bar.time)<=visible.to));
  return <div className="professional-chart" data-geometry={geometry}><div className="professional-chart-canvas"><div ref={host}/><svg className="chart-drawings" aria-label={`User drawings for chart ${pane+1}`}>
    {active.map(drawing=>{const api=chart.current,series=price.current;if(!api||!series)return null;const x1=api.timeScale().timeToCoordinate(utc(drawing.time1)),y1=series.priceToCoordinate(drawing.price1);if(x1===null||y1===null)return null;const x2=drawing.time2?api.timeScale().timeToCoordinate(utc(drawing.time2)):x1,y2=drawing.price2?series.priceToCoordinate(drawing.price2):y1;const width=host.current?.clientWidth||0,height=340;
      if(drawing.kind==='horizontal')return <line key={drawing.id} x1={0} x2={width} y1={y1} y2={y1} stroke="#b45309" strokeDasharray="5 3"/>;
      if(drawing.kind==='vertical')return <line key={drawing.id} x1={x1} x2={x1} y1={0} y2={height} stroke="#b45309" strokeDasharray="5 3"/>;
      if(drawing.kind==='text')return <text key={drawing.id} x={x1} y={y1} fill="#172033" fontSize="12">{drawing.text}</text>;
      if(x2===null||y2===null)return null;
      if(drawing.kind==='rectangle')return <rect key={drawing.id} x={Math.min(x1,x2)} y={Math.min(y1,y2)} width={Math.abs(x2-x1)} height={Math.abs(y2-y1)} fill="#818cf822" stroke="#4338ca"/>;
      if(drawing.kind==='fibonacci')return <g key={drawing.id}>{[0,.236,.382,.5,.618,1].map(level=><g key={level}><line x1={Math.min(x1,x2)} x2={Math.max(x1,x2)} y1={y1+(y2-y1)*level} y2={y1+(y2-y1)*level} stroke="#7c3aed"/><text x={Math.max(x1,x2)+3} y={y1+(y2-y1)*level} fontSize="9">{level}</text></g>)}</g>;
      return <g key={drawing.id}><line x1={x1} x2={x2} y1={y1} y2={y2} stroke="#4338ca"/>{drawing.kind==='measure'&&<text x={(x1+x2)/2} y={(y1+y2)/2-8} fill="#172033" fontSize="11">{((drawing.price2||drawing.price1)-drawing.price1).toFixed(2)} points</text>}</g>;
    })}</svg></div>
    {type==='heikin'&&<p className="chart-disclosure">Heikin-Ashi prices are derived visual values, not executable quotes.</p>}
    {indicators.includes('RSI')&&<Oscillator bars={plotted} keys={['rsi14']} label="RSI14"/>}{indicators.includes('MACD')&&<Oscillator bars={plotted} keys={['macd','macd_signal','macd_histogram']} label="MACD 12/26/9"/>}{indicators.includes('ATR')&&<Oscillator bars={plotted} keys={['atr14']} label="ATR14"/>}
    <details><summary>Accessible candle &amp; indicator data</summary><div className="workspace-table"><table><thead><tr><th>Time</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th><th>RSI</th><th>ATR</th></tr></thead><tbody>{plotted.map(bar=><tr key={bar.time}><th>{new Date(bar.time).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata'})}</th>{[bar.open,bar.high,bar.low,bar.close,bar.volume,bar.indicators.rsi14,bar.indicators.atr14].map((value,i)=><td key={i}>{value===null?'Warming up':Number(value).toFixed(i===4?0:2)}</td>)}</tr>)}</tbody></table></div></details>
  </div>;
}
