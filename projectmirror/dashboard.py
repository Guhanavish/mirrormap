"""Standalone interactive, offline, data-only audit atlas.

No CDN, telemetry, network fetch, source execution, or external assets.
Untrusted project strings are embedded as escaped JSON and rendered via textContent.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
from pathlib import Path

MAX_GRAPH_FINDINGS = 120
MAX_EMBED_NODES = 1200

_CSS = r'''
:root{color-scheme:dark;--bg:#0b1317;--panel:#142126;--panel2:#1a292e;--line:#30434a;--text:#ecf5ef;--muted:#9ab3ad;--mint:#9cddbb;--green:#4cb892;--pink:#f4a4aa;--gold:#e1bd80;--violet:#a6b8e7;font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(156deg,#0d1e22 0%,#0b1317 42%,#142421 100%);min-height:100vh;color:var(--text);line-height:1.5}
button,input,select{font:inherit}button{cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible,[tabindex]:focus-visible{outline:3px solid var(--mint);outline-offset:3px}
.site{max-width:1560px;margin:auto;padding:24px clamp(14px,3vw,40px) 70px}
.top{display:flex;align-items:center;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding:10px 0 24px;flex-wrap:wrap}
.logo{display:flex;align-items:center;gap:12px;font-weight:780;letter-spacing:-.045em;font-size:23px}.mark{width:32px;height:32px;border:2px solid var(--mint);border-radius:11px;display:grid;place-items:center;color:var(--mint);transform:rotate(-12deg)}.mark span{transform:rotate(12deg)}
.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}.eyebrow{color:var(--mint);font-size:11px;font-weight:730;letter-spacing:.19em;text-transform:uppercase}h1{letter-spacing:-.055em;font-weight:780;font-size:clamp(33px,5vw,62px);line-height:1.1;margin:24px 0 9px}h2{font-size:18px;letter-spacing:-.02em}
.muted{color:var(--muted)}.sub{max-width:740px;margin:0 0 24px}.meta{font-size:12px;color:var(--muted);overflow-wrap:anywhere}
.stats{display:flex;gap:9px;flex-wrap:wrap;margin:24px 0}.stat{border:1px solid var(--line);border-radius:12px;background:#17252a;padding:12px 18px;min-width:115px;flex:1}.stat strong{display:block;font-size:27px;line-height:1.1}.stat span{color:var(--muted);font-size:11px;letter-spacing:.055em;text-transform:uppercase}
.layout{display:grid;grid-template-columns:minmax(235px,300px) minmax(0,1fr);gap:14px;align-items:start}.panel{border:1px solid var(--line);background:var(--panel);border-radius:16px;overflow:hidden}
.sidebar{position:sticky;top:10px}.panelhead{padding:15px 18px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:9px}.panelhead h2{margin:0}.controls{padding:12px}.search{width:100%;background:#0e1a1f;color:var(--text);padding:12px 13px;border:1px solid #41565c;border-radius:10px}
.filters{display:flex;gap:5px;flex-wrap:wrap;margin:11px 0}.filter{border:1px solid var(--line);background:transparent;color:var(--muted);border-radius:999px;padding:6px 10px;font-size:12px}.filter[aria-pressed=true]{border-color:var(--mint);color:var(--mint);background:#1c3732}
.results{max-height:570px;overflow:auto}.finding{width:100%;border:0;border-left:3px solid transparent;border-bottom:1px solid #26383e;padding:12px 14px;text-align:left;display:block;background:transparent;color:var(--text)}.finding:hover,.finding[aria-current=true]{background:#203238;border-left-color:var(--mint)}.finding strong{font-size:13px;display:block;overflow-wrap:anywhere}.finding small{color:var(--muted);font-size:11px}.pill{display:inline-block;padding:2px 7px;font-size:10px;border-radius:6px;border:1px solid var(--line);background:#26363c;margin-right:5px;font-weight:680;text-transform:uppercase;letter-spacing:.04em}
.pill.complete{border-color:#387d63;color:#a3ead1}.pill.missing,.pill.broken,.pill.mismatch{border-color:#995860;color:#ffabb7}.pill.partial,.pill.spec_conflict{border-color:#92714b;color:#f4d2a4}.pill.unverified,.pill.unknown{border-color:#5f7786;color:#bed1de}.pill.undocumented{border-color:#796e9a;color:#d1c7f6}
.canvasControls{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.toggle{color:var(--mint);border:1px solid #3a6459;border-radius:9px;background:#1b3431;padding:7px 11px;font-size:12px}.toggle[aria-pressed=false]{color:var(--muted);background:transparent;border-color:var(--line)}
.canvas{overflow:auto;max-height:650px;background-image:radial-gradient(#40605b50 .75px,transparent .75px);background-size:18px 18px;min-height:300px}.canvas svg{display:block;min-width:900px;max-width:none}.canvas svg g[role=button]{cursor:pointer}.canvas svg g[role=button]:focus-visible rect{stroke:#fff;stroke-width:3}.empty{padding:45px 20px;text-align:center;color:var(--muted)}.details{padding:18px;border-top:1px solid var(--line)}.details h2{margin:0 0 5px}.details p{margin:7px 0;font-size:13px}.detailGrid{display:grid;grid-template-columns:110px 1fr;gap:7px 12px;font-size:12px;overflow-wrap:anywhere}.detailGrid dt{color:var(--muted)}.detailGrid dd{margin:0}.evidence{margin-top:13px;padding:12px;background:#0e2024;border-radius:9px;border:1px solid var(--line)}.evidence li{font-size:12px;overflow-wrap:anywhere;margin:4px 0}
.notice{padding:12px 16px;border:1px solid #715f43;border-radius:12px;color:#eed5aa;background:#342d21;margin:14px 0 18px;font-size:13px}.foot{margin-top:23px;font-size:12px;color:var(--muted)}.foot code{color:var(--mint)}
@media(max-width:860px){.layout{grid-template-columns:1fr}.sidebar{position:static}.results{max-height:240px}}@media(prefers-reduced-motion:no-preference){.finding,.filter,.toggle{transition:background .18s,border-color .18s}}@media print{.canvasControls,.filters,.search{display:none}.canvas{max-height:none;overflow:visible}.results{max-height:none}.layout{display:block}.sidebar{page-break-after:always}body{background:white;color:black}.panel,.stat{background:white;color:black}}
'''
_JS = r'''
'use strict';
const data = JSON.parse(document.getElementById('atlas-data').textContent);
const $ = id => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
let search='', status='all', zoom=1, view='map', selectedId=null;
const findings = Array.isArray(data.findings) ? data.findings : [];
const implementations = new Map((data.implementation || []).map(n=>[n.id,n]));
const observations = new Map((data.verification || []).map(n=>[n.id,n]));
function el(tag,text,cls){const x=document.createElement(tag);if(cls)x.className=cls;if(text!==undefined)x.textContent=String(text);return x;}
function svg(tag,attrs){const x=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs||{}))x.setAttribute(k,String(v));return x;}
const COLORS={complete:'#72ceae',missing:'#f19ba6',broken:'#f19ba6',mismatch:'#f19ba6',partial:'#e6bd80',spec_conflict:'#e6bd80',unverified:'#9db3c7',unknown:'#9db3c7',undocumented:'#a9a0d7'};
const color=f=>COLORS[f.classification]||'#9db3c7';
function visible(){return findings.filter(f => (status==='all'||f.classification===status) && ([f.title,f.id,f.classification,f.reason].join(' ').toLowerCase().includes(search.toLowerCase())));}
function select(id){selectedId=id; renderList();renderDetails(); if(view==='map')renderMap();}
function pill(cls){return el('span',cls,'pill '+cls);}
function renderList(){
 const list=$('results'); list.replaceChildren();const fs=visible();$('resultCount').textContent=fs.length+' shown';
 if(!fs.length){list.append(el('p','No matching findings. Change your search or filter.','empty'));return;}
 for(const f of fs){const b=el('button',undefined,'finding');b.type='button';b.setAttribute('aria-current',String(f.id===selectedId));
 const label=el('strong');label.append(pill(f.classification));label.append(document.createTextNode(f.title||f.id));b.append(label,el('small',f.id));b.addEventListener('click',()=>select(f.id));list.append(b);}
}
function renderDetails(){const holder=$('details');holder.replaceChildren();const f=findings.find(x=>x.id===selectedId);
 if(!f){holder.append(el('p','Select a requirement or graph node to inspect its evidence.','muted'));return;}
 const h=el('h2',f.title||f.id);holder.append(h,pill(f.classification),el('p',f.reason||''));
 const info=el('dl',undefined,'detailGrid');for(const [k,v] of [['Finding ID',f.id],['Requirement ID',f.requirement_id||'Unmapped'],['Scope',f.scope||'Unknown'],['Implementations',(f.implementation_ids||[]).length],['Observations',(f.verification_ids||[]).length]]){info.append(el('dt',k),el('dd',v));}holder.append(info);
 const evidence=el('div',undefined,'evidence');evidence.append(el('strong','Linked evidence & source references'));
 const ul=el('ul');const ev=(f.evidence||[]).slice(0,30);if(!ev.length)ul.append(el('li','No direct evidence attached to this finding.'));else for(const e of ev)ul.append(el('li',e));
 for(const id of (f.implementation_ids||[]).slice(0,10)){const item=implementations.get(id);if(item)ul.append(el('li','Code: '+(item.locator||item.title||id)));}
 for(const id of (f.verification_ids||[]).slice(0,10)){const item=observations.get(id);if(item)ul.append(el('li','Test: '+(item.title||id)+' — '+(item.result||'unknown')));}
 evidence.append(ul);holder.append(evidence);
}
function clip(s,n=32){s=String(s||'');return s.length>n?s.slice(0,n-1)+'…':s;}
function rectGroup(x,y,w,h,text,outline,kind,callback){
 const g=svg('g',{role:'button',tabindex:0,'aria-label':kind+': '+text});
 g.append(svg('rect',{x,y,width:w,height:h,rx:11,fill:'#192b2d',stroke:outline,'stroke-width':1.5}));
 const t=svg('text',{x:x+12,y:y+24,fill:'#e4f3e9','font-size':12,'font-weight':650});t.textContent=clip(text,w>250?40:30);g.append(t);
 const sub=svg('text',{x:x+12,y:y+42,fill:outline,'font-size':10});sub.textContent=kind;g.append(sub);
 if(callback){g.addEventListener('click',callback);g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();callback();}});}
 return g;
}
function renderMap(){
 const holder=$('canvas');holder.replaceChildren();let fs=visible();const total=fs.length;fs=fs.slice(0,data.graph_limit||120);
 if(!fs.length){holder.append(el('p','No graph nodes match your current filters.','empty'));return;}
 const w=1080, step=77;
 const heightFor=f=>Math.max(1,Math.min(3,(f.implementation_ids||[]).length),Math.min(3,(f.verification_ids||[]).length))*step+16;
 const heights=fs.map(heightFor);
 const h=Math.max(360,heights.reduce((a,b)=>a+b,0)+100);
 const board=svg('svg',{viewBox:`0 0 ${w} ${h}`,width:w*zoom,height:h*zoom,role:'img','aria-label':'Three-lane evidence graph showing named requirement, implementation and verification nodes'});
 for(const [label,x] of [['01  INTENT',30],['02  IMPLEMENTATION',400],['03  VERIFICATION',770]]){
  const t=svg('text',{x,y:35,fill:'#b1c9c3','font-size':13,'font-weight':'700','letter-spacing':'1.5'});t.textContent=label;board.append(t);}
 const edges=svg('g',{'stroke-width':1.4,fill:'none','stroke-opacity':.75});const nodes=svg('g');
 let y=65;
 fs.forEach((f,i)=>{
   const height=heights[i],reqY=y+(height-59)/2,reqMid=reqY+29.5;
   const outline=selectedId===f.id?'#d3f7d9':color(f);
   const implIds=f.implementation_ids||[],testIds=f.verification_ids||[];
   const impls=implIds.length?implIds.slice(0,3).map(id=>implementations.get(id)||{id,title:id}):[null];
   const tests=testIds.length?testIds.slice(0,3).map(id=>observations.get(id)||{id,title:id}):[null];
   const pick=()=>select(f.id);
   nodes.append(rectGroup(30,reqY,294,59,f.title||f.id,outline,f.classification.toUpperCase(),pick));
   impls.forEach((node,j)=>{
     const yy=y+j*step,mid=yy+29.5;
     edges.append(svg('path',{d:`M 324 ${reqMid} C 363 ${reqMid} 361 ${mid} 400 ${mid}`,stroke:node?'#7dbda5':'#586b71','stroke-dasharray':node?'none':'4 4'}));
     nodes.append(rectGroup(400,yy,304,59,node?(node.title||node.locator||node.id):'No reviewed code link',node?'#75bc9e':'#576f79',node?'CODE · '+(j+1):'IMPLEMENTATION',pick));
   });
   tests.forEach((node,j)=>{
     const yy=y+j*step,mid=yy+29.5;
     // This line groups observations by requirement; it does NOT assert test-to-source execution coverage.
     edges.append(svg('path',{d:`M 704 ${reqMid} C 743 ${reqMid} 739 ${mid} 770 ${mid}`,stroke:node?'#9ccabb':'#586b71','stroke-dasharray':'4 4'}));
     nodes.append(rectGroup(770,yy,280,59,node?(node.title||node.id):'No test observation',node?'#9ccabb':'#576f79',node?'TEST · '+String(node.result||'unknown').toUpperCase():'VERIFICATION',pick));
   });
   if(implIds.length>3||testIds.length>3){const count=svg('text',{x:390,y:y+height-7,fill:'#99bdb3','font-size':10});count.textContent=(implIds.length>3?`+${implIds.length-3} more code links `:'')+(testIds.length>3?`+${testIds.length-3} more observations`:'');nodes.append(count);}
   y+=height;
 });board.append(edges,nodes);holder.append(board);
 $('graphCount').textContent=`${fs.length} of ${total} findings graphed`+(total>fs.length?' • limited for performance':'');
}

function update(){renderList();renderDetails();renderMap();}
function filters(){const place=$('filters');place.replaceChildren();const classes=['all',...Object.keys(data.counts||{})];for(const cls of classes){const btn=el('button',cls==='all'?'All':cls.replaceAll('_',' '),'filter');btn.type='button';btn.setAttribute('aria-pressed',String(status===cls));btn.addEventListener('click',()=>{status=cls;filters();update();});place.append(btn);}}
$('search').addEventListener('input',ev=>{search=ev.target.value;update();});
$('zoom').addEventListener('input',ev=>{zoom=Number(ev.target.value)/100;renderMap();});
$('focusAll').addEventListener('click',()=>{search='';status='all';$('search').value='';filters();update();});
$('resetZoom').addEventListener('click',()=>{$('zoom').value='100';zoom=1;renderMap();});
filters();selectedId=findings[0]?.id||null;update();
'''


def write_dashboard(out: Path, title: str, findings: dict, manifest: dict,
                    implementation: dict | None = None, verification: dict | None = None) -> Path:
    """Write an offline, graph-driven dashboard. No external assets or network calls."""
    def h(value: object) -> str:
        return html.escape(str(value), quote=True)
    fs = findings.get('findings', [])
    if not isinstance(fs, list):
        fs = []
    linked_impl = {id for f in fs for id in f.get('implementation_ids', [])}
    linked_ver = {id for f in fs for id in f.get('verification_ids', [])}
    source_nodes = (implementation or {}).get('nodes', [])
    check_nodes = (verification or {}).get('nodes', [])
    selected_impl = [n for n in source_nodes if n.get('id') in linked_impl][:MAX_EMBED_NODES]
    selected_ver = [n for n in check_nodes if n.get('id') in linked_ver][:MAX_EMBED_NODES]
    payload = {'findings': fs, 'counts': findings.get('counts', {}),
               'implementation': selected_impl, 'verification': selected_ver,
               'graph_limit': MAX_GRAPH_FINDINGS}
    # Prevent untrusted JSON from terminating the data script block.
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026').replace('\u2028', '\\u2028').replace('\u2029','\\u2029')
    script_hash = base64.b64encode(hashlib.sha256(_JS.encode('utf-8')).digest()).decode('ascii')
    csp = f"default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'"
    stats = ''.join(f'<div class="stat"><strong>{int(v)}</strong><span>{h(k)}</span></div>' for k,v in sorted(findings.get('counts', {}).items()))
    if not stats:
        stats = '<div class="stat"><strong>0</strong><span>Classified findings</span></div>'
    repo = manifest.get('project', {}).get('repo') or 'unknown'
    sha = manifest.get('project', {}).get('revision') or 'unversioned'
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{h(csp)}"><meta name="color-scheme" content="dark"><title>MirrorMap | {h(title)}</title>
<style>{_CSS}</style></head><body><div class="site">
<header class="top"><div class="logo"><div class="mark"><span>◇</span></div>Mirror<span style="color:var(--mint)">Map</span></div><div class="eyebrow">Offline evidence atlas / interactive view</div></header>
<h1>{h(title)}</h1><p class="sub muted">Trace each approved requirement through source evidence and observed tests. Search, filter, zoom and inspect connections—without installing a dashboard server.</p>
<div class="meta">Repository: {h(repo)}<br>Revision: <span class="mono">{h(sha)}</span></div>
<div class="stats" aria-label="Finding counts">{stats}</div>
<p class="notice">Graph lines group evidence by requirement, not direct test-to-code coverage. A mapped file is not proof of working behavior. JUnit reports are not executed here. Unknown does not mean missing, and this dashboard does not approve or make code changes.</p>
<div class="layout"><aside class="panel sidebar" aria-label="Findings"><div class="panelhead"><h2>Findings</h2><span class="muted" id="resultCount" aria-live="polite"></span></div>
<div class="controls"><label for="search" class="eyebrow">Search the atlas</label><input id="search" class="search" type="search" placeholder="Find feature, ID or issue…" autocomplete="off"><div id="filters" class="filters" aria-label="Filter by status"></div><button class="toggle" id="focusAll" type="button">Clear filters</button></div><div id="results" class="results"></div></aside>
<main class="panel"><div class="panelhead"><h2>Evidence connections</h2><div class="canvasControls"><span class="muted" id="graphCount"></span><label for="zoom" class="muted">Zoom</label><input id="zoom" type="range" min="60" max="160" value="100" step="10" aria-label="Zoom evidence graph"><button id="resetZoom" class="toggle" type="button">Reset</button></div></div>
<div class="canvas" id="canvas" aria-label="Interactive evidence map"></div><section class="details" id="details" aria-live="polite"></section></main></div>
<footer class="foot">MirrorMap • Local, read-only report • No trackers or external scripts • Graph limited to {MAX_GRAPH_FINDINGS} visible findings at once. <code>mindmap.mmd</code> and <code>findings.json</code> contain the complete output.</footer>
</div><script id="atlas-data" type="application/json">{data}</script><script type="text/javascript">{_JS}</script></body></html>'''
    file = out / 'dashboard.html'
    file.write_text(page, encoding='utf-8')
    return file
