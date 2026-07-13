"""Detect near-duplicate prose and competing search intent across local content."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

from .config import SiteConfig
from .models import Document

WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?", re.I)
HEADING_RE = re.compile(r"^#{1,3}\s+(.+?)\s*$", re.M)
STOP_WORDS = {
    "a", "about", "after", "all", "also", "an", "and", "any", "are", "as", "at", "be", "been",
    "before", "but", "by", "can", "do", "for", "from", "get", "has", "have", "how", "if", "in",
    "into", "is", "it", "its", "more", "not", "of", "on", "or", "our", "out", "should", "so",
    "that", "the", "their", "then", "there", "these", "this", "those", "to", "use", "using", "was",
    "we", "were", "what", "when", "where", "which", "who", "why", "will", "with", "you", "your",
}


def _normalize_token(token: str) -> str:
    token = token.lower().strip("'-")
    if len(token) > 5 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokens(text: str) -> list[str]:
    cleaned = re.sub(r"```.*?```|`[^`]*`", " ", text, flags=re.S)
    cleaned = re.sub(r"!?\[([^]]*)\]\([^)]+\)", r"\1", cleaned)
    return [
        normalized
        for raw in WORD_RE.findall(cleaned)
        if len(normalized := _normalize_token(raw)) > 2 and normalized not in STOP_WORDS
    ]


def _focus(doc: Document) -> tuple[str, str]:
    for key in ("focus_keyword", "focus_keyphrase", "primary_keyword", "keyword"):
        value = doc.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip(), "frontmatter"
    return doc.title, "title-derived"


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    shared = set(left) & set(right)
    numerator = sum(left[t] * right[t] for t in shared)
    left_norm = math.sqrt(sum(v * v for v in left.values()))
    right_norm = math.sqrt(sum(v * v for v in right.values()))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _jaccard(left: set[Any], right: set[Any]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _shingles(tokens: list[str], size: int = 5) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + size]) for i in range(max(0, len(tokens) - size + 1))}


def _in_target(doc: Document, target: Path | None) -> bool:
    if target is None:
        return True
    resolved = target.resolve()
    path = doc.path.resolve()
    return path == resolved or resolved in path.parents


def run_content_overlap(site: SiteConfig, target: Path | None, docs: list[Document]) -> dict[str, Any]:
    """Return an explainable site-wide overlap map, optionally centered on a target."""
    selected = {doc.key for doc in docs if _in_target(doc, target)}
    if target is not None and not selected:
        docs = []

    body_tokens = {doc.key: _tokens(doc.markdown) for doc in docs}
    title_tokens = {doc.key: set(_tokens(doc.title)) for doc in docs}
    focus_values = {doc.key: _focus(doc) for doc in docs}
    intent_tokens: dict[str, set[str]] = {}
    for doc in docs:
        focus, _source = focus_values[doc.key]
        heading_text = " ".join(HEADING_RE.findall(doc.markdown))
        # Focus/title terms dominate; headings add sub-intent context.
        intent_tokens[doc.key] = set(_tokens(f"{focus} {focus} {doc.title} {heading_text}"))

    document_frequency: Counter[str] = Counter()
    for tokens in body_tokens.values():
        document_frequency.update(set(tokens))
    total_docs = max(1, len(docs))
    vectors: dict[str, dict[str, float]] = {}
    for key, tokens in body_tokens.items():
        counts = Counter(tokens)
        vectors[key] = {
            term: (1 + math.log(count)) * (math.log((total_docs + 1) / (document_frequency[term] + 1)) + 1)
            for term, count in counts.items()
        }

    overlaps: list[dict[str, Any]] = []
    graph_edges: list[dict[str, Any]] = []
    collision_counts: Counter[str] = Counter()
    max_scores: dict[str, int] = {doc.key: 0 for doc in docs}
    for left, right in combinations(docs, 2):
        if target is not None and left.key not in selected and right.key not in selected:
            continue
        intent = _jaccard(intent_tokens[left.key], intent_tokens[right.key])
        titles = _jaccard(title_tokens[left.key], title_tokens[right.key])
        body = _cosine(vectors[left.key], vectors[right.key])
        shingles = _jaccard(_shingles(body_tokens[left.key]), _shingles(body_tokens[right.key]))
        score = round(100 * (0.50 * intent + 0.20 * titles + 0.20 * body + 0.10 * shingles))
        max_scores[left.key] = max(max_scores[left.key], score)
        max_scores[right.key] = max(max_scores[right.key], score)

        if shingles >= 0.55 or body >= 0.92:
            level = "critical"
            kind = "near-duplicate"
            action = "Compare side by side; consolidate repeated prose or make one page materially distinct before publishing."
        elif score >= 65 and (intent >= 0.58 or titles >= 0.50):
            level = "high"
            kind = "intent-collision"
            action = "Assign different search intent and focus keyphrases, or merge the weaker page into the stronger canonical resource."
        elif score >= 48:
            level = "medium"
            kind = "topical-overlap"
            action = "Keep both only if their audience, question, and internal-link relationship are explicit."
        else:
            level = "low"
            kind = "related"
            action = "No collision action required; consider an internal link if the relationship helps readers."

        shared = sorted(intent_tokens[left.key] & intent_tokens[right.key])[:10]
        if score >= 20:
            graph_edges.append({"source": left.key, "target": right.key, "score": score, "level": level})
        if level in {"critical", "high", "medium"}:
            collision_counts.update((left.key, right.key))
            overlaps.append(
                {
                    "left": left.key,
                    "right": right.key,
                    "score": score,
                    "level": level,
                    "kind": kind,
                    "shared_terms": shared,
                    "metrics": {
                        "intent": round(intent * 100),
                        "title": round(titles * 100),
                        "body": round(body * 100),
                        "verbatim_shingles": round(shingles * 100),
                    },
                    "recommended_action": action,
                }
            )

    overlaps.sort(key=lambda row: (-row["score"], row["left"], row["right"]))
    document_rows = []
    for doc in docs:
        focus, source = focus_values[doc.key]
        count = collision_counts[doc.key]
        document_rows.append(
            {
                "document": doc.key,
                "title": doc.title,
                "collection": doc.collection,
                "status": doc.status,
                "focus_keyword": focus,
                "focus_source": source,
                "search_intent": str(doc.metadata.get("search_intent") or "unspecified"),
                "content_role": str(doc.metadata.get("content_role") or "unspecified"),
                "words": len(body_tokens[doc.key]),
                "collision_count": count,
                "max_overlap": max_scores[doc.key],
                "health": "collision" if count else "clear",
            }
        )
    document_rows.sort(key=lambda row: (-row["max_overlap"], row["document"]))
    missing_focus = [row["document"] for row in document_rows if row["focus_source"] == "title-derived"]
    missing_intent = [row["document"] for row in document_rows if row["search_intent"] == "unspecified"]
    isolated = [row["document"] for row in document_rows if row["max_overlap"] < 20]

    return {
        "tool": "content-overlap",
        "generated_at": datetime.now(UTC).isoformat(),
        "target": str(target) if target else "site",
        "summary": {
            "documents": len(document_rows),
            "pairs_analyzed": sum(1 for _ in combinations(docs, 2)) if target is None else sum(1 for left, right in combinations(docs, 2) if left.key in selected or right.key in selected),
            "critical": sum(row["level"] == "critical" for row in overlaps),
            "high": sum(row["level"] == "high" for row in overlaps),
            "medium": sum(row["level"] == "medium" for row in overlaps),
            "isolated": len(isolated),
            "missing_focus_keyword": len(missing_focus),
            "missing_search_intent": len(missing_intent),
        },
        "documents": document_rows,
        "overlaps": overlaps,
        "graph": {"nodes": document_rows, "edges": graph_edges},
        "task_queue": {
            "manual_review": overlaps[:20],
            "add_focus_keyword": missing_focus[:30],
            "add_search_intent": missing_intent[:30],
            "consider_internal_links": [edge for edge in graph_edges if edge["level"] == "low"][:30],
        },
        "interpretation": (
            "This is a local editorial risk signal, not a Google ranking verdict. High similarity can be intentional; "
            "a human should decide whether pages answer distinct questions before merging or redirecting anything."
        ),
    }


def write_content_overlap_html(site_key: str, payload: dict[str, Any], report_path: Path) -> Path:
    output = report_path.with_suffix(".html")
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    safe = data.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    safe_site = json.dumps(site_key, ensure_ascii=False).replace("<", "\\u003c")
    output.write_text(_HTML.replace("__DATA__", safe).replace("__SITE__", safe_site), encoding="utf-8")
    return output


_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Content Overlap Map · Content Factory</title><style>
:root{--ink:#17201c;--muted:#68746d;--paper:#f3f5f1;--card:#fff;--line:#dce3dc;--green:#176b50;--amber:#d39522;--red:#c54d47;--blue:#426dc2}*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.45 Inter,system-ui,sans-serif}.shell{max-width:1380px;margin:auto;padding:28px}.eyebrow{font-size:11px;font-weight:800;letter-spacing:.15em;text-transform:uppercase;color:var(--green)}h1{font-size:clamp(28px,4vw,46px);letter-spacing:-.045em;margin:7px 0}.sub{color:var(--muted)}
.kpis{display:grid;grid-template-columns:repeat(7,minmax(110px,1fr));gap:10px;margin:20px 0}.card{background:var(--card);border:1px solid var(--line);border-radius:17px;box-shadow:0 12px 32px rgba(22,45,32,.06)}.kpi{padding:15px}.kpi b{display:block;font-size:26px}.kpi span{font-size:11px;color:var(--muted)}
.grid{display:grid;grid-template-columns:1.25fr .75fr;gap:14px}.panel{padding:18px;min-width:0}.panel h2{font-size:16px;margin:0 0 3px}.panel p{font-size:12px;color:var(--muted);margin:0 0 14px}#map{display:block;width:100%;height:520px;border-radius:12px;background:radial-gradient(circle at center,#fff,#f6f8f4)}.edge{stroke:#cdd6cf}.edge.high,.edge.critical{stroke:var(--red)}.edge.medium{stroke:var(--amber)}.node{cursor:pointer;stroke:#fff;stroke-width:2}.node.posts{fill:var(--green)}.node.pages{fill:var(--blue)}.label{font-size:9px;fill:var(--muted);pointer-events:none}.legend{display:flex;gap:12px;flex-wrap:wrap;margin-top:10px;color:var(--muted);font-size:11px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px}
.list{display:grid;gap:9px;max-height:555px;overflow:auto}.pair{border:1px solid var(--line);border-left:4px solid var(--amber);border-radius:11px;padding:11px}.pair.critical,.pair.high{border-left-color:var(--red)}.pair-top{display:flex;justify-content:space-between;gap:8px}.pair b{font-size:12px}.score{font-size:18px;font-weight:800}.pair small{display:block;color:var(--muted);margin-top:5px}.terms{color:var(--green);font-size:11px;margin-top:5px}.empty{padding:40px;text-align:center;color:var(--muted)}
.table-card{margin-top:14px;overflow:auto}table{width:100%;border-collapse:collapse;min-width:850px}th,td{padding:11px 14px;border-top:1px solid var(--line);text-align:left}th{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.pill{display:inline-block;padding:2px 7px;border-radius:12px;background:#e7f3eb;color:var(--green);font-size:11px}.pill.collision{background:#fde8e5;color:var(--red)}.note{margin-top:14px;color:var(--muted);font-size:12px}
@media(max-width:1000px){.kpis{grid-template-columns:repeat(4,1fr)}.grid{grid-template-columns:1fr}}@media(max-width:600px){.shell{padding:18px 12px}.kpis{grid-template-columns:repeat(2,1fr)}#map{height:380px}}
</style></head><body><main class="shell"><div class="eyebrow">WordPress Content Factory</div><h1>Content overlap map</h1><div class="sub" id="sub"></div><section class="kpis" id="kpis"></section><section class="grid"><article class="card panel"><h2>Search-intent neighborhood</h2><p>Connections show related pages; red lines need editorial review before more long-tail content is published.</p><svg id="map" role="img" aria-label="Content similarity network"></svg><div class="legend"><span><i class="dot" style="background:var(--green)"></i>Posts</span><span><i class="dot" style="background:var(--blue)"></i>Pages</span><span><i class="dot" style="background:var(--red)"></i>Collision risk</span></div></article><aside class="card panel"><h2>Review first</h2><p>Highest-risk pairs with the evidence behind each flag.</p><div class="list" id="pairs"></div></aside></section><section class="card table-card"><table><thead><tr><th>Document</th><th>Focus</th><th>Intent</th><th>Role</th><th>Collisions</th><th>Max overlap</th><th>Health</th></tr></thead><tbody id="rows"></tbody></table></section><div class="note" id="note"></div></main><script id="report" type="application/json">__DATA__</script><script>
const D=JSON.parse(document.getElementById('report').textContent),SITE=__SITE__,S=D.summary||{},esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));document.getElementById('sub').textContent=SITE+' · '+new Date(D.generated_at).toLocaleString();document.getElementById('kpis').innerHTML=Object.entries(S).slice(0,7).map(([k,v])=>`<div class="card kpi"><b>${v}</b><span>${esc(k.replaceAll('_',' '))}</span></div>`).join('');
const pairs=D.overlaps||[];document.getElementById('pairs').innerHTML=pairs.length?pairs.slice(0,20).map(p=>`<div class="pair ${p.level}"><div class="pair-top"><b>${esc(p.kind.replaceAll('-',' '))}</b><span class="score">${p.score}</span></div><small>${esc(p.left)}<br>${esc(p.right)}</small><div class="terms">${esc((p.shared_terms||[]).join(' · '))}</div><small>${esc(p.recommended_action)}</small></div>`).join(''):'<div class="empty">No material overlap found.</div>';
const docs=D.documents||[];document.getElementById('rows').innerHTML=docs.map(d=>`<tr><td><b>${esc(d.document)}</b><div class="sub">${esc(d.title)}</div></td><td>${esc(d.focus_keyword)}${d.focus_source==='title-derived'?'<div class="sub">derived</div>':''}</td><td>${esc(d.search_intent)}</td><td>${esc(d.content_role)}</td><td>${d.collision_count}</td><td>${d.max_overlap}</td><td><span class="pill ${d.health}">${d.health}</span></td></tr>`).join('');document.getElementById('note').textContent=D.interpretation||'';
function draw(){const svg=document.getElementById('map'),w=Math.max(500,svg.clientWidth||700),h=520,nodes=(D.graph?.nodes||[]),edges=(D.graph?.edges||[]),byKey=Object.fromEntries(nodes.map((n,i)=>[n.document,{...n,i}])),cx=w/2,cy=h/2,r=Math.min(w,h)*.39;nodes.forEach((n,i)=>{let a=Math.PI*2*i/Math.max(1,nodes.length)-Math.PI/2;n.x=cx+Math.cos(a)*r;n.y=cy+Math.sin(a)*r;byKey[n.document]=n});svg.setAttribute('viewBox',`0 0 ${w} ${h}`);let lines=edges.map(e=>{let a=byKey[e.source],b=byKey[e.target];return a&&b?`<line class="edge ${e.level}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke-width="${Math.max(1,e.score/28)}" opacity="${Math.max(.25,e.score/100)}"/>`:''}).join('');let circles=nodes.map(n=>{let label=n.title.length>25?n.title.slice(0,23)+'…':n.title,rr=Math.max(5,Math.min(13,6+n.collision_count*2));return `<g><circle class="node ${n.collection}" cx="${n.x}" cy="${n.y}" r="${rr}"><title>${esc(n.title)} · max ${n.max_overlap}</title></circle><text class="label" x="${n.x+rr+3}" y="${n.y+3}">${esc(label)}</text></g>`}).join('');svg.innerHTML=lines+circles}draw();addEventListener('resize',draw);
</script></body></html>'''
