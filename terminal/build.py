"""Render the self-contained terminal HTML from bundle.json.

Writes terminal/pak_terminal.html — a single file with the data embedded, no
external requests (works offline, CSP-safe for publishing as an Artifact).
"""
import json
from pathlib import Path

from pakterm import config

HERE = Path(__file__).resolve().parent


def build():
    bundle_path = HERE / "bundle.json"
    if not bundle_path.exists():
        from terminal import bundle as B
        B.main()
    data = bundle_path.read_text(encoding="utf-8")
    html = TEMPLATE.replace("/*__BUNDLE__*/", data)
    out = HERE / "pak_terminal.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size/1e3:.0f} KB)")
    return out


TEMPLATE = r"""<meta charset="utf-8">
<title>Pak Terminal</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{
  --ground:#f4f6f8; --panel:#ffffff; --panel2:#eef1f5; --border:#d7dee6;
  --ink:#0f1720; --muted:#5b6876; --faint:#8894a3;
  --accent:#c8791a; --accent-soft:#f0d6b0;
  --up:#1a7f37; --down:#c9302c; --cyan:#0e7c8c; --violet:#6b46c1;
  --grid:#e2e8ef; --shadow:0 1px 3px rgba(16,24,32,.08),0 8px 24px rgba(16,24,32,.06);
  --mono:"Cascadia Code","SF Mono","JetBrains Mono",Consolas,ui-monospace,monospace;
  --sans:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;
}
:root:not([data-theme="light"]){ }
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ground:#0a0e14; --panel:#111823; --panel2:#0d141d; --border:#1f2a37;
  --ink:#e6edf3; --muted:#8b97a6; --faint:#5d6a79;
  --accent:#f5a623; --accent-soft:#3a2c14;
  --up:#3fb950; --down:#f85149; --cyan:#4cc4d6; --violet:#a371f7;
  --grid:#182230; --shadow:0 1px 0 rgba(0,0,0,.4),0 12px 32px rgba(0,0,0,.35);
}}
:root[data-theme="dark"]{
  --ground:#0a0e14; --panel:#111823; --panel2:#0d141d; --border:#1f2a37;
  --ink:#e6edf3; --muted:#8b97a6; --faint:#5d6a79;
  --accent:#f5a623; --accent-soft:#3a2c14;
  --up:#3fb950; --down:#f85149; --cyan:#4cc4d6; --violet:#a371f7;
  --grid:#182230; --shadow:0 1px 0 rgba(0,0,0,.4),0 12px 32px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--ground);color:var(--ink);font-family:var(--sans);
  font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums}
a{color:var(--accent)}
h1,h2,h3{text-wrap:balance;margin:0}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint)}
.up{color:var(--up)} .down{color:var(--down)} .accent{color:var(--accent)}
.muted{color:var(--muted)}

/* header */
header{position:sticky;top:0;z-index:20;background:var(--panel);
  border-bottom:1px solid var(--border)}
.hbar{display:flex;align-items:center;gap:14px;padding:10px 18px}
.brand{font-family:var(--mono);font-weight:700;letter-spacing:.08em;font-size:15px}
.brand b{color:var(--accent)}
.dot{width:7px;height:7px;border-radius:50%;display:inline-block;background:var(--up);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--up) 22%,transparent)}
.chip{font-family:var(--mono);font-size:11px;padding:3px 8px;border:1px solid var(--border);
  border-radius:999px;color:var(--muted);white-space:nowrap}
.spacer{flex:1}
.themebtn{cursor:pointer;background:var(--panel2);border:1px solid var(--border);
  color:var(--muted);border-radius:8px;padding:5px 9px;font-family:var(--mono);font-size:12px}
/* ticker strip */
.ticker{display:flex;gap:0;overflow:hidden;border-top:1px solid var(--border);
  background:var(--panel2)}
.ticker .track{display:flex;gap:26px;padding:6px 18px;white-space:nowrap;
  animation:scroll 42s linear infinite}
@keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.ticker .track{animation:none}}
.tk{font-family:var(--mono);font-size:12px;color:var(--muted)}
.tk b{color:var(--ink);font-weight:600}
/* tabs */
nav.tabs{display:flex;gap:2px;padding:0 12px;overflow-x:auto;background:var(--panel);
  border-bottom:1px solid var(--border)}
nav.tabs button{background:none;border:none;border-bottom:2px solid transparent;
  color:var(--muted);font-family:var(--mono);font-size:12.5px;letter-spacing:.04em;
  text-transform:uppercase;padding:11px 13px;cursor:pointer;white-space:nowrap}
nav.tabs button:hover{color:var(--ink)}
nav.tabs button[aria-selected="true"]{color:var(--accent);border-bottom-color:var(--accent)}
nav.tabs button:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}

main{max-width:1240px;margin:0 auto;padding:20px 18px 80px}
.panel{display:none;animation:fade .25s ease}
.panel.active{display:block}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.grid{display:grid;gap:16px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:16px 18px;box-shadow:var(--shadow)}
.card h3{font-size:13px;font-family:var(--mono);letter-spacing:.05em;text-transform:uppercase;
  color:var(--muted);font-weight:600;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.sect-title{font-size:22px;font-weight:650;margin-bottom:4px}
.lead{color:var(--muted);max-width:70ch;margin-bottom:18px}
.tag{font-family:var(--mono);font-size:10.5px;padding:2px 7px;border-radius:5px;
  border:1px solid var(--border);color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.tag.ok{color:var(--up);border-color:color-mix(in srgb,var(--up) 40%,var(--border))}
.tag.info{color:var(--cyan);border-color:color-mix(in srgb,var(--cyan) 40%,var(--border))}
.tag.warn{color:var(--accent);border-color:color-mix(in srgb,var(--accent) 40%,var(--border))}

table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:right;padding:6px 9px;border-bottom:1px solid var(--grid);white-space:nowrap}
th{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--faint);font-weight:600;position:sticky;top:0;background:var(--panel);cursor:pointer}
th:first-child,td:first-child{text-align:left}
tbody tr:hover{background:var(--panel2)}
.tablewrap{overflow-x:auto;max-height:460px;overflow-y:auto}
.bar{height:8px;border-radius:4px;background:var(--panel2);position:relative;overflow:hidden;min-width:60px}
.bar>span{position:absolute;top:0;bottom:0;border-radius:4px}
.kpi{display:flex;flex-direction:column;gap:2px}
.kpi .v{font-family:var(--mono);font-size:26px;font-weight:600;line-height:1.1}
.kpi .l{font-size:11px;color:var(--faint);font-family:var(--mono);text-transform:uppercase;letter-spacing:.06em}
.badge{display:inline-flex;align-items:center;gap:9px;font-family:var(--mono);font-weight:700;
  font-size:20px;letter-spacing:.06em;padding:10px 16px;border-radius:10px}
.badge.on{color:var(--up);background:color-mix(in srgb,var(--up) 12%,transparent);
  border:1px solid color-mix(in srgb,var(--up) 35%,transparent)}
.badge.off{color:var(--down);background:color-mix(in srgb,var(--down) 12%,transparent);
  border:1px solid color-mix(in srgb,var(--down) 35%,transparent)}
.gauge{display:flex;gap:5px}
.gauge i{width:26px;height:10px;border-radius:3px;background:var(--panel2)}
.gauge i.f{background:var(--up)}
.chipwrap{display:flex;flex-wrap:wrap;gap:7px}
.mchip{font-family:var(--mono);font-size:11.5px;padding:4px 9px;border-radius:7px;
  border:1px solid var(--border);background:var(--panel2)}
svg{display:block;max-width:100%}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:11.5px;color:var(--muted);font-family:var(--mono)}
.legend i{width:11px;height:11px;border-radius:3px;display:inline-block;margin-right:5px;vertical-align:-1px}
.note{font-size:12px;color:var(--faint);border-left:2px solid var(--accent);padding:2px 0 2px 11px;margin-top:12px}
.chain{border:1px solid var(--border);border-radius:10px;padding:12px 14px;background:var(--panel2)}
.chain .trig{font-weight:600;margin-bottom:5px}
.chain .mech{font-size:12.5px;color:var(--muted);margin-bottom:9px}
.pill{font-family:var(--mono);font-size:11px;padding:2px 8px;border-radius:999px;margin:2px 4px 2px 0;display:inline-block}
.detail{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;font-size:12.5px}
.newsitem{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:start;
  padding:9px 0;border-bottom:1px solid var(--grid)}
.tier{font-family:var(--mono);font-size:10px;font-weight:700;padding:2px 6px;border-radius:5px;white-space:nowrap}
.cols2{grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.cols3{grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.toggle{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}
.toggle button{background:var(--panel);border:none;color:var(--muted);font-family:var(--mono);
  font-size:11.5px;padding:5px 11px;cursor:pointer}
.toggle button[aria-pressed="true"]{background:var(--accent);color:#111}
.hint{cursor:help;border-bottom:1px dotted var(--faint)}
</style>

<header>
  <div class="hbar">
    <span class="brand">PAK<b>·</b>TERMINAL</span>
    <span id="regimeChip" class="chip"></span>
    <span class="chip" id="asOf"></span>
    <span class="spacer"></span>
    <span class="chip" id="coverage"></span>
    <button class="themebtn" id="themeBtn" title="Toggle theme">◐ theme</button>
  </div>
  <div class="ticker"><div class="track" id="tickTrack"></div></div>
</header>
<nav class="tabs" id="tabs"></nav>
<main id="main"></main>

<script id="data" type="application/json">/*__BUNDLE__*/</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const $ = (t,a={},...k)=>{const e=document.createElement(t);
  for(const[p,v]of Object.entries(a)){if(p==='class')e.className=v;else if(p==='html')e.innerHTML=v;
  else if(p.startsWith('on'))e.addEventListener(p.slice(2),v);else e.setAttribute(p,v);}
  for(const c of k.flat())e.append(c?.nodeType?c:document.createTextNode(c??''));return e;};
const pct=(x,d=1)=>x==null||isNaN(x)?'—':(x>=0?'+':'')+(x*100).toFixed(d)+'%';
const fmt=(x,d=2)=>x==null||isNaN(x)?'—':(+x).toFixed(d);
const cls=x=>x==null||isNaN(x)?'':x>0?'up':x<0?'down':'';
const heat=x=>{if(x==null||isNaN(x))return 'transparent';const a=Math.min(1,Math.abs(x)/0.5);
  const c=x>0?'26,127,55':'201,48,44';return `rgba(${c},${(0.12+a*0.55).toFixed(2)})`;};

/* ---------- SVG helpers ---------- */
function lineChart(series,{w=640,h=190,pad=28,fmt:f=(v=>v),colors=['var(--accent)']}={}){
  const all=series.flatMap(s=>s.y).filter(v=>v!=null&&!isNaN(v));
  if(!all.length)return $('div',{class:'muted'},'no data');
  const lo=Math.min(...all),hi=Math.max(...all),n=Math.max(...series.map(s=>s.x.length));
  const X=i=>pad+ (n<2?0:i/(n-1))*(w-pad*1.4);
  const Y=v=>h-pad-((v-lo)/((hi-lo)||1))*(h-pad*1.7);
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
  svg.setAttribute('width','100%');
  for(let g=0;g<=3;g++){const y=pad+g*(h-pad*1.7)/3;
    const l=document.createElementNS(ns,'line');l.setAttribute('x1',pad);l.setAttribute('x2',w-pad*0.4);
    l.setAttribute('y1',y);l.setAttribute('y2',y);l.setAttribute('stroke','var(--grid)');svg.append(l);
    const t=document.createElementNS(ns,'text');t.setAttribute('x',4);t.setAttribute('y',y+3);
    t.setAttribute('fill','var(--faint)');t.setAttribute('font-size','9');t.setAttribute('font-family','var(--mono)');
    t.textContent=f(hi-(hi-lo)*g/3);svg.append(t);}
  series.forEach((s,si)=>{let d='';s.y.forEach((v,i)=>{if(v==null||isNaN(v))return;
    d+=(d?'L':'M')+X(i).toFixed(1)+' '+Y(v).toFixed(1)+' ';});
    const p=document.createElementNS(ns,'path');p.setAttribute('d',d);p.setAttribute('fill','none');
    p.setAttribute('stroke',colors[si%colors.length]);p.setAttribute('stroke-width','1.8');
    p.setAttribute('stroke-linejoin','round');svg.append(p);
    // endpoint dot
    for(let i=s.y.length-1;i>=0;i--){if(s.y[i]!=null&&!isNaN(s.y[i])){
      const c=document.createElementNS(ns,'circle');c.setAttribute('cx',X(i));c.setAttribute('cy',Y(s.y[i]));
      c.setAttribute('r','2.6');c.setAttribute('fill',colors[si%colors.length]);svg.append(c);break;}}});
  return svg;
}
function barRow(v,max,color){const w=Math.min(100,Math.abs(v)/max*100);
  const b=$('div',{class:'bar'});b.append($('span',{style:`width:${w}%;background:${color};${v<0?'right:50%':'left:50%'}`}));
  return b;}

/* ---------- panels ---------- */
const PANELS={};

PANELS.Regime=()=>{
  const r=D.regime, t=r.timing, m=r.macro;
  const wrap=$('div',{});
  wrap.append($('h2',{class:'sect-title'},'Market Regime'),
    $('p',{class:'lead'},'The one verified, out-of-sample, cost-surviving edge in this project: trend-following the liquid PSX index. Everything else on this terminal is context or curated prior — this is the signal.'));
  const g=$('div',{class:'grid cols2'});
  // signal card
  const sc=$('div',{class:'card'});
  sc.append($('h3',{},'Today’s signal ',$('span',{class:'tag ok'},'verified edge')));
  sc.append($('div',{class:'badge '+(t.signal==='RISK-ON'?'on':'off')},
    $('span',{class:'dot',style:t.signal==='RISK-ON'?'':'background:var(--down);box-shadow:0 0 0 3px color-mix(in srgb,var(--down) 22%,transparent)'}),t.signal));
  const gauge=$('div',{class:'gauge',style:'margin:14px 0 6px'});
  for(let i=0;i<4;i++)gauge.append($('i',{class:i<Math.round(t.exposure*4)?'f':''}));
  sc.append(gauge,$('div',{class:'mono muted',style:'font-size:12px'},`exposure ${(t.exposure*100).toFixed(0)}% · as of ${t.as_of}`));
  const fl=$('div',{class:'chipwrap',style:'margin-top:12px'});
  for(const[k,v]of Object.entries(t.filters))fl.append($('span',{class:'mchip',style:v?'color:var(--up)':'color:var(--down)'},(v?'▲ ':'▼ ')+k.replace('above_','> ')));
  sc.append(fl);
  sc.append($('div',{class:'note'},'RISK-ON = be invested; RISK-OFF = move to cash/T-bills. Trend-following raises Sharpe ~1.15→~1.7 and roughly halves max drawdown out-of-sample.'));
  g.append(sc);
  // verify table
  const vc=$('div',{class:'card'});
  vc.append($('h3',{},'Edge, reproduced live'));
  const tb=$('table');tb.append($('thead',{},$('tr',{},...['Strategy','CAGR','Sharpe','Max DD'].map(h=>$('th',{},h)))));
  const bd=$('tbody');
  r.verify.forEach(row=>{const best=row.strategy==='trend_ensemble';
    bd.append($('tr',{style:best?'background:var(--accent-soft)':''},
      $('td',{},row.strategy.replace('_',' ')),
      $('td',{class:'num'},pct(row.CAGR,1)),
      $('td',{class:'num',style:best?'color:var(--accent);font-weight:600':''},fmt(row.Sharpe,2)),
      $('td',{class:'num '+cls(row.maxDD)},pct(row.maxDD,1))));});
  tb.append(bd);vc.append($('div',{class:'tablewrap'},tb));
  vc.append($('div',{class:'note'},'Buy&hold vs. trend variants on the equal-weight liquid index (net of 0.3%/switch, cash @12% PKR). Time-series momentum is the most replicated anomaly in finance; it shows up cleanly in PSX too.'));
  g.append(vc);
  wrap.append(g);
  // macro overlay
  const mc=$('div',{class:'card',style:'margin-top:16px'});
  mc.append($('h3',{},'Macro overlay ',$('span',{class:'tag info'},'context only — not a predictor')));
  if(m.score==null){mc.append($('div',{class:'muted'},'macro not seeded'));}
  else{
    mc.append($('div',{class:'mono',style:'font-size:15px;margin-bottom:10px'},`tilt: `,
      $('b',{class:m.tilt==='supportive'?'up':m.tilt==='restrictive'?'down':'accent'},m.tilt.toUpperCase()),
      `  (score ${m.score>=0?'+':''}${m.score})`));
    const fw=$('div',{class:'chipwrap'});
    for(const[k,v]of Object.entries(m.factors)){const s=v.signal;
      fw.append($('span',{class:'mchip',style:s>0?'color:var(--up)':s<0?'color:var(--down)':''},
        `${k}: ${v.value} ${s>0?'▲':s<0?'▼':'▬'}`));}
    mc.append(fw);
    mc.append($('div',{class:'note'},'A few economically-signed factors (policy-rate direction, PKR trend, reserves, inflation). With ~85 monthly points, fitting a predictor would overfit — this only annotates the primary trend signal.'));
  }
  wrap.append(mc);
  // index curve
  const ic=$('div',{class:'card',style:'margin-top:16px'});
  ic.append($('h3',{},'Liquid-index equity curve (log-cum, daily)'));
  ic.append(lineChart([{x:D.index.level_daily.x,y:D.index.level_daily.y}],{fmt:v=>v.toFixed(1)+'x',colors:['var(--accent)']}));
  wrap.append(ic);
  // FIPI/LIPI flows (smart-money positioning)
  const flw=D.flows;
  if(flw&&flw.available){const fc=$('div',{class:'card',style:'margin-top:16px'});
    fc.append($('h3',{},'Foreign vs local flows (FIPI/LIPI) ',$('span',{class:'tag info'},'NCCPL · recent')));
    fc.append($('div',{class:'mono',style:'margin-bottom:8px'},'Foreign: ',
      $('b',{class:flw.foreign_stance.includes('BUYER')?'up':'down'},flw.foreign_stance),
      ` · last ${flw.fipi_last_usd_m>=0?'+':''}${flw.fipi_last_usd_m}M · 5d ${flw.fipi_5d_usd_m>=0?'+':''}${flw.fipi_5d_usd_m}M · 2mo cum ${flw.fipi_cum_usd_m>=0?'+':''}${flw.fipi_cum_usd_m}M`));
    fc.append(lineChart([{x:flw.series.days,y:flw.series.fipi_m},{x:flw.series.days,y:flw.series.lipi_m}],
      {fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'M',colors:['var(--down)','var(--cyan)'],h:150}));
    fc.append($('div',{class:'legend',style:'margin-top:6px'},
      $('span',{},$('i',{style:'background:var(--down)'}),'FIPI (foreign net, $M)'),
      $('span',{},$('i',{style:'background:var(--cyan)'}),'LIPI (local net, $M)')));
    // client-type bars this week
    const cw=flw.client_week||{};const ent=Object.entries(cw).sort((a,b)=>b[1]-a[1]);
    const maxc=Math.max(...ent.map(([,v])=>Math.abs(v)),1);
    const cb=$('div',{style:'margin-top:12px'});
    ent.forEach(([k,v])=>cb.append($('div',{style:'display:grid;grid-template-columns:170px 1fr 66px;gap:8px;align-items:center;margin:2px 0'},
      $('div',{class:'mono muted',style:'font-size:11px'},k),
      barRow(v,maxc,v>0?'var(--up)':'var(--down)'),
      $('div',{class:'num '+cls(v),style:'font-size:11px'},(v>=0?'+':'')+(v/1e6).toFixed(1)+'M'))));
    fc.append(cb);
    fc.append($('div',{class:'note'},'Market-level net buy/sell by investor category (this week). Full 7y history for backtesting needs the NCCPL bulk portal — this is the current positioning signal, honestly scoped.'));
    wrap.append(fc);}
  return wrap;
};

PANELS.Sectors=()=>{
  const wrap=$('div',{});
  wrap.append($('h2',{class:'sect-title'},'Sectors'),
    $('p',{class:'lead'},`${D.sectors.perf.length} PSX equity sectors, equal-weight baskets of the liquid universe. Sector codes verified against constituents. Click a column header to sort.`));
  const maxv=Math.max(...D.sectors.perf.map(p=>Math.abs(p.r_12m||0)))||0.5;
  const cols=[['sector','Sector'],['r_1m','1M'],['r_3m','3M'],['r_12m','12M'],['vol_ann','Vol']];
  let sortk='r_12m',asc=false;
  const card=$('div',{class:'card'});
  const tb=$('table');const th=$('thead');const hr=$('tr');
  cols.forEach(([k,l])=>hr.append($('th',{onclick:()=>{asc=(sortk===k)?!asc:false;sortk=k;render();}},l)));
  hr.append($('th',{},'12M bar'));th.append(hr);tb.append(th);const body=$('tbody');tb.append(body);
  function render(){body.innerHTML='';
    const rows=[...D.sectors.perf].sort((a,b)=>{const x=a[sortk],y=b[sortk];
      if(typeof x==='string')return asc?x.localeCompare(y):y.localeCompare(x);
      return asc?(x||-9)-(y||-9):(y||-9)-(x||-9);});
    rows.forEach(p=>{body.append($('tr',{},
      $('td',{},p.sector),
      $('td',{class:'num '+cls(p.r_1m)},pct(p.r_1m)),
      $('td',{class:'num '+cls(p.r_3m)},pct(p.r_3m)),
      $('td',{class:'num '+cls(p.r_12m)},pct(p.r_12m)),
      $('td',{class:'num muted'},p.vol_ann==null?'—':(p.vol_ann*100).toFixed(0)+'%'),
      $('td',{},barRow(p.r_12m||0,maxv,(p.r_12m||0)>0?'var(--up)':'var(--down)'))));});}
  render();card.append($('div',{class:'tablewrap'},tb));wrap.append(card);
  // cumulative chart of top sectors
  const cc=$('div',{class:'card',style:'margin-top:16px'});
  cc.append($('h3',{},'Cumulative sector index — leaders (monthly)'));
  const names=Object.keys(D.sectors.cum).slice(0,6);
  const palette=['var(--accent)','var(--cyan)','var(--up)','var(--violet)','var(--down)','#8894a3'];
  cc.append(lineChart(names.map(n=>({x:D.sectors.cum[n].x,y:D.sectors.cum[n].y})),{fmt:v=>v.toFixed(1)+'x',colors:palette,h:220}));
  const lg=$('div',{class:'legend',style:'margin-top:10px'});
  names.forEach((n,i)=>lg.append($('span',{},$('i',{style:`background:${palette[i]}`}),n)));
  cc.append(lg);wrap.append(cc);
  return wrap;
};

PANELS.Interconnections=()=>{
  const wrap=$('div',{});
  wrap.append($('h2',{class:'sect-title'},'Sector Interconnections'),
    $('p',{class:'lead'},'A curated supply-chain / macro-sensitivity map — inputs, outputs, and how each sector reacts to rates, the rupee, oil, and global shocks. This is an expert PRIOR (economic logic + cited facts), not a fitted model. Hover a node for detail.'));
  const g=D.graph;
  if(!g.sectors.length){wrap.append($('div',{class:'card muted'},'sector graph not seeded'));return wrap;}
  // network
  const ns='http://www.w3.org/2000/svg',W=900,H=560,cx=W/2,cy=H/2,R=Math.min(W,H)/2-70;
  const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('width','100%');
  const nodes=g.sectors.map((s,i)=>{const a=-Math.PI/2+i/g.sectors.length*2*Math.PI;
    return{...s,x:cx+R*Math.cos(a),y:cy+R*Math.sin(a),a};});
  const byname=Object.fromEntries(nodes.map(n=>[n.name,n]));
  const perf=Object.fromEntries(D.sectors.perf.map(p=>[p.sector,p.r_12m]));
  // edges from downstream links
  nodes.forEach(n=>{(n.downstream||[]).forEach(dn=>{const t=byname[dn];if(!t)return;
    const p=document.createElementNS(ns,'path');
    p.setAttribute('d',`M${n.x.toFixed(1)} ${n.y.toFixed(1)} Q ${cx} ${cy} ${t.x.toFixed(1)} ${t.y.toFixed(1)}`);
    p.setAttribute('fill','none');p.setAttribute('stroke','var(--grid)');p.setAttribute('stroke-width','1');
    p.setAttribute('opacity','.8');svg.append(p);});});
  const tip=$('div',{class:'card',style:'position:absolute;pointer-events:none;opacity:0;max-width:300px;z-index:5;transition:opacity .1s;font-size:12px'});
  nodes.forEach(n=>{const r12=perf[n.name];
    const c=document.createElementNS(ns,'circle');c.setAttribute('cx',n.x);c.setAttribute('cy',n.y);
    c.setAttribute('r',10);c.setAttribute('fill',r12==null?'var(--panel2)':heat(r12));
    c.setAttribute('stroke','var(--accent)');c.setAttribute('stroke-width','1.2');c.style.cursor='pointer';
    c.addEventListener('mousemove',e=>{tip.style.opacity=1;tip.style.left=(e.pageX+12)+'px';tip.style.top=(e.pageY+12)+'px';
      const ms=n.macro_sensitivity||{};
      tip.innerHTML=`<b>${n.name}</b> <span class="mono muted">${(n.key_tickers||[]).slice(0,4).join(' ')}</span><br>
        <span class="mono" style="font-size:11px">12M ${pct(r12)}</span><br>
        <div class="mono" style="font-size:11px;margin-top:5px">rate ${sgn(ms.policy_rate)} · pkr↓ ${sgn(ms.pkr_depreciation)} · oil ${sgn(ms.oil)} · remit ${sgn(ms.remittances)}</div>
        <div style="font-size:11px;margin-top:5px;color:var(--muted)">in: ${(n.inputs||[]).slice(0,3).join(', ')||'—'}</div>`;});
    c.addEventListener('mouseleave',()=>tip.style.opacity=0);
    svg.append(c);
    const tx=document.createElementNS(ns,'text');const out=n.x>cx;
    tx.setAttribute('x',n.x+(out?15:-15));tx.setAttribute('y',n.y+3);tx.setAttribute('text-anchor',out?'start':'end');
    tx.setAttribute('fill','var(--muted)');tx.setAttribute('font-size','10');tx.setAttribute('font-family','var(--mono)');
    tx.textContent=n.name.length>20?n.name.slice(0,19)+'…':n.name;svg.append(tx);});
  const netcard=$('div',{class:'card'});
  netcard.append($('h3',{},'Supply-chain network ',$('span',{class:'tag warn'},'curated prior')),svg,
    $('div',{class:'legend',style:'margin-top:6px'},
      $('span',{},$('i',{style:'background:'+heat(0.3)}),'12M up'),
      $('span',{},$('i',{style:'background:'+heat(-0.3)}),'12M down'),
      $('span',{},'edges = downstream (sells-to) links')));
  wrap.append(netcard,tip);
  function sgn(v){return v==null?'·':v>0?`+${v}`:`${v}`;}
  // causal chains
  const cch=$('div',{class:'card',style:'margin-top:16px'});
  cch.append($('h3',{},'Causal playbooks ',$('span',{class:'tag'},`${g.causal_chains.length} scenarios`)));
  const cg=$('div',{class:'grid cols2'});
  g.causal_chains.forEach(ch=>{const el=$('div',{class:'chain'});
    el.append($('div',{class:'trig'},'▶ '+ch.trigger),$('div',{class:'mech'},ch.mechanism));
    const pl=$('div',{});(ch.affected||[]).forEach(a=>{const up=a.sign>0;
      pl.append($('span',{class:'pill',style:`background:${up?'color-mix(in srgb,var(--up) 16%,transparent)':'color-mix(in srgb,var(--down) 16%,transparent)'};color:${up?'var(--up)':'var(--down)'}`},
        (up?'▲ ':'▼ ')+a.sector));});
    el.append(pl);
    if(ch.evidence)el.append($('div',{class:'mono',style:'font-size:10.5px;color:var(--faint);margin-top:7px'},ch.evidence.slice(0,90)));
    cg.append(el);});
  cch.append(cg);wrap.append(cch);
  return wrap;
};

PANELS.Macro=()=>{
  const wrap=$('div',{});
  wrap.append($('h2',{class:'sect-title'},'Macro & Global'),
    $('p',{class:'lead'},'SBP policy, inflation, external accounts, the rupee and oil — monthly, 2019→present. Every value is sourced or flagged interpolated (see provenance). Live fetch is best-effort; sources are bot-walled to plain requests, so seeds are committed and refreshed opportunistically.'));
  const S=D.macro.series;
  const specs=[['policy_rate','SBP policy rate','%',v=>v.toFixed(0),'var(--accent)'],
    ['cpi_yoy','CPI inflation (YoY)','%',v=>v.toFixed(0),'var(--down)'],
    ['pkr_usd','PKR / USD','',v=>v.toFixed(0),'var(--violet)'],
    ['fx_reserves_sbp_bn','SBP FX reserves','$bn',v=>v.toFixed(0),'var(--up)'],
    ['remittances_bn','Remittances (monthly)','$bn',v=>v.toFixed(1),'var(--cyan)'],
    ['brent_usd','Brent crude','$',v=>v.toFixed(0),'#c8791a']];
  const g=$('div',{class:'grid cols2'});
  specs.forEach(([k,l,u,f,c])=>{if(!S[k])return;const card=$('div',{class:'card'});
    const last=S[k].y[S[k].y.length-1];
    card.append($('h3',{},l,$('span',{class:'spacer',style:'flex:1'}),$('span',{class:'mono accent',style:'font-size:15px'},f(last)+' '+u)));
    card.append(lineChart([{x:S[k].x,y:S[k].y}],{fmt:f,colors:[c],h:150}));g.append(card);});
  wrap.append(g);
  wrap.append($('div',{class:'note',style:'margin-top:14px'},'Landmarks reproduce reality: CPI peak ~38% (May-2023), PKR 152→306, reserves trough ~$3.7bn (Jan-2023), Brent $18 (Apr-2020)→$118 (Jun-2022).'));
  return wrap;
};

PANELS.Correlations=()=>{
  const wrap=$('div',{});
  wrap.append($('h2',{class:'sect-title'},'Correlations & Structure'),
    $('p',{class:'lead'},'Real correlations with sample size and t-stats — nothing fitted. With ~85 months, many pairs are noise; |t|<2 is flagged not-significant. We show the curated prior beside the market-adjusted data so you see where the story holds and where it breaks.'));
  // cross-sector heatmap
  const cs=D.sectors.corr;const labels=cs.labels;const N=labels.length;
  const cell=Math.max(9,Math.min(20,Math.floor(760/N)));const sz=N*cell+150;
  const ns='http://www.w3.org/2000/svg';const svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox',`0 0 ${sz} ${N*cell+150}`);svg.setAttribute('width','100%');
  for(let i=0;i<N;i++)for(let j=0;j<N;j++){const v=cs.matrix[i][j];
    const r=document.createElementNS(ns,'rect');r.setAttribute('x',150+j*cell);r.setAttribute('y',10+i*cell);
    r.setAttribute('width',cell-1);r.setAttribute('height',cell-1);r.setAttribute('fill',v==null?'transparent':heat(v));
    const ttl=document.createElementNS(ns,'title');ttl.textContent=`${labels[i]} × ${labels[j]}: ${v}`;r.append(ttl);svg.append(r);}
  labels.forEach((l,i)=>{const t=document.createElementNS(ns,'text');t.setAttribute('x',145);t.setAttribute('y',10+i*cell+cell*0.75);
    t.setAttribute('text-anchor','end');t.setAttribute('font-size',Math.min(10,cell-1));t.setAttribute('font-family','var(--mono)');
    t.setAttribute('fill','var(--muted)');t.textContent=l.length>22?l.slice(0,21)+'…':l;svg.append(t);});
  const hc=$('div',{class:'card'});hc.append($('h3',{},'Sector × sector monthly-return correlation'),
    $('div',{style:'overflow-x:auto'},svg),
    $('div',{class:'legend',style:'margin-top:8px'},$('span',{},$('i',{style:'background:'+heat(0.4)}),'+ correlated'),$('span',{},$('i',{style:'background:'+heat(-0.4)}),'– inverse')));
  wrap.append(hc);
  // prior vs empirical
  const pve=D.connections.prior_vs_empirical, ag=D.connections.agreement;
  const pc=$('div',{class:'card',style:'margin-top:16px'});
  pc.append($('h3',{},'Curated prior vs. market-adjusted data'));
  if(ag&&ag.all&&ag.all.rate!=null)pc.append($('div',{class:'mono',style:'margin-bottom:10px'},
    `sign agreement: `,$('b',{class:'accent'},(ag.all.rate*100).toFixed(0)+'%'),` of ${ag.all.n} priors`,
    ag.sig&&ag.sig.rate!=null?` · ${ (ag.sig.rate*100).toFixed(0)}% of the ${ag.sig.n} significant (|t|≥2)`:''));
  const tb=$('table');tb.append($('thead',{},$('tr',{},...['Sector','Factor','Prior','Data r','t','Match'].map(h=>$('th',{},h)))));
  const bd=$('tbody');
  [...pve].sort((a,b)=>Math.abs(b.t)-Math.abs(a.t)).forEach(row=>{
    bd.append($('tr',{},$('td',{},row.sector),$('td',{class:'mono muted'},row.factor.replace('_',' ')),
      $('td',{class:'num '+cls(row.prior)},row.prior>0?'+'+row.prior:row.prior),
      $('td',{class:'num '+cls(row.empirical_corr)},fmt(row.empirical_corr,2)),
      $('td',{class:'num',style:Math.abs(row.t)>=2?'color:var(--ink)':'color:var(--faint)'},fmt(row.t,1)),
      $('td',{},row.agrees==null?$('span',{class:'muted'},'—'):$('span',{class:row.agrees?'up':'down'},row.agrees?'✓':'✗'))));});
  tb.append(bd);pc.append($('div',{class:'tablewrap'},tb));
  pc.append($('div',{class:'note'},'Market-adjusted = sector return minus market return, isolating cross-sectional tilts. In crises everything falls together, so raw correlations hide the exporter/importer split that the priors describe.'));
  wrap.append(pc);
  // sector x macro top
  const sm=D.connections.sector_macro_corr_rel||[];
  if(sm.length){const smc=$('div',{class:'card',style:'margin-top:16px'});
    smc.append($('h3',{},'Strongest sector × macro links (market-adjusted)'));
    const tb2=$('table');tb2.append($('thead',{},$('tr',{},...['Sector','Macro shock','corr','t','sig'].map(h=>$('th',{},h)))));
    const b2=$('tbody');sm.slice(0,18).forEach(r=>b2.append($('tr',{},$('td',{},r.sector),
      $('td',{class:'mono muted'},r.factor),$('td',{class:'num '+cls(r.corr)},fmt(r.corr,2)),
      $('td',{class:'num'},fmt(r.t,1)),$('td',{},r.sig?$('span',{class:'accent'},'●'):$('span',{class:'muted'},'○')))));
    tb2.append(b2);smc.append($('div',{class:'tablewrap'},tb2));wrap.append(smc);}
  return wrap;
};

PANELS.Events=()=>{
  const wrap=$('div',{});
  wrap.append($('h2',{class:'sect-title'},'Event Studies'),
    $('p',{class:'lead'},'How sectors moved around dated policy/macro events — abnormal return (sector minus market), aggregated by event TYPE because any single event is N=1. Descriptive decision-support, not a predictor.'));
  const bt=D.events.by_type, hr=Object.fromEntries((D.events.hit_rate||[]).map(h=>[h.type,h]));
  const card=$('div',{class:'card'});
  card.append($('h3',{},'Average sector abnormal return (CAR) by event type'));
  const tb=$('table');tb.append($('thead',{},$('tr',{},...['Event type','n','Pre[-5,-1]','Event[0,1]','Post[1,5]','Drift[1,20]','Hit-rate'].map(h=>$('th',{},h)))));
  const bd=$('tbody');
  bt.forEach(r=>{const h=hr[r.type];
    bd.append($('tr',{},$('td',{},r.type.replace('_',' ')),$('td',{class:'num muted'},r.n),
      $('td',{class:'num '+cls(r['pre[-5,-1]'])},pct(r['pre[-5,-1]'],1)),
      $('td',{class:'num '+cls(r['event[0,1]'])},pct(r['event[0,1]'],1)),
      $('td',{class:'num '+cls(r['post[1,5]'])},pct(r['post[1,5]'],1)),
      $('td',{class:'num '+cls(r['drift[1,20]'])},pct(r['drift[1,20]'],1)),
      $('td',{class:'num'},h?(h.hit_rate*100).toFixed(0)+'%':'—')));});
  tb.append(bd);card.append($('div',{class:'tablewrap'},tb));
  card.append($('div',{class:'note'},'Read: "policy" events (housing scheme, EV/sector policy) show meaningful positive drift over the next month with a high expected-sign hit-rate — the "home-loan → construction" thesis, descriptively. IMF milestones do NOT move sectors as priors expect. Small n per type: treat as suggestive.'));
  wrap.append(card);
  // event list
  const lc=$('div',{class:'card',style:'margin-top:16px'});
  lc.append($('h3',{},`Event catalog (${D.events.list.length})`));
  const tb2=$('table');tb2.append($('thead',{},$('tr',{},...['Date','Type','Title','Sectors','Exp.'].map(h=>$('th',{},h)))));
  const b2=$('tbody');
  [...D.events.list].sort((a,b)=>b.date.localeCompare(a.date)).forEach(e=>b2.append($('tr',{},
    $('td',{class:'mono'},e.date),$('td',{},$('span',{class:'tag'},e.type)),
    $('td',{style:'text-align:left;white-space:normal;max-width:320px'},e.title),
    $('td',{class:'mono muted',style:'text-align:left;white-space:normal;max-width:220px;font-size:11px'},(e.sectors||[]).join(', ')),
    $('td',{class:'num '+cls(e.expected_sign)},e.expected_sign>0?'▲':e.expected_sign<0?'▼':'·'))));
  tb2.append(b2);lc.append($('div',{class:'tablewrap'},tb2));wrap.append(lc);
  return wrap;
};

PANELS.Sentiment=()=>{
  const wrap=$('div',{});
  wrap.append($('h2',{class:'sect-title'},'News & 5-Tier Sentiment'),
    $('p',{class:'lead'},'A real-time DECISION AID, honestly labelled — not a backtestable edge on this history. Headlines are tiered by source credibility (1 official → 5 social) and mapped to affected sectors; sentiment is tier-weighted.'));
  const tiers={1:['T1 official','var(--up)'],2:['T2 wire/press','var(--cyan)'],3:['T3 mainstream','var(--muted)'],4:['T4 analyst','var(--violet)'],5:['T5 social','var(--faint)']};
  const g=$('div',{class:'grid cols2'});
  // sector sentiment
  const sc=$('div',{class:'card'});sc.append($('h3',{},'Sector sentiment (tier-weighted)'));
  const bs=Object.entries(D.sentiment.by_sector).sort((a,b)=>b[1].score-a[1].score);
  if(!bs.length)sc.append($('div',{class:'muted'},'no items'));
  bs.forEach(([s,v])=>{const row=$('div',{style:'display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;margin:5px 0'});
    row.append($('div',{},s,' ',$('span',{class:'num '+cls(v.score),style:'font-size:12px'},(v.score>=0?'+':'')+v.score)),
      barRow(v.score,1,v.score>0?'var(--up)':'var(--down)'));sc.append(row);});
  g.append(sc);
  // tier legend + items
  const ic=$('div',{class:'card'});ic.append($('h3',{},'Latest headlines'));
  D.sentiment.items.forEach(it=>{const[tl,tc]=tiers[it.tier]||tiers[3];
    ic.append($('div',{class:'newsitem'},
      $('span',{class:'tier',style:`color:${tc};border:1px solid ${tc}`},'T'+it.tier),
      $('div',{},$('div',{},it.headline),$('div',{class:'mono muted',style:'font-size:11px'},`${it.source} · ${it.date} · ${(it.sectors||[]).join(', ')}`)),
      $('span',{class:'num '+cls(it.sentiment),style:'font-weight:600'},(it.sentiment>=0?'+':'')+it.sentiment)));});
  g.append(ic);wrap.append(g);
  wrap.append($('div',{class:'note',style:'margin-top:14px'},'Seed items shown are illustrative. A live pipeline scrapes headlines and classifies each with the LLM tagging contract (tier, sentiment, sectors, rationale) in analysis/sentiment.py.'));
  return wrap;
};

PANELS.Method=()=>{
  const wrap=$('div',{});
  wrap.append($('h2',{class:'sect-title'},'Method & Honesty'),
    $('p',{class:'lead'},'What is validated, what is context, and what would be self-deception. This terminal refuses the trap that killed four earlier stock-pickers: fitting a monthly predictor on ~85 data points.'));
  const rows=[['Market-timing regime','VERIFIED','var(--up)','Trend-following on the liquid index. Out-of-sample in both halves, survives cost + realistic cash yield. Sharpe ~1.15→~1.7, drawdown roughly halved. The one real edge.'],
    ['Sector interconnection graph','CURATED PRIOR','var(--accent)','Hand-built supply-chain + macro-sensitivity map from economic logic and cited facts. Not fitted; shown beside the data.'],
    ['Sector × macro correlations','DESCRIPTIVE','var(--cyan)','Real correlations with n and t-stats; |t|<2 flagged. Market-adjusted to isolate cross-sectional tilts.'],
    ['Event studies','DESCRIPTIVE','var(--cyan)','Sector abnormal returns around dated events, aggregated by type. Single events are N=1.'],
    ['News 5-tier sentiment','REAL-TIME AID','var(--violet)','Not backtestable on this history. A decision aid, tier-weighted, honestly labelled.']];
  const card=$('div',{class:'card'});
  rows.forEach(([n,s,c,d])=>{card.append($('div',{style:'display:grid;grid-template-columns:200px 130px 1fr;gap:12px;padding:11px 0;border-bottom:1px solid var(--grid);align-items:start'},
    $('div',{style:'font-weight:600'},n),$('div',{},$('span',{class:'tag',style:`color:${c};border-color:${c}`},s)),
    $('div',{class:'muted',style:'font-size:12.5px'},d)));});
  wrap.append(card);
  const dc=$('div',{class:'card',style:'margin-top:16px'});
  dc.append($('h3',{},'Data provenance'));
  dc.append($('div',{class:'detail'},
    $('div',{},$('b',{},'Prices'),' PSX daily (dps.psx.com.pk) via psx-quant, read-only snapshot'),
    $('div',{},$('b',{},'Coverage'),` ${D.meta.n_symbols} symbols · ${D.meta.n_months} months · through ${D.meta.as_of}`),
    $('div',{},$('b',{},'Policy rate'),' SBP MPC decisions, sourced per-decision'),
    $('div',{},$('b',{},'Macro'),' SBP / PBS / market data; sourced or flagged interpolated'),
    $('div',{},$('b',{},'Sector codes'),' verified against constituents (e.g. 0804=Cement)'),
    $('div',{},$('b',{},'Built on'),' psx-quant — never modified')));
  wrap.append(dc);
  wrap.append($('div',{class:'note',style:'margin-top:14px'},D.meta.note));
  const src=(D.sources&&D.sources.sources)||[];
  if(src.length){const sc=$('div',{class:'card',style:'margin-top:16px'});
    sc.append($('h3',{},`Data sources scanned (${src.length})`));
    const ts=$('table');ts.append($('thead',{},$('tr',{},...['Source','Provides','Access','Free','Reliab.'].map(h=>$('th',{},h)))));
    const bs=$('tbody');src.forEach(r=>bs.append($('tr',{},
      $('td',{style:'text-align:left'},r.name),
      $('td',{class:'muted',style:'text-align:left;white-space:normal;font-size:11px;max-width:280px'},(r.data_types||[]).join(', ')),
      $('td',{class:'mono muted',style:'font-size:11px'},(r.access||'').split('(')[0]),
      $('td',{},r.free?$('span',{class:'up'},'✓'):$('span',{class:'muted'},'paid')),
      $('td',{class:'mono muted',style:'font-size:11px'},r.reliability||''))));
    ts.append(bs);sc.append($('div',{class:'tablewrap'},ts));
    sc.append($('div',{class:'note'},'Roadmap for richer data: dps.psx.com.pk exposes JSON endpoints (EOD, company, financials); SCSTrade & Sarmaaya carry quarterly fundamentals (EPS/PE/ROE) — the paths to a full fundamentals time series.'));
    wrap.append(sc);}
  return wrap;
};

PANELS.Strategy=()=>{
  const w=$('div',{});const S=D.strategy||{};
  w.append($('h2',{class:'sect-title'},'The Strategy'),
    $('p',{class:'lead'},'The honest optimum from the full research arc: a rule-based momentum top-5 (futures-eligible only), gated by the verified timing signal. Convex, moonshot-carried, unlevered, sized small. Not a money-printer — a fat-tailed bet with ~−30% drawdown that depends on a fragile edge.'));
  // the rule
  const rc=$('div',{class:'card'});rc.append($('h3',{},'The rule ',$('span',{class:'tag ok'},'locked in')));
  rc.append($('div',{class:'mono',style:'font-size:12.5px;line-height:1.8'},
    'score = z(3m momentum) + z(closeness to 52w-high) + z(liquidity growth)',$('br',{}),
    'picks = top-5 futures-eligible by score',$('br',{}),
    'gate  = hold picks only when trend = RISK-ON, else cash (T-bills ~11%)'));
  const reg=(S.regime||{});
  rc.append($('div',{style:'margin-top:10px'},$('span',{class:'badge '+(reg.signal==='RISK-ON'?'on':'off'),style:'font-size:15px'},
    (reg.signal||'—')+(reg.exposure!=null?` · ${(reg.exposure*100).toFixed(0)}%`:''))));
  w.append(rc);
  // backtest stats
  const bt=S.backtest||{};const bc=$('div',{class:'card',style:'margin-top:16px'});
  bc.append($('h3',{},'Backtest — gated top-5 (net of cost+carry, walk-forward)'));
  const t=$('table');t.append($('thead',{},$('tr',{},...['Horizon','Avg / period','% positive','$1 → (7yr)','Max drawdown','n'].map(h=>$('th',{},h)))));
  const tb=$('tbody');['1','2','3'].forEach(H=>{const s=bt[H];if(!s)return;
    tb.append($('tr',{style:H==='3'?'background:var(--accent-soft)':''},$('td',{},H+'-month'),
      $('td',{class:'num '+cls(s.avg_per_period)},pct(s.avg_per_period)),
      $('td',{class:'num'},(s.pct_positive*100).toFixed(0)+'%'),
      $('td',{class:'num accent'},'$'+s.mult_1usd),
      $('td',{class:'num down'},pct(s.max_dd,0)),$('td',{class:'num muted'},s.n)));});
  t.append(tb);bc.append($('div',{class:'tablewrap'},t));
  bc.append($('div',{class:'note'},'Nominal PKR over ~7 years (1–2 regime cycles) against 20–38% inflation — real returns are far lower. The timing gate roughly halved drawdown vs ungated (−64%→−30%) and doubled compounding. Fragile: relies on the trend signal exiting before crashes, which PSX circuit breakers can prevent.'));
  w.append(bc);
  // live picks
  const lv=S.live||{};const lc=$('div',{class:'card',style:'margin-top:16px'});
  lc.append($('h3',{},'Live picks ',$('span',{class:'tag warn'},`entry ${lv.entry_date||'—'} · gate ${lv.risk_on?'RISK-ON':'RISK-OFF'}`)));
  if((lv.legs||[]).length){
    const t2=$('table');t2.append($('thead',{},$('tr',{},...['Symbol','Sector','Entry','Now','Return'].map(h=>$('th',{},h)))));
    const b2=$('tbody');[...lv.legs].sort((a,b)=>b.ret-a.ret).forEach(l=>b2.append($('tr',{},
      $('td',{},l.symbol),$('td',{class:'muted',style:'text-align:left;font-size:11px'},l.sector),
      $('td',{class:'num muted'},l.entry_close),$('td',{class:'num'},l.last_close),
      $('td',{class:'num '+cls(l.ret)},pct(l.ret,1)))));
    t2.append(b2);lc.append($('div',{class:'tablewrap'},t2));
    lc.append($('div',{class:'kpi',style:'margin-top:10px'},
      $('span',{class:'v '+cls(lv.basket_ret)},pct(lv.basket_ret,1)),
      $('span',{class:'l'},`basket so far · ${lv.days_held||0} days · through ${lv.as_of||''} ${lv.risk_on?'':'(gate RISK-OFF → real position is cash)'}`)));
  } else lc.append($('div',{class:'muted'},'no live picks'));
  lc.append($('div',{class:'note'},'⚠️ This is ONE partial period (~2 weeks of a 1–3 month hold), n=1 — as much luck as skill. It is the GOOD tail of a fat-tailed bet; the −30% drawdown periods look like this in reverse. Some of the gain is the market rebounding (beta), not selection. Do not extrapolate from one fortnight.'));
  w.append(lc);
  // this-month live comparison across ALL pick strategies
  const pl=S.predictor_live||{}, mk=S.market_live;
  const mc=$('div',{class:'card',style:'margin-top:16px'});
  mc.append($('h3',{},'This month — live, all strategies ',$('span',{class:'tag warn'},`entry ${lv.entry_date||'—'} → ${lv.as_of||S.as_of||''}`)));
  const rows=[['Market (buy&hold / timing baseline)',mk],['Gated momentum top-5 (locked-in)',lv.basket_ret]];
  ['1','2','3'].forEach(H=>{const d=(pl.by_horizon||{})[H];if(d)rows.push([`ML futures predictor ${H}m`,d.basket_ret]);});
  const maxv=Math.max(...rows.map(([,v])=>Math.abs(v||0)),0.05);
  rows.forEach(([lab,v])=>mc.append($('div',{style:'display:grid;grid-template-columns:230px 1fr 60px;gap:8px;align-items:center;margin:4px 0'},
    $('div',{style:lab.includes('Market')?'color:var(--muted)':'font-weight:600'},lab),
    barRow(v||0,maxv,(v||0)>0?'var(--up)':'var(--down)'),
    $('div',{class:'num '+cls(v)},pct(v,1)))));
  // ML predictor picks per horizon (tickers)
  ['1','2','3'].forEach(H=>{const d=(pl.by_horizon||{})[H];if(!d||!d.legs.length)return;
    mc.append($('div',{class:'chipwrap',style:'margin-top:8px'},$('span',{class:'mono muted',style:'font-size:11px;align-self:center'},`ML ${H}m: `),
      ...d.legs.map(l=>$('span',{class:'pill',style:`background:var(--panel2);color:${(l.ret||0)>=0?'var(--up)':'var(--down)'}`},`${l.symbol} `,$('span',{class:'muted'},l.entry),` ${l.ret==null?'':pct(l.ret,0)}`))));});
  mc.append($('div',{class:'note'},'ONE partial period (n=1, ~2.5 weeks), and the market rebounded — every strategy is riding beta + the good tail (moonshots showed up). The pick strategies beating the market here is the mirror image of the months they lose. Do not extrapolate.'));
  w.append(mc);
  w.append($('div',{class:'card',style:'margin-top:16px;border-left:3px solid var(--down)'},
    $('h3',{},'Do not fool yourself'),
    $('div',{class:'detail',style:'grid-template-columns:1fr;font-size:12.5px;gap:8px'},
      $('div',{},'• Individual surger prediction has NO out-of-sample edge (precision ~16%, catch the #1 ~1-in-10). The picks are a convex basket, not a crystal ball.'),
      $('div',{},'• The −30% drawdown is intrinsic — the moonshots and the crashers are the SAME volatile names; you cannot keep the upside and cut the downside.'),
      $('div',{},'• It LOST in the last live window (Jan-2026: gate was risk-on into the −31% Iran-war crash → −11 to −15%). The gate helps on average, not every time.'),
      $('div',{},'• NEVER lever this. Research on your own project — not investment advice.'))));
  return w;
};

PANELS.Mood=()=>{
  const w=$('div',{});const c=D.mood.current, bt=D.mood.backtest;
  w.append($('h2',{class:'sect-title'},'Market Mood'),
    $('p',{class:'lead'},'A 5-level Fear/Greed gauge from market internals — momentum, trend, breadth, volatility, drawdown — trailing-percentile normalised so the history has no look-ahead.'));
  const bands=[['Extreme Fear','var(--down)'],['Fear','#d9773c'],['Neutral','var(--muted)'],['Greed','#6fae4f'],['Extreme Greed','var(--up)']];
  const gc=$('div',{class:'card'});gc.append($('h3',{},'Today’s mood'));
  const score=c.score, bi=Math.min(4,Math.floor(score/20));
  gc.append($('div',{class:'kpi',style:'margin-bottom:12px'},$('span',{class:'v',style:`color:${bands[bi][1]}`},c.label),
    $('span',{class:'l'},`${score}/100 · was ${c.week_ago} a week ago`)));
  const bar=$('div',{style:'position:relative;height:32px;border-radius:8px;overflow:hidden;display:flex;border:1px solid var(--border)'});
  bands.forEach(([l,col])=>bar.append($('div',{style:`flex:1;background:${col};opacity:.32`})));
  bar.append($('div',{style:`position:absolute;top:-3px;bottom:-3px;left:calc(${score}% - 2px);width:4px;background:var(--ink);border-radius:2px`}));
  gc.append(bar);
  const cw=$('div',{class:'chipwrap',style:'margin-top:14px'});
  for(const[k,v]of Object.entries(c.components))cw.append($('span',{class:'mchip'},`${k.replace('_',' ')}: ${v}`));
  gc.append(cw);w.append(gc);
  const hc=$('div',{class:'card',style:'margin-top:16px'});hc.append($('h3',{},'Mood history (last ~year)'));
  hc.append(lineChart([{x:c.history.x,y:c.history.y}],{fmt:v=>v.toFixed(0),colors:['var(--accent)'],h:170}));w.append(hc);
  const bc=$('div',{class:'card',style:'margin-top:16px'});
  bc.append($('h3',{},'Does mood predict returns? ',$('span',{class:'tag info'},'in-sample, honest')));
  const tb=$('table');tb.append($('thead',{},$('tr',{},...['Mood band at entry','n','Avg fwd 20d','Median','Up-rate'].map(h=>$('th',{},h)))));
  const bd=$('tbody');(bt.table||[]).forEach(r=>bd.append($('tr',{},$('td',{},r.band),$('td',{class:'num muted'},r.n),
    $('td',{class:'num '+cls(r.avg_fwd)},pct(r.avg_fwd)),$('td',{class:'num '+cls(r.median_fwd)},pct(r.median_fwd)),
    $('td',{class:'num'},(r.up_rate*100).toFixed(0)+'%'))));tb.append(bd);bc.append($('div',{class:'tablewrap'},tb));
  bc.append($('div',{class:'note'},bt.verdict+' — '+bt.caveat));w.append(bc);
  return w;
};

PANELS.Surges=()=>{
  const w=$('div',{});const s=D.surges;
  w.append($('h2',{class:'sect-title'},'Surges, Multi-baggers & Shocks'),
    $('p',{class:'lead'},'Mined from 7 years of prices. Descriptive base rates, not signals — including the honest test of the “banks boom when rates are high” thesis, and how the market dips into shocks and rebounds after.'));
  const g=$('div',{class:'grid cols2'});
  const mbc=$('div',{class:'card'});mbc.append($('h3',{},'Multi-baggers (peak multiple, liquid)'));
  const t1=$('table');t1.append($('thead',{},$('tr',{},...['Symbol','Sector','Peak×','Now×','CAGR'].map(h=>$('th',{},h)))));
  const b1=$('tbody');(s.multibaggers||[]).slice(0,20).forEach(r=>b1.append($('tr',{},$('td',{},r.symbol),
    $('td',{class:'muted',style:'text-align:left;font-size:11px'},r.sector),$('td',{class:'num accent'},r.peak_mult+'×'),
    $('td',{class:'num'},r.end_mult+'×'),$('td',{class:'num'},r.cagr==null?'—':(r.cagr*100).toFixed(0)+'%'))));
  t1.append(b1);mbc.append($('div',{class:'tablewrap'},t1));g.append(mbc);
  const rc=$('div',{class:'card'});rc.append($('h3',{},'Recent surgers (trailing 6 months)'));
  const t2=$('table');t2.append($('thead',{},$('tr',{},...['Symbol','Sector','6M'].map(h=>$('th',{},h)))));
  const b2=$('tbody');(s.recent||[]).forEach(r=>b2.append($('tr',{},$('td',{},r.symbol),
    $('td',{class:'muted',style:'text-align:left;font-size:11px'},r.sector),$('td',{class:'num up'},pct(r.ret,0)))));
  t2.append(b2);rc.append($('div',{class:'tablewrap'},t2));g.append(rc);w.append(g);
  const bk=s.bank_thesis;const bc=$('div',{class:'card',style:'margin-top:16px'});
  bc.append($('h3',{},'“Banks boom when rates are high” — tested ',$('span',{class:'tag ok'},'in-sample')));
  bc.append($('div',{class:'mono',style:'margin-bottom:10px'},bk.verdict));
  const t3=$('table');t3.append($('thead',{},$('tr',{},...['Rate regime','Months','Bank avg/mo','Bank excess/mo','Market avg/mo'].map(h=>$('th',{},h)))));
  const b3=$('tbody');for(const[k,v]of Object.entries(bk.regime_split))b3.append($('tr',{},$('td',{},k),$('td',{class:'num muted'},v.n_months),
    $('td',{class:'num '+cls(v.bank_avg)},pct(v.bank_avg)),$('td',{class:'num '+cls(v.bank_excess_avg)},pct(v.bank_excess_avg)),
    $('td',{class:'num '+cls(v.mkt_avg)},pct(v.mkt_avg))));t3.append(b3);bc.append($('div',{class:'tablewrap'},t3));
  bc.append($('div',{class:'note'},'UBL/MCB/HBL outperform the market when the policy rate is high; MEBL (a top multi-bagger) compounded regardless of rates.'));
  w.append(bc);
  const g2=$('div',{class:'grid cols2',style:'margin-top:16px'});
  const sm=s.surge_meta, dr=s.dip_rebounds;
  const smc=$('div',{class:'card'});smc.append($('h3',{},'Surge base rate (≥50% in 20d)'));
  smc.append($('div',{class:'detail'},$('div',{},'Episodes'),$('div',{class:'num'},sm.n_episodes||'—'),
    $('div',{},'Avg fwd 20d'),$('div',{class:'num '+cls(sm.avg_fwd_20d)},pct(sm.avg_fwd_20d)),
    $('div',{},'Median fwd 20d'),$('div',{class:'num '+cls(sm.median_fwd_20d)},pct(sm.median_fwd_20d)),
    $('div',{},'Continued up'),$('div',{class:'num'},sm.continued_up_rate!=null?(sm.continued_up_rate*100).toFixed(0)+'%':'—')));
  smc.append($('div',{class:'note'},sm.note||''));g2.append(smc);
  const drc=$('div',{class:'card'});drc.append($('h3',{},'Dips → rebounds (≤−25% in 20d)'));
  drc.append($('div',{class:'detail'},$('div',{},'Episodes'),$('div',{class:'num'},dr.n_episodes||'—'),
    $('div',{},'Avg rebound 40d'),$('div',{class:'num '+cls(dr.avg_rebound)},pct(dr.avg_rebound)),
    $('div',{},'Bounce rate'),$('div',{class:'num'},dr.rebound_positive_rate!=null?(dr.rebound_positive_rate*100).toFixed(0)+'%':'—')));
  drc.append($('div',{class:'note'},dr.note||''));g2.append(drc);w.append(g2);
  if((s.shock_response||[]).length){const sc=$('div',{class:'card',style:'margin-top:16px'});
    sc.append($('h3',{},'Geopolitical / macro shocks — index dip & rebound'));
    const t4=$('table');t4.append($('thead',{},$('tr',{},...['Date','Event','Into event (10d)','Rebound (20d)'].map(h=>$('th',{},h)))));
    const b4=$('tbody');s.shock_response.forEach(r=>b4.append($('tr',{},$('td',{class:'mono'},r.date),
      $('td',{style:'text-align:left;white-space:normal;max-width:340px'},r.title),
      $('td',{class:'num '+cls(r.into_event_10d)},pct(r.into_event_10d)),$('td',{class:'num '+cls(r.rebound_20d)},pct(r.rebound_20d)))));
    t4.append(b4);sc.append($('div',{class:'tablewrap'},t4));
    sc.append($('div',{class:'note'},'May-2025 India–Pakistan escalation: −10% into it, +15% rebound in 20d. COVID (kept falling) is the honest exception — not every dip bounces.'));
    w.append(sc);}
  return w;
};

PANELS.Predictor=()=>{
  const w=$('div',{});const p=D.predictor;
  w.append($('h2',{class:'sect-title'},'Surge Predictor'),
    $('p',{class:'lead'},'A surge-propensity model from pre-surge metrics, validated OUT-OF-SAMPLE (train pre-2024, test 2024→now). This is the honest “predictor” — no curve-fitting; it reports the real lift, however modest.'));
  if(p.error){w.append($('div',{class:'card muted'},'insufficient data'));return w;}
  const topd=(p.decile_lift||[]).find(d=>d.decile===9);
  const kpi=(v,l,cl='')=>$('div',{class:'card'},$('div',{class:'kpi'},$('span',{class:'v '+cl},v),$('span',{class:'l'},l)));
  w.append($('div',{class:'grid cols3'},kpi((p.base_rate*100).toFixed(0)+'%','base surge rate'),
    kpi(p.oos_auc.toFixed(2),'out-of-sample AUC','accent'),kpi(topd?topd.lift+'×':'—','top-decile lift','accent')));
  w.append($('div',{class:'card',style:'margin-top:16px'},$('div',{class:'mono'},p.verdict)));
  const dc=$('div',{class:'card',style:'margin-top:16px'});dc.append($('h3',{},'Decile lift (test): actual surge rate by predicted decile'));
  const dl=p.decile_lift||[];const maxr=Math.max(...dl.map(d=>d.mean),0.01);
  dl.forEach(d=>{dc.append($('div',{style:'display:grid;grid-template-columns:44px 1fr 52px;gap:8px;align-items:center;margin:3px 0'},
    $('div',{class:'mono muted'},'D'+(d.decile+1)),
    $('div',{class:'bar',style:'height:14px'},$('span',{style:`left:0;width:${d.mean/maxr*100}%;background:${d.decile===9?'var(--accent)':'var(--cyan)'}`})),
    $('div',{class:'num'},(d.mean*100).toFixed(0)+'%')));});
  dc.append($('div',{class:'note'},`Base rate ${(p.base_rate*100).toFixed(0)}%. Top decile rising above it = the metrics carry signal (modestly, AUC ~${p.oos_auc.toFixed(2)}).`));
  w.append(dc);
  const g=$('div',{class:'grid cols2',style:'margin-top:16px'});
  const fc=$('div',{class:'card'});fc.append($('h3',{},'What drives surge odds'));
  const tf=$('table');tf.append($('thead',{},$('tr',{},$('th',{},'Feature'),$('th',{},'AUC drop when shuffled'))));
  const bf=$('tbody');(p.top_features||[]).forEach(f=>bf.append($('tr',{},$('td',{class:'mono'},f.feature),$('td',{class:'num'},f.auc_drop.toFixed(3)))));
  tf.append(bf);fc.append(tf);g.append(fc);
  const sc=$('div',{class:'card'});sc.append($('h3',{},'Current top surge-propensity screen'));
  const ts=$('table');ts.append($('thead',{},$('tr',{},...['Symbol','Sector','p(surge)','ret60'].map(h=>$('th',{},h)))));
  const bs=$('tbody');(p.screen||[]).forEach(r=>bs.append($('tr',{},$('td',{},r.symbol),
    $('td',{class:'muted',style:'text-align:left;font-size:11px'},r.sector_name),
    $('td',{class:'num accent'},r.prob.toFixed(2)),$('td',{class:'num '+cls(r.ret_60)},pct(r.ret_60,0)))));
  ts.append(bs);sc.append($('div',{class:'tablewrap'},ts));
  sc.append($('div',{class:'note'},'A screen, not a promise — highest historical-pattern odds of a big move. Use as a watchlist, not a buy list.'));
  g.append(sc);w.append(g);
  if((p.sector_base_rates||[]).length){const bc=$('div',{class:'card',style:'margin-top:16px'});
    bc.append($('h3',{},'Which sectors surge most often (base rates)'));
    const tb=$('table');tb.append($('thead',{},$('tr',{},...['Sector','Surge rate','n'].map(h=>$('th',{},h)))));
    const bd=$('tbody');p.sector_base_rates.slice(0,12).forEach(r=>bd.append($('tr',{},$('td',{},r.sector_name),
      $('td',{class:'num accent'},(r.surge_rate*100).toFixed(0)+'%'),$('td',{class:'num muted'},r.n))));
    tb.append(bd);bc.append($('div',{class:'tablewrap'},tb));w.append(bc);}
  return w;
};

PANELS.Fundamentals=()=>{
  const w=$('div',{});const f=D.fundamentals;
  w.append($('h2',{class:'sect-title'},'Company Fundamentals'),
    $('p',{class:'lead'},`Latest valuation snapshot for ${(f.companies||[]).length} large PSX names (as of ${f.as_of||'—'}). From PSX/SCSTrade/Sarmaaya — blanks are values that couldn’t be verified, left empty rather than fabricated. Click a header to sort.`));
  const card=$('div',{class:'card'});
  const cols=[['ticker','Ticker'],['sector','Sector'],['pe','P/E'],['eps_ttm','EPS'],['roe_pct','ROE%'],['div_yield_pct','Div%'],['mkt_cap_pkr_bn','MCap bn'],['earnings_growth_yoy_pct','EPS gr%']];
  let sk='mkt_cap_pkr_bn',asc=false;
  const tb=$('table');const th=$('thead');const hr=$('tr');
  cols.forEach(([k,l])=>hr.append($('th',{onclick:()=>{asc=(sk===k)?!asc:false;sk=k;render();}},l)));th.append(hr);tb.append(th);
  const bd=$('tbody');tb.append(bd);
  function render(){bd.innerHTML='';const rows=[...(f.companies||[])].sort((a,b)=>{const x=a[sk],y=b[sk];
    if(typeof x==='string')return asc?(x||'').localeCompare(y||''):(y||'').localeCompare(x||'');
    return asc?((x==null?-1e12:x)-(y==null?-1e12:y)):((y==null?-1e12:y)-(x==null?-1e12:x));});
    rows.forEach(r=>bd.append($('tr',{},$('td',{},r.ticker),$('td',{class:'muted',style:'text-align:left;font-size:11px'},r.sector),
      $('td',{class:'num'},r.pe==null?'—':fmt(r.pe,1)),$('td',{class:'num'},r.eps_ttm==null?'—':fmt(r.eps_ttm,1)),
      $('td',{class:'num'},r.roe_pct==null?'—':fmt(r.roe_pct,0)),$('td',{class:'num'},r.div_yield_pct==null?'—':fmt(r.div_yield_pct,1)),
      $('td',{class:'num'},r.mkt_cap_pkr_bn==null?'—':fmt(r.mkt_cap_pkr_bn,0)),
      $('td',{class:'num '+cls(r.earnings_growth_yoy_pct)},r.earnings_growth_yoy_pct==null?'—':fmt(r.earnings_growth_yoy_pct,0)+'%'))));}
  render();card.append($('div',{class:'tablewrap'},tb));w.append(card);
  w.append($('div',{class:'note',style:'margin-top:12px'},'Point-in-time snapshots, not a full quarterly time series (reliable per-quarter history needs the SCSTrade / Sarmaaya scrapers listed under Method → Data sources).'));
  return w;
};

PANELS.Sovereign=()=>{
  const w=$('div',{});const s=D.sovereign;
  w.append($('h2',{class:'sect-title'},'Sovereign, Debt & IMF'),
    $('p',{class:'lead'},'Pakistan’s credit ratings, external debt and IMF programme timeline — the macro backdrop that sets the whole market’s risk premium.'));
  const g=$('div',{class:'grid cols2'});
  const agencyColor={Moodys:'var(--violet)',SP:'var(--cyan)',Fitch:'var(--accent)'};
  const rc=$('div',{class:'card'});rc.append($('h3',{},'Sovereign credit ratings'));
  const tr=$('table');tr.append($('thead',{},$('tr',{},...['Date','Agency','Rating','Action'].map(h=>$('th',{},h)))));
  const br=$('tbody');[...(s.ratings||[])].sort((a,b)=>b.date.localeCompare(a.date)).forEach(r=>br.append($('tr',{},
    $('td',{class:'mono'},r.date),$('td',{style:`color:${agencyColor[r.agency]||''}`},r.agency),
    $('td',{class:'mono',style:'font-weight:600'},r.rating),
    $('td',{class:'muted',style:'text-align:left;white-space:normal;font-size:11px;max-width:280px'},(r.action||r.outlook||'')))));
  tr.append(br);rc.append($('div',{class:'tablewrap'},tr));g.append(rc);
  const ic=$('div',{class:'card'});ic.append($('h3',{},'IMF programme timeline'));
  const ti=$('table');ti.append($('thead',{},$('tr',{},...['Date','Program','Event','$bn'].map(h=>$('th',{},h)))));
  const bi=$('tbody');[...(s.imf_programs||[])].sort((a,b)=>b.date.localeCompare(a.date)).forEach(r=>bi.append($('tr',{},
    $('td',{class:'mono'},r.date),$('td',{},r.program),$('td',{style:'text-align:left;white-space:normal;font-size:11px'},r.event),
    $('td',{class:'num'},r.amount_usd_bn==null?'—':r.amount_usd_bn))));
  ti.append(bi);ic.append($('div',{class:'tablewrap'},ti));g.append(ic);w.append(g);
  const g2=$('div',{class:'grid cols2',style:'margin-top:16px'});
  if((s.external_debt||[]).length){const ec=$('div',{class:'card'});ec.append($('h3',{},'External debt (USD bn)'));
    const ed=[...s.external_debt].sort((a,b)=>a.year-b.year);
    ec.append(lineChart([{x:ed.map(e=>''+e.year),y:ed.map(e=>e.total_usd_bn)}],{fmt:v=>'$'+v.toFixed(0),colors:['var(--down)'],h:150}));
    ec.append($('div',{class:'legend',style:'margin-top:6px'},$('span',{},`${ed[0].year} $${ed[0].total_usd_bn}bn → ${ed[ed.length-1].year} $${ed[ed.length-1].total_usd_bn}bn`)));g2.append(ec);}
  if((s.macro_annual||[]).length){const mc=$('div',{class:'card'});mc.append($('h3',{},'Macro by fiscal year'));
    const tm=$('table');tm.append($('thead',{},$('tr',{},...['FY','GDP %','Deficit %GDP','Debt/GDP %'].map(h=>$('th',{},h)))));
    const bm=$('tbody');s.macro_annual.forEach(r=>bm.append($('tr',{},$('td',{},r.fy),
      $('td',{class:'num '+cls(r.gdp_growth_pct)},r.gdp_growth_pct==null?'—':fmt(r.gdp_growth_pct,1)),
      $('td',{class:'num'},r.fiscal_deficit_pct_gdp==null?'—':fmt(r.fiscal_deficit_pct_gdp,1)),
      $('td',{class:'num'},r.debt_to_gdp_pct==null?'—':fmt(r.debt_to_gdp_pct,0)))));
    tm.append(bm);mc.append($('div',{class:'tablewrap'},tm));g2.append(mc);}
  w.append(g2);
  return w;
};

PANELS.Futures=()=>{
  const w=$('div',{});const F=D.futures||{};
  w.append($('h2',{class:'sect-title'},'Futures Surger Predictor'),
    $('p',{class:'lead'},`Top-5 surger predictor for the PSX single-stock-futures universe (${F.universe_now||'—'} names, point-in-time eligible), horizons 1/2/3 months. Built the honest way: no look-ahead, walk-forward with a purge/embargo, out-of-sample. Meta-analysis of every metric drives it.`));
  const ft=(F.factor_tilt||{})['3']||{}, wf=(F.horizons||{})['3']||{};
  // headline verdict
  const vb=$('div',{class:'card',style:'border-left:3px solid var(--accent)'});
  vb.append($('h3',{},'Honest verdict ',$('span',{class:'tag warn'},'no curve-fitting')));
  vb.append($('div',{style:'font-size:15px;line-height:1.6'},
    'Meta-analysis found ',$('b',{class:'accent'},'real but weak'),' selection factors (momentum, proximity-to-52w-high, low-volatility, low-beta, avoid recent 1-day spikes). But: ',
    $('b',{},'top-5 surger picking fails out-of-sample'),' — the extremes are dominated by idiosyncratic news. A broad factor tilt beats the universe by only ~0.5%/period (not significant, eaten by cost). ',
    $('b',{class:'up'},'Conclusion: the robust edge in PSX is market timing (when to be in/out), not stock selection.')));
  w.append(vb);
  // meta-analysis table (3m)
  const ma=(F.meta_analysis||{})['3']||[];
  if(ma.length){const mc=$('div',{class:'card',style:'margin-top:16px'});
    mc.append($('h3',{},'Meta-analysis: every metric’s standalone power (3-month, cross-sectional IC)'));
    const tb=$('table');tb.append($('thead',{},$('tr',{},...['Metric','Mean IC','t-stat','Up-month %','Signal'].map(h=>$('th',{},h)))));
    const bd=$('tbody');ma.slice(0,16).forEach(r=>{const sig=Math.abs(r.t)>=2;
      bd.append($('tr',{},$('td',{class:'mono'},r.feature),$('td',{class:'num '+cls(r.mean_ic)},r.mean_ic>0?'+'+r.mean_ic:r.mean_ic),
        $('td',{class:'num',style:sig?'color:var(--ink);font-weight:600':'color:var(--faint)'},r.t>0?'+'+r.t:r.t),
        $('td',{class:'num muted'},(r.hit*100).toFixed(0)+'%'),
        $('td',{},sig?$('span',{class:'accent'},'● significant'):$('span',{class:'muted'},'○ noise'))));});
    tb.append(bd);mc.append($('div',{class:'tablewrap'},tb));
    mc.append($('div',{class:'note'},'IC = month-by-month rank correlation of the metric with forward return, averaged over 80+ months. |t|≥2 ≈ real. Strong: near-52w-high, 6m momentum, low drawdown (+); high vol, high beta, big recent spike (−). All economically tiny (IC~0.1 ≈ 1% of variance).'));
    w.append(mc);}
  // surger DNA (bottom-up autopsy of the actual top-5 surgers)
  const dna=(F.surger_dna||{})['1']||{};
  if(dna.profile){const dc=$('div',{class:'card',style:'margin-top:16px'});
    dc.append($('h3',{},'Surger DNA — the actual top-5 surgers’ pre-surge profile (1m)'));
    dc.append($('div',{class:'mono muted',style:'margin-bottom:8px;font-size:12px'},`${dna.n_surgers} surgers · avg surge ${pct(dna.surger_avg_fwd,0)} · median ${pct(dna.surger_median_fwd,0)}`));
    const tb=$('table');tb.append($('thead',{},$('tr',{},...['Metric','Surger avg','Others avg','Std diff (d)'].map(h=>$('th',{},h)))));
    const bd=$('tbody');dna.profile.slice(0,12).forEach(r=>{const strong=Math.abs(r.std_diff)>=0.2;
      bd.append($('tr',{},$('td',{class:'mono'},r.feature),$('td',{class:'num'},fmt(r.surger_mean,3)),$('td',{class:'num muted'},fmt(r.other_mean,3)),
        $('td',{class:'num '+cls(r.std_diff),style:strong?'font-weight:600':''},(r.std_diff>0?'+':'')+r.std_diff)));});
    tb.append(bd);dc.append($('div',{class:'tablewrap'},tb));
    if(dna.top_sectors){const sc=$('div',{class:'chipwrap',style:'margin-top:10px'});
      dna.top_sectors.slice(0,6).forEach(s=>sc.append($('span',{class:'mchip'},`${s.sector} ${s.pct.toFixed(0)}%`)));dc.append(sc);}
    dc.append($('div',{class:'note'},'Surgers were momentum + relative-strength names already in an uptrend, in Tech/Cement/Banks, appearing most in high-inflation / weak-PKR / post-rate-cut regimes. But std-diff ≈ 0.2 (small) — the distributions overlap ~92%, so the pattern is real yet weak. That is precisely why the top-5 selector can’t be made reliable, and why the edge is regime timing + tilt, not blind picking.'));
    w.append(dc);}
  // factor tilt OOS
  const tilt=F.factor_tilt||{};
  const tc=$('div',{class:'card',style:'margin-top:16px'});
  tc.append($('h3',{},'Factor-tilt basket (top-quintile) vs universe — out-of-sample'));
  const t2=$('table');t2.append($('thead',{},$('tr',{},...['Horizon','Top-Q fwd','Universe','Spread','Spread t','Long-Short','IC t','Hit'].map(h=>$('th',{},h)))));
  const b2=$('tbody');['1','2','3'].forEach(H=>{const r=tilt[H];if(!r||r.error)return;
    b2.append($('tr',{},$('td',{},H+'m'),$('td',{class:'num '+cls(r.top_avg_fwd)},pct(r.top_avg_fwd)),
      $('td',{class:'num'},pct(r.universe_avg_fwd)),$('td',{class:'num '+cls(r.spread_top_minus_uni)},pct(r.spread_top_minus_uni)),
      $('td',{class:'num',style:Math.abs(r.spread_t)>=2?'color:var(--up)':'color:var(--faint)'},fmt(r.spread_t,1)),
      $('td',{class:'num '+cls(r.longshort_avg)},pct(r.longshort_avg)),
      $('td',{class:'num accent'},fmt(r.ic_t,1)),$('td',{class:'num'},(r.hit_rate*100).toFixed(0)+'%')));});
  t2.append(b2);tc.append($('div',{class:'tablewrap'},t2));
  tc.append($('div',{class:'note'},'IC t-stats are significant (2.5–3.3) — the factors are real. But the top-quintile spread t-stats are <1 — the tilt is too small to trade reliably after costs. Real signal, not a robust portfolio.'));
  w.append(tc);
  // top-5 walk-forward scorecard
  const wc=$('div',{class:'card',style:'margin-top:16px'});
  wc.append($('h3',{},'Top-5 surger picking — walk-forward OOS scorecard'));
  const t3=$('table');t3.append($('thead',{},$('tr',{},...['Horizon','Top-5 fwd','Universe','Spread','Hit','Precision@5','IC t'].map(h=>$('th',{},h)))));
  const b3=$('tbody');['1','2','3'].forEach(H=>{const r=(F.horizons||{})[H];if(!r||r.error)return;
    b3.append($('tr',{},$('td',{},H+'m'),$('td',{class:'num '+cls(r.top5_avg_fwd)},pct(r.top5_avg_fwd)),
      $('td',{class:'num'},pct(r.universe_avg_fwd)),$('td',{class:'num '+cls(r.spread_top_minus_uni)},pct(r.spread_top_minus_uni)),
      $('td',{class:'num'},(r.hit_rate_beat_uni*100).toFixed(0)+'%'),$('td',{class:'num'},(r.precision_at_5*100).toFixed(0)+'%'),
      $('td',{class:'num muted'},fmt(r.ic_t,1))));});
  t3.append(b3);wc.append($('div',{class:'tablewrap'},t3));
  wc.append($('div',{class:'note'},'Precision@5 ~10% ≈ random. The concentrated top-5 bet has no OOS edge — proof (not failure) that we tested honestly instead of curve-fitting a pretty backtest.'));
  w.append(wc);
  // leverage-fair / risk-adjusted check
  if(((F.horizons||{})['3']||{}).risk_adjusted){const rc=$('div',{class:'card',style:'margin-top:16px'});
    rc.append($('h3',{},'Leverage-fair check: top-5 vs universe (risk-adjusted, OOS)'));
    const t=$('table');t.append($('thead',{},$('tr',{},...['Horizon','Basket','CAGR','Vol','Sharpe','MaxDD'].map(h=>$('th',{},h)))));
    const b=$('tbody');['1','2','3'].forEach(H=>{const rj=(F.horizons||{})[H];if(!rj||!rj.risk_adjusted)return;
      [['top5','top-5'],['universe','universe (EW)']].forEach(([k,lbl])=>{const m=rj.risk_adjusted[k]||{};const best=k==='universe';
        b.append($('tr',{style:best?'background:var(--accent-soft)':''},$('td',{},H+'m'),$('td',{},lbl),
          $('td',{class:'num'},pct(m.cagr,0)),$('td',{class:'num muted'},pct(m.vol,0)),
          $('td',{class:'num',style:best?'color:var(--accent);font-weight:600':''},fmt(m.sharpe,2)),
          $('td',{class:'num '+cls(m.maxdd)},pct(m.maxdd,0))));});});
    t.append(b);rc.append($('div',{class:'tablewrap'},t));
    rc.append($('div',{class:'note'},'Concentrating into 5 names RAISES volatility (diversification lost) → lower Sharpe and deeper drawdowns than the ~100-name equal-weight universe. On a leverage-fair basis you would lever the universe (Sharpe ~2–2.8), not the top-5. The diversified universe + the verified timing overlay is the real leverageable play — selection concentration hurts it.'));
    w.append(rc);}
  // current picks
  const cur=(F.current||{}).picks||{};
  const cc=$('div',{class:'card',style:'margin-top:16px'});
  cc.append($('h3',{},'Model’s current top-5 ',$('span',{class:'tag'},'low confidence — no validated edge')));
  ['1','2','3'].forEach(H=>{const ps=cur[H]||[];if(!ps.length)return;
    cc.append($('div',{style:'margin:6px 0'},$('span',{class:'mono muted'},H+'m: '),
      ...ps.map(p=>$('span',{class:'pill',style:'background:var(--panel2)'},`${p.symbol} `,$('span',{class:'muted'},p.score>=0?'+'+p.score:p.score)))));});
  cc.append($('div',{class:'note'},'Shown for transparency / live tracking only. Because the predictor has no validated OOS edge, treat these as a watchlist, not a buy list.'));
  w.append(cc);
  // next-data honesty note
  const nc=$('div',{class:'card',style:'margin-top:16px'});
  nc.append($('h3',{},'What could add real selection signal (and what is wired)'));
  nc.append($('div',{class:'detail',style:'grid-template-columns:1fr'},
    $('div',{},'✅ ',$('b',{},'FIPI/LIPI flows'),' — wired as a market/timing signal (Regime tab). NCCPL data is market-level, not per-stock, so it informs WHEN to be invested, not WHICH futures name. Full 7y history for a flow backtest needs the NCCPL bulk portal.'),
    $('div',{},'⏳ ',$('b',{},'Earnings momentum'),' — the most promising missing stock-specific feature (surges follow earnings beats). PSX has no broad analyst consensus, so a true earnings surprise is unavailable; the honest proxy is reported quarterly-EPS growth and acceleration, which needs a historical quarterly-EPS scrape (SCSTrade/Sarmaaya) to backtest. Current EPS-growth snapshots are in the Fundamentals tab.')));
  nc.append($('div',{class:'note'},'Neither can leak from price data, so both are legitimate additions — but each needs its own historical series before it can be honestly backtested. No shortcuts taken.'));
  w.append(nc);
  return w;
};

PANELS.Filter=()=>{
  const w=$('div',{});const F=D.analysis_filter||{};
  w.append($('h2',{class:'sect-title'},'Analysis Filter'),
    $('p',{class:'lead'},'A SEPARATE investor-brain overlay that sits on top of the locked-in picks — it never changes them. It re-judges each pick through four lenses (extension / “chased”, regime-fit, overhang, valuation) and down-sizes the crash-prone names. Walk-forward, OOS-validated: it roughly halves max drawdown. Precision is NOT improvable mechanically on the data available — the verdict tags are a discretionary read, not an edge.'));
  const rg=F.regime||{};
  const rc=$('div',{class:'card'});
  rc.append($('h3',{},'Regime read ',$('span',{class:'tag info'},'from CPI + policy-rate trend')));
  rc.append($('div',{class:'mono',style:'font-size:14px;margin:6px 0'},'state: ',
    $('b',{class:rg.sign>0?'up':rg.sign<0?'down':'accent'},(rg.label||'—').toUpperCase()),
    rg.cpi_chg_3m!=null?`  ·  3-mo CPI change ${rg.cpi_chg_3m>0?'+':''}${rg.cpi_chg_3m}pp`:''));
  rc.append($('div',{class:'muted',style:'font-size:12.5px'},'favours: '+(rg.favours||'—')));
  w.append(rc);
  const bt=F.backtest||{};
  const bc=$('div',{class:'card',style:'margin-top:16px'});
  bc.append($('h3',{},'What the overlay does to risk ',$('span',{class:'tag ok'},'walk-forward · OOS-validated')));
  const t=$('table');t.append($('thead',{},$('tr',{},...['Horizon','Base maxDD','Filtered maxDD','Base Sharpe','Filt Sharpe','Base Calmar','Filt Calmar'].map(h=>$('th',{},h)))));
  const tb=$('tbody');['1','2','3'].forEach(H=>{const s=bt[H];if(!s)return;
    tb.append($('tr',{style:H==='3'?'background:var(--accent-soft)':''},$('td',{},H+'-month'),
      $('td',{class:'num down'},pct(s.base_dd,0)),
      $('td',{class:'num up'},pct(s.filt_dd,0)),
      $('td',{class:'num muted'},fmt(s.base_sharpe,2)),
      $('td',{class:'num'},fmt(s.filt_sharpe,2)),
      $('td',{class:'num muted'},fmt(s.base_calmar,2)),
      $('td',{class:'num'},fmt(s.filt_calmar,2))));});
  t.append(tb);bc.append($('div',{class:'tablewrap'},t));
  bc.append($('div',{class:'note'},'Same names — only the SIZING changes: extended/parabolic names are down-weighted and the shed weight sits in cash. Drawdown roughly halves at every horizon and held in both halves of the sample. You pay for it in CAGR; at 3-month it also lifts Sharpe & Calmar.'));
  w.append(bc);
  const pc=$('div',{class:'card',style:'margin-top:16px'});
  pc.append($('h3',{},'Current picks — verdicts & filter sizing ',$('span',{class:'tag warn'},`entry ${F.entry_month||'—'}`)));
  const tcol=v=>v==='regime-fit'?'up':(v==='clean'?'muted':'down');
  if((F.picks||[]).length){
    const t2=$('table');t2.append($('thead',{},$('tr',{},...['Symbol','Sector','Ext','Verdict','Base wt','Filter wt'].map(h=>$('th',{},h)))));
    const b2=$('tbody');F.picks.forEach(p=>{
      const tags=$('div',{class:'chipwrap'});(p.verdict||[]).forEach(v=>tags.append($('span',{class:'mchip',style:'color:var(--'+tcol(v)+')'},v)));
      b2.append($('tr',{},
        $('td',{},p.symbol),
        $('td',{class:'muted',style:'text-align:left;font-size:11px'},p.sector),
        $('td',{class:'num'},fmt(p.extension,1)),
        $('td',{},tags),
        $('td',{class:'num muted'},(p.base_weight*100).toFixed(0)+'%'),
        $('td',{class:'num accent'},(p.filter_weight*100).toFixed(0)+'%')));});
    t2.append(b2);pc.append($('div',{class:'tablewrap'},t2));
    pc.append($('div',{class:'kpi',style:'margin-top:10px'},
      $('span',{class:'v accent'},((F.invested_pct||0)*100).toFixed(0)+'%'),
      $('span',{class:'l'},'invested under the overlay · rest in cash (T-bills)')));
  } else pc.append($('div',{class:'muted'},'no picks'));
  pc.append($('div',{class:'note'},F.note||''));
  w.append(pc);
  return w;
};

PANELS.Surger=()=>{
  const w=$('div',{});const S=D.surger||{};
  w.append($('h2',{class:'sect-title'},'Surger Predictor'),
    $('p',{class:'lead'},'Forward 6-month surger picks from a rule + ML + AI ensemble on the FULL liquid universe. Futures-eligibility is a SEPARATE overlay (⚡ = leverageable via single-stock futures) — toggle it below. Returns mark-to-market and update daily. A wide-basket harvest: it catches ~30% of surgers out-of-sample; it does not snipe individual mega-surgers.'));
  const mc=$('div',{class:'card'});
  mc.append($('h3',{},'Live prediction ',$('span',{class:'tag warn'},`entry ${S.entry_month||'—'} · forward ${S.forward_window||''}`)));
  mc.append($('div',{class:'mono muted',style:'font-size:12px;margin-bottom:10px'},`made at ${S.entry_date||'—'} · marked to ${S.as_of||''} (${S.days_held||0}d) · universe ${S.universe_n||0} names (${S.n_eligible||0} futures-eligible)`));
  const kwrap=$('div',{class:'grid cols2'});
  kwrap.append($('div',{class:'card'},$('div',{class:'kpi'},$('span',{class:'v '+cls(S.basket_ret)},pct(S.basket_ret,1)),$('span',{class:'l'},'basket so far · all picks'))),
    $('div',{class:'card'},$('div',{class:'kpi'},$('span',{class:'v '+cls(S.basket_ret_eligible)},pct(S.basket_ret_eligible,1)),$('span',{class:'l'},'basket so far · ⚡ futures-eligible only'))));
  mc.append(kwrap);
  w.append(mc);
  const pill='font-family:var(--mono);font-size:12px;padding:4px 11px;border:1px solid var(--bd);border-radius:999px;background:var(--panel2);color:var(--ink);cursor:pointer';
  const BM=S.by_method||{};
  // per-method live basket comparison
  const cmp=$('div',{class:'card',style:'margin-top:16px'});
  cmp.append($('h3',{},'How each method is performing — live basket'));
  const ct=$('table');ct.append($('thead',{},$('tr',{},...['Method','Basket · all','Basket · ⚡ eligible'].map(h=>$('th',{},h)))));
  const ctb=$('tbody');
  ['Ensemble','Rule','ML','AI'].forEach(m=>{const d=BM[m]||{};
    ctb.append($('tr',{style:m==='Ensemble'?'background:var(--accent-soft)':''},
      $('td',{},m),$('td',{class:'num '+cls(d.basket_ret)},pct(d.basket_ret,1)),
      $('td',{class:'num '+cls(d.basket_ret_eligible)},pct(d.basket_ret_eligible,1))));});
  ct.append(ctb);cmp.append($('div',{class:'tablewrap'},ct));
  cmp.append($('div',{class:'note'},'Each model ranks the same universe independently; the ensemble rank-blends all three. They make different errors, so the blend is usually steadier than any single one.'));
  w.append(cmp);
  // picks by method — model selector + eligibility overlay toggle
  const pc=$('div',{class:'card',style:'margin-top:16px'});
  const hdr=$('div',{style:'display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px'});
  hdr.append($('h3',{style:'margin:0'},'Picks — every method'));
  let curM='Ensemble',eligOnly=false;const mbtn={};
  const sel=$('div',{class:'chipwrap'});
  ['Ensemble','Rule','ML','AI'].forEach(m=>{const b=$('button',{style:pill},m);mbtn[m]=b;
    b.onclick=()=>{curM=m;draw();};sel.append(b);});
  const eb=$('button',{style:pill},'⚡ eligible only');
  eb.onclick=()=>{eligOnly=!eligOnly;eb.textContent=eligOnly?'show all':'⚡ eligible only';draw();};
  sel.append(eb);hdr.append(sel);pc.append(hdr);
  const holder=$('div',{});pc.append(holder);
  function draw(){
    holder.innerHTML='';
    Object.entries(mbtn).forEach(([m,b])=>{b.style.borderColor=m===curM?'var(--accent)':'var(--bd)';b.style.color=m===curM?'var(--accent)':'var(--ink)';});
    const d=BM[curM]||{};let picks=(d.picks||[]);if(eligOnly)picks=picks.filter(p=>p.futures_eligible);
    const t=$('table',{style:'margin-top:12px'});
    t.append($('thead',{},$('tr',{},...['#','Sym','⚡','Sector','Entry','Now','Return','Earnings','Ens','R/ML/AI'].map(h=>$('th',{},h)))));
    const tb=$('tbody');
    const ecls=e=>e==='earnings-backed'?'up':e==='price-ahead'?'down':'muted';
    picks.forEach((p,i)=>tb.append($('tr',{},$('td',{class:'num muted'},i+1),$('td',{},$('b',{},p.symbol)),
      $('td',{style:'text-align:center'},p.futures_eligible?'⚡':''),
      $('td',{class:'muted',style:'text-align:left;font-size:11px'},p.sector),
      $('td',{class:'num muted'},p.entry_close),
      $('td',{class:'num'},p.last_close==null?'—':p.last_close),
      $('td',{class:'num '+cls(p.ret)},p.ret==null?'—':pct(p.ret,1)),
      $('td',{style:'text-align:left;font-size:10px'},$('span',{class:ecls(p.earn_read)},p.earn_read||'—'),p.eps_growth!=null?$('span',{class:'muted'},` ${p.eps_growth>0?'+':''}${p.eps_growth}%`):''),
      $('td',{class:'num accent'},p.ens),
      $('td',{class:'mono muted',style:'font-size:10px'},`${p.rule_pct}/${p.ml_pct}/${p.ai_pct}`))));
    t.append(tb);holder.append($('div',{class:'tablewrap'},t));
    const br=eligOnly?d.basket_ret_eligible:d.basket_ret;
    holder.append($('div',{class:'kpi',style:'margin-top:10px'},$('span',{class:'v '+cls(br)},pct(br,1)),
      $('span',{class:'l'},`${curM} basket · ${eligOnly?'⚡ eligible only':'all picks'}`)));
  }
  draw();
  pc.append($('div',{class:'note'},'Switch models with the chips. Columns: Ens = ensemble score; R/ML/AI = each model’s percentile rank for that name. ⚡ = futures-eligible; the toggle filters to that subset. Entry = last completed month-end; returns update daily, window rolls monthly.'));
  w.append(pc);
  // full backtest — every method & combination
  const bt=(S.backtest_methods||{}).K15||[];
  const bc=$('div',{class:'card',style:'margin-top:16px'});
  bc.append($('h3',{},'Backtest — every method & combination ',$('span',{class:'tag ok'},'walk-forward · OOS held-out half')));
  const t2=$('table');t2.append($('thead',{},$('tr',{},...['Method','Precision','Catch %','Cumulative','Max DD'].map(h=>$('th',{},h)))));
  const tb2=$('tbody');
  bt.forEach(r=>tb2.append($('tr',{style:r.m==='Rule+ML+AI'?'background:var(--accent-soft)':''},
    $('td',{},r.m),$('td',{class:'num'},r.prec+'%'),$('td',{class:'num'},r.catch+'%'),
    $('td',{class:'num accent'},r.mult),$('td',{class:'num '+cls(r.dd)},(r.dd>0?'+':'')+r.dd+'%'))));
  t2.append(tb2);bc.append($('div',{class:'tablewrap'},t2));
  bc.append($('div',{class:'note'},'6-month hold, non-overlapping, gated, held-out second half of 2019–2026 (K=15 basket). Precision base rate ~7%, so ~27% is a 3–4× edge that survives out-of-sample. No single method dominates; the ensemble adds catch-rate. (Concentrated K=5 ensembles reach 4–6× in the test half but on tiny samples — high variance.) A WIDE-basket harvest, not a sniper.'));
  w.append(bc);
  return w;
};

PANELS.Catalysts=()=>{
  const w=$('div',{});const C=D.catalysts||{};
  const pill='font-family:var(--mono);font-size:12px;padding:4px 11px;border:1px solid var(--bd);border-radius:999px;background:var(--panel2);color:var(--ink);cursor:pointer';
  w.append($('h2',{class:'sect-title'},'Live Catalysts'),
    $('p',{class:'lead'},'Material PSX announcements from the official portal (dps.psx.com.pk), last 30 days — earnings, dividends, rights/bonus, corporate actions. AWARENESS only: post-announcement drift is not tradeable on next-day entry (I tested it), so this shows WHAT was announced for you to judge — it is not an edge.'));
  const meta=$('div',{class:'card'});
  meta.append($('h3',{},'Recent announcements ',$('span',{class:'tag info'},`as of ${C.as_of||'—'} · ${C.n_total||0} in ${C.window_days||30}d`)));
  const cc=$('div',{class:'chipwrap',style:'margin-top:6px'});
  Object.entries(C.counts||{}).sort((a,b)=>b[1]-a[1]).forEach(([k,v])=>cc.append($('span',{class:'mchip'},`${k}: ${v}`)));
  meta.append(cc);w.append(meta);
  const pc=$('div',{class:'card',style:'margin-top:16px'});
  const types=['ALL','EARNINGS','DIVIDEND','RIGHTS/BONUS','CORP-ACTION','RATING'];
  let cur='ALL';const fb={};const sel=$('div',{class:'chipwrap'});
  types.forEach(t=>{const b=$('button',{style:pill},t);fb[t]=b;b.onclick=()=>{cur=t;draw();};sel.append(b);});
  pc.append(sel);const holder=$('div',{});pc.append(holder);
  function draw(){
    holder.innerHTML='';
    Object.entries(fb).forEach(([t,b])=>{b.style.borderColor=t===cur?'var(--accent)':'var(--bd)';b.style.color=t===cur?'var(--accent)':'var(--ink)';});
    const items=(C.items||[]).filter(it=>cur==='ALL'||it.type===cur);
    const t=$('table',{style:'margin-top:12px'});
    t.append($('thead',{},$('tr',{},...['Date','Sym','⚡','Type','Announcement'].map(h=>$('th',{},h)))));
    const tb=$('tbody');
    items.forEach(it=>tb.append($('tr',{},
      $('td',{class:'mono muted',style:'font-size:11px'},it.date),
      $('td',{},$('b',{},it.symbol)),
      $('td',{style:'text-align:center'},it.eligible?'⚡':''),
      $('td',{},$('span',{class:'mchip',style:'font-size:10px'},it.type)),
      $('td',{style:'text-align:left;font-size:12px'},it.title))));
    if(!items.length)tb.append($('tr',{},$('td',{colspan:'5',class:'muted'},'none in window')));
    t.append(tb);holder.append($('div',{class:'tablewrap'},t));
  }
  draw();
  pc.append($('div',{class:'note'},C.note||''));
  w.append(pc);
  return w;
};

PANELS.MacroNews=()=>{
  const w=$('div',{});const M=D.macro_live||{};const WB=M.worldbank||{};
  w.append($('h2',{class:'sect-title'},'Macro & Policy'),
    $('p',{class:'lead'},'Auto-refreshed weekly. Annual macro numbers from the World Bank (keyless, reliable) + recent Pakistan macro / policy / geopolitical headlines scraped from the business press. Keeps the terminal current on inflation, rates, IMF, budget and geopolitics without a manual reseed.'));
  const LBL={inflation_cpi_annual_pct:['Inflation (CPI)','%'],gdp_growth_pct:['GDP growth','%'],
    current_account_pctgdp:['Current account','% GDP'],reserves_usd:['FX reserves','$'],
    policy_lending_rate_pct:['Lending rate','%'],pop_millions:['Population','']};
  const nc=$('div',{class:'card'});
  nc.append($('h3',{},'Macro snapshot ',$('span',{class:'tag info'},'World Bank · annual')));
  const grid=$('div',{class:'grid cols3'});
  Object.entries(LBL).forEach(([k,[lab,unit]])=>{const v=WB[k];if(!v||v.latest==null)return;
    let val=v.latest; if(k==='reserves_usd')val='$'+(val/1e9).toFixed(1)+'b'; else if(k==='pop_millions')val=(val/1e6).toFixed(0)+'M'; else val=val+unit;
    grid.append($('div',{class:'card'},$('div',{class:'kpi'},$('span',{class:'v'},val),$('span',{class:'l'},`${lab} · ${v.latest_year}`))));});
  nc.append(grid);w.append(nc);
  const hc=$('div',{class:'card',style:'margin-top:16px'});
  hc.append($('h3',{},'Macro / policy / geopolitical headlines ',$('span',{class:'tag warn'},`as of ${M.as_of||'—'}`)));
  const hl=M.headlines||[];
  if(hl.length){const ul=$('div',{});
    hl.forEach(h=>ul.append($('div',{class:'note',style:'border-left:2px solid var(--accent);margin:6px 0;font-size:13px'},h)));
    hc.append(ul);
  } else hc.append($('div',{class:'muted'},'no headlines (refresh pending)'));
  hc.append($('div',{class:'note'},'Headlines are AWARENESS from the business press (profit.pakistantoday.com.pk) — context for the macro regime, not a trading signal. Numbers in-text are as-reported. Refreshes weekly via CI.'));
  w.append(hc);
  return w;
};

PANELS.Ultimate=()=>{
  const w=$('div',{});const U=D.ultimate||{};const BT=U.backtest||{};
  w.append($('h2',{class:'sect-title'},'Ultimate — PSX Beta Harvester'),
    $('p',{class:'lead'},'The honest winner from the whole research arc. NOT a stock-picker — a risk-managed premia harvester that beats every selection model built here, out-of-sample. It stops fighting the fat-tailed surger problem and instead extracts three robust, parameter-free edges: own the broad liquid universe (beta + small-size/rebalancing premium), weight by inverse-volatility on the low-vol half (risk parity + the low-vol anomaly), and scale exposure by the trend gate (the one validated edge). Monthly rebalance, no ML, no fitting, no look-ahead.'));
  // live positioning
  const lc=$('div',{class:'card'});
  const rs=U.risk_state||'—';
  lc.append($('h3',{},'Live positioning ',$('span',{class:'badge '+(U.exposure>=0.5?'on':'off'),style:'font-size:14px'},`${rs} · ${Math.round((U.exposure||0)*100)}% invested`)));
  lc.append($('div',{class:'mono muted',style:'font-size:12px'},`as of ${U.as_of||'—'} · universe ${U.n_universe||0} liquid names · holding ${U.n_held||0} low-vol names · ${Math.round((U.cash_pct||0)*100)}% in T-bills`));
  w.append(lc);
  // scorecard vs baselines
  const sc=$('div',{class:'card',style:'margin-top:16px'});
  sc.append($('h3',{},'Why it wins ',$('span',{class:'tag ok'},'walk-forward · OOS validated')));
  const f=BT.full||{},o=BT.oos||{};
  const kpi=(v,l,cl='')=>$('div',{class:'card'},$('div',{class:'kpi'},$('span',{class:'v '+cl},v),$('span',{class:'l'},l)));
  sc.append($('div',{class:'grid cols2'},
    kpi(f.sharpe!=null?f.sharpe.toFixed(2):'—','Sharpe (full)','accent'),
    kpi(f.calmar!=null?f.calmar.toFixed(2):'—','Calmar (full)','accent'),
    kpi(f.maxdd!=null?(f.maxdd*100).toFixed(0)+'%':'—','max drawdown'),
    kpi(f.cagr!=null?'+'+(f.cagr*100).toFixed(0)+'%':'—','CAGR (full)')));
  sc.append($('div',{class:'grid cols2',style:'margin-top:8px'},
    kpi(o.sharpe!=null?o.sharpe.toFixed(2):'—','Sharpe (OOS)','accent'),
    kpi(o.calmar!=null?o.calmar.toFixed(2):'—','Calmar (OOS)','accent'),
    kpi(o.maxdd!=null?(o.maxdd*100).toFixed(0)+'%':'—','maxDD (OOS)'),
    kpi(o.cagr!=null?'+'+(o.cagr*100).toFixed(0)+'%':'—','CAGR (OOS)')));
  const vs=BT.vs||[];
  if(vs.length){const t=$('table',{style:'margin-top:12px'});
    t.append($('thead',{},$('tr',{},...['System','Sharpe','Calmar'].map(h=>$('th',{},h)))));
    const tb=$('tbody');
    vs.forEach(r=>tb.append($('tr',{style:r.name.includes('Harvester')?'background:var(--accent-soft)':''},
      $('td',{},r.name),$('td',{class:'num'},r.sharpe.toFixed(2)),$('td',{class:'num'},r.calmar.toFixed(2)))));
    t.append(tb);sc.append($('div',{class:'tablewrap'},t));}
  sc.append($('div',{class:'note'},BT.method||''));
  w.append(sc);
  // month-by-month backtest (collapsible by year)
  const mo=U.monthly||[];
  if(mo.length){
    const mc=$('div',{class:'card',style:'margin-top:16px'});
    mc.append($('h3',{},'Backtest — month by month ',$('span',{class:'tag ok'},'realised net returns · click a year')));
    const byYear={};mo.forEach(r=>{const y=r.ym.slice(0,4);(byYear[y]=byYear[y]||[]).push(r);});
    Object.keys(byYear).sort().reverse().forEach(y=>{
      const rows=byYear[y];const yr=rows.reduce((a,r)=>a*(1+r.net),1)-1;
      const hdr=$('button',{style:'width:100%;text-align:left;font-family:var(--mono);font-size:13px;padding:8px 11px;border:1px solid var(--bd);border-radius:8px;background:var(--panel2);color:var(--ink);cursor:pointer;margin-top:6px;display:flex;justify-content:space-between;align-items:center'},
        $('span',{},`▸ ${y}  (${rows.length} mo)`),$('span',{class:'num '+cls(yr)},pct(yr,1)));
      const body=$('div',{style:'display:none'});
      const t=$('table',{style:'margin-top:6px'});
      t.append($('thead',{},$('tr',{},...['Month','Exposure','Net','Cumulative','Names'].map(h=>$('th',{},h)))));
      const tb=$('tbody');
      rows.forEach(r=>tb.append($('tr',{},$('td',{class:'mono'},r.ym),
        $('td',{class:'num muted'},Math.round(r.exposure*100)+'%'),
        $('td',{class:'num '+cls(r.net)},pct(r.net,1)),
        $('td',{class:'num '+cls(r.cum)},pct(r.cum,1)),
        $('td',{class:'num muted'},r.n))));
      t.append(tb);body.append($('div',{class:'tablewrap'},t));
      let open=false;
      hdr.onclick=()=>{open=!open;body.style.display=open?'':'none';hdr.firstChild.textContent=`${open?'▾':'▸'} ${y}  (${rows.length} mo)`;};
      mc.append(hdr,body);
    });
    mc.append($('div',{class:'note'},'Each month: the trend-gated exposure, the realised net return of the inverse-vol/low-vol book, and cumulative since inception. Net of ~0.2%/rebalance. This is the actual series behind the scorecard above — no look-ahead.'));
    w.append(mc);
  }
  // holdings
  const hc=$('div',{class:'card',style:'margin-top:16px'});
  hc.append($('h3',{},'Current book — largest weights (inverse-vol, low-vol half)'));
  const hold=U.top_holdings||[];
  if(hold.length){const t=$('table');
    t.append($('thead',{},$('tr',{},...['Symbol','Sector','Weight','Vol','Close'].map(h=>$('th',{},h)))));
    const tb=$('tbody');
    hold.forEach(h=>tb.append($('tr',{},$('td',{},$('b',{},h.symbol)),
      $('td',{class:'muted',style:'text-align:left;font-size:11px'},h.sector),
      $('td',{class:'num accent'},(h.weight*100).toFixed(1)+'%'),
      $('td',{class:'num muted'},h.vol_1m!=null?(h.vol_1m*100).toFixed(0)+'%':'—'),
      $('td',{class:'num muted'},h.close))));
    t.append(tb);hc.append($('div',{class:'tablewrap'},t));
  } else hc.append($('div',{class:'muted'},'book unavailable'));
  hc.append($('div',{class:'note'},U.note||''));
  w.append(hc);
  // sniper satellite — opportunity-gated 1-month top-5
  const SN=D.sniper||{};const SB=SN.backtest||{};const so=SN.opportunity||{};
  const snc=$('div',{class:'card',style:'margin-top:16px'});
  snc.append($('h3',{},'Sniper satellite — 1-month top-5 ',$('span',{class:'badge '+((SN.action||'').indexOf('TRADE')===0?'on':'off'),style:'font-size:13px'},SN.action||'—')));
  snc.append($('div',{class:'mono muted',style:'font-size:12px'},`entry ${SN.entry_month||'—'} · opportunity gate: dispersion ${so.dispersion} vs median ${so.disp_median} (${so.high_dispersion?'HIGH':'low'}) · ${so.risk_on?'risk-on':'risk-off'} → ${so.trade?'DEPLOY':'sit in cash'}`));
  const so2=SB.oos||{};
  const kpi2=(v,l,cl='')=>$('div',{class:'card'},$('div',{class:'kpi'},$('span',{class:'v '+cl},v),$('span',{class:'l'},l)));
  snc.append($('div',{class:'grid cols2',style:'margin-top:8px'},
    kpi2(so2.sharpe!=null?so2.sharpe.toFixed(2):'—','Sharpe (OOS)','accent'),
    kpi2(so2.calmar!=null?so2.calmar.toFixed(2):'—','Calmar (OOS)','accent'),
    kpi2(so2.maxdd!=null?(so2.maxdd*100).toFixed(0)+'%':'—','maxDD (OOS)'),
    kpi2(SB.precision!=null?(SB.precision*100).toFixed(0)+'%':'—','precision')));
  const sv=SB.vs||[];
  if(sv.length){const t=$('table',{style:'margin-top:10px'});
    t.append($('thead',{},$('tr',{},...['Variant','Sharpe','Calmar','maxDD'].map(h=>$('th',{},h)))));
    const tb=$('tbody');
    sv.forEach(r=>tb.append($('tr',{style:(r.name||'').includes('this')?'background:var(--accent-soft)':''},
      $('td',{},r.name),$('td',{class:'num'},r.sharpe.toFixed(2)),$('td',{class:'num'},r.calmar.toFixed(2)),$('td',{class:'num down'},(r.maxdd*100).toFixed(0)+'%'))));
    t.append(tb);snc.append($('div',{class:'tablewrap'},t));}
  const sp=SN.picks||[];
  if(sp.length){const t=$('table',{style:'margin-top:10px'});
    t.append($('thead',{},$('tr',{},...['#','Sym','Sector','Weight','Entry','Now','Return'].map(h=>$('th',{},h)))));
    const tb=$('tbody');
    sp.forEach(p=>tb.append($('tr',{},$('td',{class:'num muted'},p.rank),$('td',{},$('b',{},p.symbol)),
      $('td',{class:'muted',style:'text-align:left;font-size:11px'},p.sector),
      $('td',{class:'num accent'},(p.weight*100).toFixed(1)+'%'),
      $('td',{class:'num muted'},p.entry_close),$('td',{class:'num'},p.last_close==null?'—':p.last_close),
      $('td',{class:'num '+cls(p.ret)},p.ret==null?'—':pct(p.ret,1)))));
    t.append(tb);snc.append($('div',{class:'tablewrap'},t));}
  snc.append($('div',{class:'note'},SN.note||''));
  w.append(snc);
  // consensus filter — common picks across the running models (this month)
  const CN=D.consensus||{};const cr=CN.rows||[];const bk=CN.buckets||{};
  const cc=$('div',{class:'card',style:'margin-top:16px'});
  cc.append($('h3',{},'Consensus filter — common picks ',$('span',{class:'tag warn'},`this month · ${CN.n_distinct||0} names across all models`)));
  const bl=(b,lab)=>$('div',{class:'card'},$('div',{class:'kpi'},
    $('span',{class:'v '+cls(b&&b.avg)},(b&&b.avg!=null)?pct(b.avg,1):'—'),
    $('span',{class:'l'},`${lab} · ${b?b.n:0} names${(b&&b.pos!=null)?' · '+Math.round(b.pos*100)+'% up':''}`)));
  cc.append($('div',{class:'grid cols3'},bl(bk.solo,'1 model (solo)'),bl(bk.multi,'2-3 models'),bl(bk.strong,'4+ models')));
  cc.append($('div',{class:'note'},'Names only ONE model picks average negative; agreement across models removes the idiosyncratic losers. Below: every name ≥2 models agree on this month.'));
  if(cr.length){const t=$('table',{style:'margin-top:10px'});
    t.append($('thead',{},$('tr',{},...['Symbol','Sector','Models','Return','Which'].map(h=>$('th',{},h)))));
    const tb=$('tbody');
    cr.forEach(r=>tb.append($('tr',{style:r.n_models>=4?'background:var(--accent-soft)':''},
      $('td',{},$('b',{},r.symbol)),
      $('td',{class:'muted',style:'text-align:left;font-size:11px'},r.sector||'—'),
      $('td',{class:'num accent'},r.n_models),
      $('td',{class:'num '+cls(r.ret)},r.ret==null?'—':pct(r.ret,1)),
      $('td',{class:'mono muted',style:'text-align:left;font-size:10px'},(r.models||[]).join(', ')))));
    t.append(tb);cc.append($('div',{class:'tablewrap'},t));
  } else cc.append($('div',{class:'muted'},'no multi-model consensus this month'));
  cc.append($('div',{class:'note'},CN.note||''));
  w.append(cc);
  return w;
};

PANELS.Confluence=()=>{
  const w=$('div',{});const C=D.confluence||{};const rg=C.regime||{};const o=C.opportunity||{};
  const V=C.variants||{};const ORDER=['raw','conviction','combined'];const rec=C.recommended||'combined';
  const tcls=t=>t==='REAL'?'up':t==='FAKEOUT'?'down':'muted';
  const kpi=(v,l,cl='')=>$('div',{class:'card'},$('div',{class:'kpi'},$('span',{class:'v '+cl},v),$('span',{class:'l'},l)));
  w.append($('h2',{class:'sect-title'},'Confluence — Three Variants'),
    $('p',{class:'lead'},'The capstone, run three ways over the same futures-eligible universe so you can compare like-for-like. Every name is scored by how many independent edges INTERSECT — regime-fit + earnings turnaround + momentum + relative strength + liquidity — and tagged REAL (earnings-backed, hold), FAKEOUT (momentum but earnings falling — scalp with a stop) or WATCH. The three baskets differ only in how they RANK: A raw single score · B raw + earnings-conviction tilt · ★ rank-averaged momentum ensemble. Each is opportunity-gated, inverse-vol weighted, 1-month. Walk-forward 2019-2026, OOS = held-out half, no look-ahead.'));
  // shared context
  const rc=$('div',{class:'card'});
  rc.append($('h3',{},'Context & signal ',$('span',{class:'badge '+((C.action||'').indexOf('TRADE')===0?'on':'off'),style:'font-size:13px'},C.action||'—')));
  rc.append($('div',{class:'mono',style:'font-size:13px;margin:6px 0'},'regime: ',$('b',{class:rg.sign>0?'up':rg.sign<0?'down':'accent'},(rg.label||'—').toUpperCase()),rg.policy_rate!=null?`  ·  policy rate ${rg.policy_rate}%`:''));
  rc.append($('div',{class:'muted',style:'font-size:12.5px'},`favours: ${rg.favored||'—'}`));
  rc.append($('div',{class:'mono muted',style:'font-size:12px;margin-top:6px'},`opportunity gate: dispersion ${o.dispersion} vs median ${o.disp_median} · ${o.risk_on?'risk-on':'risk-off'} → ${o.trade?'DEPLOY':'sit in cash'}`));
  w.append(rc);
  // head-to-head comparison
  const cmp=$('div',{class:'card',style:'margin-top:16px'});
  cmp.append($('h3',{},'Head-to-head ',$('span',{class:'tag ok'},'OOS · no look-ahead')));
  const ct=$('table');
  ct.append($('thead',{},$('tr',{},...['Variant','Sharpe','Calmar','CAGR','maxDD','net+ mo'].map(h=>$('th',{},h)))));
  const ctb=$('tbody');
  ORDER.forEach(k=>{const v=V[k];if(!v)return;const b=(v.backtest||{}).oos||{};const pm=(v.backtest||{}).pct_pos_months;
    ctb.append($('tr',{style:k===rec?'background:var(--accent-soft)':''},
      $('td',{},$('b',{},v.label||k)),
      $('td',{class:'num '+(k===rec?'accent':'')},b.sharpe!=null?b.sharpe.toFixed(2):'—'),
      $('td',{class:'num '+(k===rec?'accent':'')},b.calmar!=null?b.calmar.toFixed(2):'—'),
      $('td',{class:'num'},b.cagr!=null?'+'+(b.cagr*100).toFixed(0)+'%':'—'),
      $('td',{class:'num down'},b.maxdd!=null?(b.maxdd*100).toFixed(0)+'%':'—'),
      $('td',{class:'num'},pm!=null?(pm*100).toFixed(0)+'%':'—')));});
  ct.append(ctb);cmp.append($('div',{class:'tablewrap'},ct));
  cmp.append($('div',{class:'note'},'The momentum ENSEMBLE (★ Combined) is the honest out-of-sample winner and lowers drawdown — robust across basket size (K=5/8/10) and split point. The earnings tilt (B) barely beats raw once timed with point-in-time EPS; its larger live edge relies on a current EPS snapshot that cannot be backtested without look-ahead. So ★ ranks on momentum and keeps earnings as a conviction tag.'));
  w.append(cmp);
  // shared high-conviction set
  const hc=$('div',{class:'card',style:'margin-top:16px'});
  hc.append($('h3',{},`High-conviction set — ${C.n_conviction||0} names, 3+ edges aligned`));
  const hv=C.high_conviction||[];
  if(hv.length){const t=$('table');
    t.append($('thead',{},$('tr',{},...['Symbol','Tag','Edges','EPS gr','Sector','Aligned'].map(h=>$('th',{},h)))));
    const tb=$('tbody');
    hv.forEach(r=>tb.append($('tr',{style:r.tag==='REAL'?'background:var(--accent-soft)':''},
      $('td',{},$('b',{},r.symbol)),$('td',{},$('span',{class:tcls(r.tag)},r.tag)),
      $('td',{class:'num accent'},r.confluence),
      $('td',{class:'num '+cls(r.eps_growth)},r.eps_growth==null?'—':(r.eps_growth>0?'+':'')+r.eps_growth+'%'),
      $('td',{class:'muted',style:'text-align:left;font-size:11px'},r.sector),
      $('td',{class:'mono muted',style:'text-align:left;font-size:10px'},(r.edges||[]).join(', ')))));
    t.append(tb);hc.append($('div',{class:'tablewrap'},t));}
  hc.append($('div',{class:'note'},'Shared across all three variants. REAL = earnings-backed (hold). FAKEOUT = momentum but earnings falling (scalp with a stop, do not hold). WATCH = mixed.'));
  w.append(hc);
  // per-variant sections
  const section=(k)=>{const v=V[k];if(!v)return;
    const b=(v.backtest||{}).oos||{};const bt=v.backtest||{};const isRec=(k===rec);
    const card=$('div',{class:'card',style:'margin-top:16px'+(isRec?';border:1px solid var(--accent)':'')});
    card.append($('h3',{},(v.label||k)+' ',
      isRec?$('span',{class:'tag ok'},'recommended'):'',
      $('span',{class:'tag warn',style:'margin-left:6px'},`entry ${C.entry_month||'—'} · basket ${v.basket_ret==null?'—':pct(v.basket_ret,1)}`)));
    card.append($('div',{class:'grid cols2'},
      kpi(b.sharpe!=null?b.sharpe.toFixed(2):'—','Sharpe (OOS)',isRec?'accent':''),
      kpi(b.calmar!=null?b.calmar.toFixed(2):'—','Calmar (OOS)',isRec?'accent':''),
      kpi(b.cagr!=null?'+'+(b.cagr*100).toFixed(0)+'%':'—','CAGR (OOS)'),
      kpi(bt.pct_pos_months!=null?(bt.pct_pos_months*100).toFixed(0)+'%':'—','net+ months (traded)',isRec?'accent':'')));
    const bk=v.picks||[];
    if(bk.length){const t=$('table');
      t.append($('thead',{},$('tr',{},...['#','Sym','Tag','Weight','EPS gr','Entry','Now','Return'].map(h=>$('th',{},h)))));
      const tb=$('tbody');
      bk.forEach(p=>tb.append($('tr',{},$('td',{class:'num muted'},p.rank),$('td',{},$('b',{},p.symbol)),
        $('td',{},$('span',{class:tcls(p.tag)},p.tag)),
        $('td',{class:'num accent'},(p.weight*100).toFixed(1)+'%'),
        $('td',{class:'num '+cls(p.eps_growth)},p.eps_growth==null?'—':(p.eps_growth>0?'+':'')+p.eps_growth+'%'),
        $('td',{class:'num muted'},p.entry_close),$('td',{class:'num'},p.last_close==null?'—':p.last_close),
        $('td',{class:'num '+cls(p.ret)},p.ret==null?'—':pct(p.ret,1)))));
      t.append(tb);card.append($('div',{class:'tablewrap'},t));}
    card.append($('div',{class:'note'},bt.method||''));
    w.append(card);};
  ORDER.forEach(section);
  // overall note
  const nc=$('div',{class:'card',style:'margin-top:16px'});
  nc.append($('div',{class:'note'},C.note||''));
  w.append(nc);
  return w;
};

PANELS.Picker=()=>{
  const w=$('div',{});const C=D.picker||{};const S=C.summary||{};const cur=C.current||null;
  const ORDER=['turnaround','leaders','quality','combined'];const rec=C.recommended||'combined';
  const LAB={turnaround:'A · Turnaround',leaders:'B · Leaders',quality:'C · Mom-quality',combined:'★ Combined'};
  const tcls=t=>t==='REAL'?'up':t==='FADING'?'down':'muted';
  w.append($('h2',{class:'sect-title'},'Picker — Year-End Race'),
    $('p',{class:'lead'},'Which names surge most over a CALENDAR YEAR — picked once at the start of the year on prior-year data only, held to Dec 31, and tested year-by-year (the honest way to judge a "top surger of the year" model). Full liquid universe, top-15 equal-weight (upside, not risk-parity). Three framework styles — Turnaround (beaten-down, bouncing), Leaders (momentum + rel-strength), Mom-quality (low-vol quality-momentum) — plus a rank-averaged Combined. Honest result below: no style reliably beats owning the whole liquid universe; the winning style rotates with the regime; and top-decile hit-rate ≈ the 10% base rate, so this is a diversified, regime-aware candidate list, NOT a single-surger sniper.'));
  if(!C.annual||!C.annual.length){w.append($('div',{class:'card muted'},C.note||'picker unavailable'));return w;}
  // summary head-to-head
  const cmp=$('div',{class:'card'});
  cmp.append($('h3',{},'Year-by-year summary ',$('span',{class:'tag ok'},`${S.n_years||0} years · no look-ahead`)));
  const ct=$('table');
  ct.append($('thead',{},$('tr',{},...['Style','Mean annual','Compounded','Beat universe','Top-decile hit'].map(h=>$('th',{},h)))));
  const ctb=$('tbody');
  ctb.append($('tr',{style:'border-bottom:2px solid var(--border)'},$('td',{},$('b',{},'Universe (equal-wt)')),
    $('td',{class:'num'},S.univ_mean!=null?pct(S.univ_mean,0):'—'),
    $('td',{class:'num'},S.univ_comp!=null?S.univ_comp.toFixed(1)+'x':'—'),
    $('td',{class:'num muted'},'—'),$('td',{class:'num muted'},'10%')));
  ORDER.forEach(k=>{const v=S[k]||{};const isRec=(k===rec);
    ctb.append($('tr',{style:isRec?'background:var(--accent-soft)':''},
      $('td',{},$('b',{},LAB[k])),
      $('td',{class:'num '+(isRec?'accent':'')},v.mean!=null?pct(v.mean,0):'—'),
      $('td',{class:'num '+(isRec?'accent':'')},v.comp!=null?v.comp.toFixed(1)+'x':'—'),
      $('td',{class:'num'},v.beat_rate!=null?(v.beat_rate*100).toFixed(0)+'% of yrs':'—'),
      $('td',{class:'num '+(v.hit_rate>0.10?'up':'muted')},v.hit_rate!=null?(v.hit_rate*100).toFixed(0)+'%':'—')));});
  ct.append(ctb);cmp.append($('div',{class:'tablewrap'},ct));
  cmp.append($('div',{class:'note'},'Compounded = growth of an annually-rebalanced top-15 over the test window. Beat-universe = share of years the style beat the equal-weight liquid universe. Top-decile hit = share of the 15 picks that landed in that year\'s top-10% surgers (10% = pure chance). None of the styles clears the universe convincingly, and hit-rate sits at chance — the edge over just owning the market is small and regime-dependent.'));
  w.append(cmp);
  // risk-adjusted (monthly path)
  const RK=S.risk||{};
  if(RK.univ){
    const rc=$('div',{class:'card',style:'margin-top:16px'});
    rc.append($('h3',{},'Risk-adjusted ',$('span',{class:'tag warn'},`monthly path · ${RK.univ.n||''} mo`)));
    const rt=$('table');
    rt.append($('thead',{},$('tr',{},...['Style','CAGR','Volatility','Sharpe','maxDD','Calmar'].map(h=>$('th',{},h)))));
    const rtb=$('tbody');
    const rrow=(key,lab,hl)=>{const d=RK[key]||{};if(!d.sharpe&&d.sharpe!==0)return;
      rtb.append($('tr',{style:hl?'background:var(--accent-soft)':(key==='univ'?'border-bottom:2px solid var(--border)':'')},
        $('td',{},$('b',{},lab)),
        $('td',{class:'num'},d.cagr!=null?pct(d.cagr,0):'—'),
        $('td',{class:'num'},d.vol!=null?(d.vol*100).toFixed(0)+'%':'—'),
        $('td',{class:'num '+(d.sharpe>=0.5?'up':'down')},d.sharpe!=null?d.sharpe.toFixed(2):'—'),
        $('td',{class:'num down'},d.maxdd!=null?(d.maxdd*100).toFixed(0)+'%':'—'),
        $('td',{class:'num'},d.calmar!=null?d.calmar.toFixed(2):'—')));};
    rrow('univ','Universe (equal-wt)',false);
    ORDER.forEach(k=>rrow(k,LAB[k],k===rec));
    rt.append(rtb);rc.append($('div',{class:'tablewrap'},rt));
    rc.append($('div',{class:'note'},'The honest cost of chasing year-end surgers: buying a concentrated top-15 each January and holding the whole year — no rebalance, no gate — means you eat the full drawdowns. Sharpe ≈ 0.2-0.3 and maxDD −45% to −57%, and no style beats just owning the universe risk-adjusted. If you care about risk-adjusted return rather than raw year-end upside, the monthly-rebalanced, opportunity-gated Confluence / Ultimate tabs are far better (Sharpe ~1.2-1.5). Picker answers "who surges most by Dec 31", not "what is the smoothest ride".'));
    w.append(rc);
  }
  // annual table
  const ac=$('div',{class:'card',style:'margin-top:16px'});
  ac.append($('h3',{},'Full-year return of the top-15, by year'));
  const at=$('table');
  at.append($('thead',{},$('tr',{},...['Year','Universe','Turn','Lead','Qual','Comb','Winner'].map(h=>$('th',{},h)))));
  const atb=$('tbody');
  const short={turnaround:'Turn',leaders:'Lead',quality:'Qual',combined:'Comb'};
  C.annual.forEach(r=>{
    const cell=k=>$('td',{class:'num '+(k===r.winner?'up':cls(r[k]))+(k===r.winner?' accent':'')},r[k]!=null?pct(r[k],0):'—');
    atb.append($('tr',{},$('td',{class:'num muted'},r.year),
      $('td',{class:'num '+cls(r.univ)},r.univ!=null?pct(r.univ,0):'—'),
      cell('turnaround'),cell('leaders'),cell('quality'),cell('combined'),
      $('td',{class:'accent',style:'text-align:left;font-size:11px'},short[r.winner]||r.winner)));});
  at.append(atb);ac.append($('div',{class:'tablewrap'},at));
  ac.append($('div',{class:'note'},'The winner rotates: Turnaround leads recovery/choppy years, Mom-quality loses least in down years, Leaders/Combined win strong bulls. No single style is best every year — matching the style to the regime is the only real lever.'));
  w.append(ac);
  // this year's live picks
  if(cur&&cur.variants){
    const hc=$('div',{class:'card',style:'margin-top:16px'});
    hc.append($('h3',{},`${cur.year} picks — entry ${cur.entry_month}, held to ${cur.as_of} `,
      $('span',{class:'tag warn'},`universe YTD ${cur.universe_ytd==null?'—':pct(cur.universe_ytd,0)}`)));
    hc.append($('div',{class:'note'},'This year\'s actual start-of-year picks (chosen on Dec data, no hindsight) marked to today. A live, honest read — not a backtest. In a down/choppy year the Turnaround style tends to hold up best; in a strong bull the momentum styles lead.'));
    w.append(hc);
    ORDER.forEach(k=>{const v=cur.variants[k];if(!v)return;const isRec=(k===rec);
      const card=$('div',{class:'card',style:'margin-top:12px'+(isRec?';border:1px solid var(--accent)':'')});
      card.append($('h3',{},(v.label||LAB[k])+' ',
        isRec?$('span',{class:'tag ok'},'all-weather pick'):'',
        $('span',{class:'tag warn',style:'margin-left:6px'},`basket YTD ${v.basket_ytd==null?'—':pct(v.basket_ytd,0)}`)));
      const bk=v.picks||[];
      if(bk.length){const t=$('table');
        t.append($('thead',{},$('tr',{},...['#','Sym','Sector','EPS tag','Entry','Now','YTD'].map(h=>$('th',{},h)))));
        const tb=$('tbody');
        bk.forEach(p=>tb.append($('tr',{},$('td',{class:'num muted'},p.rank),$('td',{},$('b',{},p.symbol)),
          $('td',{class:'muted',style:'text-align:left;font-size:11px'},p.sector),
          $('td',{},$('span',{class:tcls(p.tag)},p.tag)),
          $('td',{class:'num muted'},p.entry_close==null?'—':p.entry_close),
          $('td',{class:'num'},p.last_close==null?'—':p.last_close),
          $('td',{class:'num '+cls(p.ytd)},p.ytd==null?'—':pct(p.ytd,1)))));
        t.append(tb);card.append($('div',{class:'tablewrap'},t));}
      w.append(card);});
  }
  // forward + overall notes
  const fc=$('div',{class:'card',style:'margin-top:16px'});
  fc.append($('h3',{},'Forward test — the parts we can\'t backtest ',$('span',{class:'tag warn'},'paper ledger')));
  fc.append($('div',{class:'note'},C.forward_note||''));
  w.append(fc);
  const nc=$('div',{class:'card',style:'margin-top:16px'});
  nc.append($('div',{class:'note'},C.note||''));
  w.append(nc);
  return w;
};

/* ---------- shell ---------- */
const TABS=[['Regime',PANELS.Regime],['Ultimate',PANELS.Ultimate],['Confluence',PANELS.Confluence],['Picker',PANELS.Picker],['Strategy',PANELS.Strategy],['Surger',PANELS.Surger],['Catalysts',PANELS.Catalysts],['MacroNews',PANELS.MacroNews],['Mood',PANELS.Mood],['Sectors',PANELS.Sectors],
  ['Surges',PANELS.Surges],['Predictor',PANELS.Predictor],['Futures',PANELS.Futures],['Filter',PANELS.Filter],
  ['Interconnections',PANELS.Interconnections],['Macro',PANELS.Macro],['Sovereign',PANELS.Sovereign],
  ['Fundamentals',PANELS.Fundamentals],['Correlations',PANELS.Correlations],['Events',PANELS.Events],
  ['Sentiment',PANELS.Sentiment],['Method',PANELS.Method]];
const tabsEl=document.getElementById('tabs'),mainEl=document.getElementById('main');
const rendered={};
function show(name){for(const b of tabsEl.children)b.setAttribute('aria-selected',b.dataset.t===name);
  for(const p of mainEl.children)p.classList.toggle('active',p.dataset.t===name);
  if(!rendered[name]){const p=$('div',{class:'panel active','data-t':name});p.append(TABS.find(t=>t[0]===name)[1]());
    mainEl.append(p);rendered[name]=true;}location.hash=name;}
TABS.forEach(([n])=>tabsEl.append($('button',{'data-t':n,role:'tab',onclick:()=>show(n)},n)));

// header fills
const rt=D.regime.timing;
document.getElementById('regimeChip').innerHTML=`<span class="dot" style="${rt.signal==='RISK-ON'?'':'background:var(--down)'}"></span> ${rt.signal} · ${(rt.exposure*100).toFixed(0)}%`;
document.getElementById('asOf').textContent='as of '+D.meta.as_of;
document.getElementById('coverage').textContent=`${D.meta.n_symbols} symbols · ${D.meta.n_months} mo`;
// ticker
const S=D.macro.series;const last=k=>S[k]?S[k].y[S[k].y.length-1]:null;
const ticks=[['POLICY',last('policy_rate'),'%'],['CPI YoY',last('cpi_yoy'),'%'],['PKR/USD',last('pkr_usd'),''],
  ['RESERVES',last('fx_reserves_sbp_bn'),'$bn'],['REMIT',last('remittances_bn'),'$bn'],['BRENT',last('brent_usd'),'$'],
  ['INDEX',D.index.level_daily.y[D.index.level_daily.y.length-1],'x'],['REGIME',rt.signal,'']];
const track=document.getElementById('tickTrack');
const mk=()=>ticks.forEach(([l,v,u])=>track.append($('span',{class:'tk'},l+' ',$('b',{},(typeof v==='number'?v.toFixed(u==='x'?2:v>100?0:1):v)+u))));
mk();mk();
// theme toggle
const tb=document.getElementById('themeBtn');
tb.addEventListener('click',()=>{const cur=document.documentElement.getAttribute('data-theme');
  const mq=matchMedia('(prefers-color-scheme:dark)').matches;
  const next=cur? (cur==='dark'?'light':'dark') : (mq?'light':'dark');
  document.documentElement.setAttribute('data-theme',next);});
// initial
show(location.hash?decodeURIComponent(location.hash.slice(1)):'Regime');
</script>
"""


if __name__ == "__main__":
    build()
