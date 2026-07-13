from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dashboard_html_path(report_path: Path) -> Path:
    return report_path.with_suffix(".html")


def write_dashboard_html(site_key: str, payload: dict[str, Any], report_path: Path) -> Path:
    """Write a portable dashboard with its report data embedded in the page."""
    output = dashboard_html_path(report_path)
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    # Keep user-authored content from ending the JSON script element.
    safe_data = data.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    safe_site = json.dumps(site_key, ensure_ascii=False).replace("<", "\\u003c")
    output.write_text(_PAGE.replace("__SITE_KEY__", safe_site).replace("__REPORT_DATA__", safe_data), encoding="utf-8")
    return output


_PAGE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Content Factory Dashboard</title>
  <style>
    :root{--ink:#18201d;--muted:#647069;--paper:#f4f6f2;--card:#fff;--line:#dce3dc;--green:#1d6b50;--lime:#b8e35b;--amber:#e8a83e;--red:#d45c55;--blue:#4f72cf;--shadow:0 14px 38px rgba(27,50,39,.09)}
    *{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    button,input,select{font:inherit}.shell{max-width:1440px;margin:auto;padding:30px}.mast{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:24px}.eyebrow{font-size:11px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:var(--green)}
    h1{font-size:clamp(28px,4vw,48px);line-height:1;margin:9px 0 7px;letter-spacing:-.045em}.sub{color:var(--muted)}.stamp{text-align:right;color:var(--muted);font-size:12px}.stamp strong{display:block;color:var(--ink);font-size:14px}
    .kpis{display:grid;grid-template-columns:repeat(5,minmax(150px,1fr));gap:14px;margin-bottom:14px}.card{background:var(--card);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow)}.kpi{padding:19px}.kpi-top{display:flex;justify-content:space-between;gap:8px;color:var(--muted);font-size:12px}.kpi-value{font-size:34px;font-weight:780;letter-spacing:-.04em;margin:8px 0}.target{font-size:11px;padding:4px 7px;border-radius:20px;background:#eef2ed}.track{height:7px;background:#edf1ed;border-radius:10px;overflow:hidden}.fill{height:100%;border-radius:10px;background:var(--green)}.kpi.warn .fill{background:var(--amber)}.kpi.bad .fill{background:var(--red)}
    .grid{display:grid;grid-template-columns:1.25fr .75fr;gap:14px;margin-bottom:14px}.panel{padding:22px;min-width:0}.panel-head{display:flex;justify-content:space-between;align-items:start;gap:16px;margin-bottom:18px}.panel h2{font-size:16px;margin:0}.panel p{margin:3px 0 0;color:var(--muted);font-size:12px}.legend{display:flex;gap:13px;flex-wrap:wrap;color:var(--muted);font-size:11px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px}
    #scatter{width:100%;height:280px;display:block}.axis{stroke:#dfe5df}.axis-label{fill:#78827c;font-size:10px}.point{fill:var(--green);fill-opacity:.7;stroke:#fff;stroke-width:1.5;cursor:pointer}.point:hover{fill:var(--amber);fill-opacity:1}.tip{position:fixed;display:none;pointer-events:none;background:#18201d;color:white;padding:8px 10px;border-radius:8px;font-size:11px;box-shadow:var(--shadow);z-index:10}
    .bars{display:grid;gap:12px}.bar-row{display:grid;grid-template-columns:minmax(80px,1fr) 3fr 28px;align-items:center;gap:10px;font-size:12px}.bar-label{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bar-track{height:9px;background:#edf1ed;border-radius:9px;overflow:hidden}.bar-fill{height:100%;background:linear-gradient(90deg,var(--green),#58a47f);border-radius:9px}.empty{color:var(--muted);padding:30px 0;text-align:center}
    .queues{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:14px}.queue{padding:20px}.queue-num{font-size:30px;font-weight:800;letter-spacing:-.04em}.queue-title{font-weight:700}.queue-copy{color:var(--muted);font-size:12px;margin-top:4px}.queue[data-tone="red"]{border-top:4px solid var(--red)}.queue[data-tone="amber"]{border-top:4px solid var(--amber)}.queue[data-tone="blue"]{border-top:4px solid var(--blue)}
    .table-card{overflow:hidden}.table-tools{display:flex;gap:10px;align-items:center;padding:18px 20px;border-bottom:1px solid var(--line)}.search{flex:1;min-width:120px;border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:#fafbf9;color:var(--ink)}select{border:1px solid var(--line);border-radius:10px;padding:10px;background:#fafbf9;color:var(--ink)}table{width:100%;border-collapse:collapse}th{text-align:left;color:var(--muted);font-size:10px;letter-spacing:.08em;text-transform:uppercase;padding:12px 20px;background:#f9faf8}td{padding:13px 20px;border-top:1px solid #edf0ed}tbody tr:hover{background:#fafcf9}.doc{font-weight:650;max-width:560px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pill{display:inline-block;padding:3px 7px;border-radius:10px;background:#edf4ef;color:var(--green);font-size:11px}.num{text-align:right;font-variant-numeric:tabular-nums}.status{color:var(--muted)}.table-foot{padding:12px 20px;color:var(--muted);font-size:11px;border-top:1px solid var(--line)}
    @media(max-width:1000px){.kpis{grid-template-columns:repeat(3,1fr)}.grid{grid-template-columns:1fr}.queues{grid-template-columns:1fr 1fr}.table-wrap{overflow:auto}table{min-width:800px}}
    @media(max-width:650px){.shell{padding:20px 14px}.mast{align-items:start;flex-direction:column}.stamp{text-align:left}.kpis{grid-template-columns:1fr 1fr}.queues{grid-template-columns:1fr}.panel{padding:17px}.table-tools{flex-wrap:wrap}}
  </style>
</head>
<body>
<main class="shell">
  <header class="mast">
    <div><div class="eyebrow">WordPress Content Factory</div><h1>Site readiness</h1><div class="sub" id="site"></div></div>
    <div class="stamp">Generated<strong id="generated"></strong></div>
  </header>
  <section class="kpis" id="kpis"></section>
  <section class="grid">
    <article class="card panel"><div class="panel-head"><div><h2>Content depth</h2><p>Every document plotted by word count and headings</p></div><div class="legend"><span><i class="dot" style="background:var(--green)"></i>Post</span><span><i class="dot" style="background:var(--blue)"></i>Page</span></div></div><svg id="scatter" role="img" aria-label="Document word count by headings"></svg></article>
    <article class="card panel"><div class="panel-head"><div><h2>Category coverage</h2><p>Documents assigned to each category</p></div></div><div class="bars" id="categories"></div></article>
  </section>
  <section class="queues" id="queues"></section>
  <section class="card table-card">
    <div class="table-tools"><input class="search" id="search" type="search" placeholder="Filter by document or category…"><select id="collection"><option value="">All content</option><option value="posts">Posts</option><option value="pages">Pages</option></select><select id="health"><option value="">All health</option><option value="short">Short posts</option><option value="missing">Missing images</option></select></div>
    <div class="table-wrap"><table><thead><tr><th>Document</th><th>Type</th><th>Status</th><th>Categories</th><th class="num">Words</th><th class="num">Images</th><th class="num">Headings</th></tr></thead><tbody id="rows"></tbody></table></div>
    <div class="table-foot" id="count"></div>
  </section>
</main>
<div class="tip" id="tip"></div>
<script id="report" type="application/json">__REPORT_DATA__</script>
<script>
const SITE=__SITE_KEY__,D=JSON.parse(document.getElementById('report').textContent),docs=D.documents||[],B=D.baselines||{},T=D.totals||{};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=(actual,target)=>target?Math.min(100,Math.round(actual/target*100)):100;
document.getElementById('site').textContent=SITE;
document.getElementById('generated').textContent=new Date(D.generated_at).toLocaleString();
const posts=docs.filter(d=>d.collection==='posts'),avgWords=posts.length?Math.round(posts.reduce((n,d)=>n+d.words,0)/posts.length):0,withImages=posts.filter(d=>d.images>=B.minimum_images_per_post).length;
const metrics=[['Posts',T.posts,B.minimum_posts],['Pages',T.pages,B.minimum_pages],['Categories',T.categories,B.minimum_categories],['Avg. post words',avgWords,B.minimum_words_per_post],['Posts with images',withImages,posts.length||1]];
document.getElementById('kpis').innerHTML=metrics.map(([label,a,t])=>{let p=pct(a,t),tone=p>=100?'':p>=60?'warn':'bad';return `<article class="card kpi ${tone}"><div class="kpi-top"><span>${label}</span><span class="target">target ${t}</span></div><div class="kpi-value">${a.toLocaleString()}</div><div class="track"><div class="fill" style="width:${p}%"></div></div></article>`}).join('');
const cats={};docs.forEach(d=>(Array.isArray(d.categories)?d.categories:[]).forEach(c=>cats[c]=(cats[c]||0)+1));
const catRows=Object.entries(cats).sort((a,b)=>b[1]-a[1]),maxCat=Math.max(1,...catRows.map(x=>x[1]));
document.getElementById('categories').innerHTML=catRows.length?catRows.slice(0,12).map(([c,n])=>`<div class="bar-row"><span class="bar-label" title="${esc(c)}">${esc(c)}</span><span class="bar-track"><i class="bar-fill" style="display:block;width:${n/maxCat*100}%"></i></span><b>${n}</b></div>`).join(''):'<div class="empty">No category assignments yet</div>';
const queues=[['Short posts',(D.short_posts||[]).length,'Below '+B.minimum_words_per_post+' words','amber'],['Missing images',(D.posts_missing_images||[]).length,'Posts without a content image','red'],['Content issues',(D.content_issues||[]).length,'Files that could not be parsed','blue']];
document.getElementById('queues').innerHTML=queues.map(([t,n,c,tone])=>`<article class="card queue" data-tone="${tone}"><div class="queue-num">${n}</div><div class="queue-title">${t}</div><div class="queue-copy">${c}</div></article>`).join('');
function scatter(){const svg=document.getElementById('scatter'),w=Math.max(560,svg.clientWidth||700),h=280,p={l:42,r:16,t:12,b:28},iw=w-p.l-p.r,ih=h-p.t-p.b,maxW=Math.max(B.minimum_words_per_post||800,...docs.map(d=>d.words)),maxH=Math.max(5,...docs.map(d=>d.headings));svg.setAttribute('viewBox',`0 0 ${w} ${h}`);let out='';for(let i=0;i<=4;i++){let y=p.t+ih*i/4,v=Math.round(maxH*(1-i/4));out+=`<line class="axis" x1="${p.l}" y1="${y}" x2="${w-p.r}" y2="${y}"/><text class="axis-label" x="${p.l-8}" y="${y+3}" text-anchor="end">${v}</text>`}for(let i=0;i<=4;i++){let x=p.l+iw*i/4,v=Math.round(maxW*i/4);out+=`<text class="axis-label" x="${x}" y="${h-6}" text-anchor="middle">${v}</text>`}out+=docs.map((d,i)=>{let x=p.l+d.words/maxW*iw,y=p.t+ih-d.headings/maxH*ih,r=Math.max(4,Math.min(10,4+d.images*2)),color=d.collection==='pages'?'var(--blue)':'var(--green)';return `<circle class="point" data-i="${i}" cx="${x}" cy="${y}" r="${r}" style="fill:${color}"/>`}).join('');svg.innerHTML=out;svg.querySelectorAll('.point').forEach(el=>{el.onmousemove=e=>{let d=docs[+el.dataset.i],tip=document.getElementById('tip');tip.innerHTML=`<b>${esc(d.document)}</b><br>${d.words} words · ${d.headings} headings · ${d.images} images`;tip.style.cssText=`display:block;left:${e.clientX+12}px;top:${e.clientY+12}px`};el.onmouseleave=()=>document.getElementById('tip').style.display='none'})}scatter();
const short=new Set(D.short_posts||[]),missing=new Set(D.posts_missing_images||[]),search=document.getElementById('search'),collection=document.getElementById('collection'),health=document.getElementById('health');
function renderRows(){let q=search.value.toLowerCase(),rows=docs.filter(d=>(!q||(d.document+' '+(d.categories||[]).join(' ')).toLowerCase().includes(q))&&(!collection.value||d.collection===collection.value)&&(!health.value||(health.value==='short'&&short.has(d.document))||(health.value==='missing'&&missing.has(d.document))));document.getElementById('rows').innerHTML=rows.map(d=>`<tr><td class="doc" title="${esc(d.document)}">${esc(d.document)}</td><td><span class="pill">${esc(d.collection)}</span></td><td class="status">${esc(d.status)}</td><td>${(d.categories||[]).map(c=>`<span class="pill">${esc(c)}</span>`).join(' ')||'—'}</td><td class="num">${d.words.toLocaleString()}</td><td class="num">${d.images}</td><td class="num">${d.headings}</td></tr>`).join('');document.getElementById('count').textContent=`Showing ${rows.length} of ${docs.length} documents`}[search,collection,health].forEach(x=>x.addEventListener('input',renderRows));renderRows();
addEventListener('resize',scatter);
</script>
</body>
</html>
'''
