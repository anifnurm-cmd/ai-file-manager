from __future__

import json
import math
import os
import re
import sqlite3
from pathlib import Path
from urllib.request import Request, urlopen

os.environ.setdefault("OLLAMA_MODEL", "qwen3-vl:8b")
os.environ.setdefault("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b")
os.environ.setdefault("OLLAMA_CHAT_MODEL", "qwen3-vl:8b")
os.environ.setdefault("PORT", "8787")

import legacy_app as legacy
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DATA = Path(os.getenv("AFM_DATA_DIR", str(ROOT / "data"))).resolve()
DB = DATA / "semantic_v2.sqlite3"
OLLAMA = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen3-vl:8b")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b")
DATA.mkdir(parents=True, exist_ok=True)


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    with db() as c:
        c.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS docs(
          id INTEGER PRIMARY KEY,path TEXT UNIQUE,name TEXT,ext TEXT,size INTEGER,mtime REAL,sha TEXT,
          title TEXT,doc_type TEXT,summary TEXT,content TEXT);
        CREATE TABLE IF NOT EXISTS chunks(
          id INTEGER PRIMARY KEY,doc_id INTEGER REFERENCES docs(id) ON DELETE CASCADE,chunk_no INTEGER,
          text TEXT,embedding TEXT,model TEXT,UNIQUE(doc_id,chunk_no));
        CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(doc_id UNINDEXED,path,name,title,doc_type,summary,content);
        CREATE INDEX IF NOT EXISTS idx_chunks_model ON chunks(model);
        """)


init()


def call(path, payload=None, timeout=90):
    try:
        if payload is None:
            req = Request(f"{OLLAMA}{path}")
        else:
            req = Request(f"{OLLAMA}{path}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def ready():
    return call("/api/version", timeout=2) is not None


def model_ready(name):
    data = call("/api/tags", timeout=3)
    return bool(data and any(m.get("name") == name for m in data.get("models", [])))


def cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def embed_documents(parts):
    if not parts or not ready() or not model_ready(EMBED_MODEL):
        return [None] * len(parts)
    payload = {"model": EMBED_MODEL, "input": [f"search_document: {p[:7000]}" for p in parts]}
    data = call("/api/embed", payload, timeout=120)
    if data and isinstance(data.get("embeddings"), list) and len(data["embeddings"]) == len(parts):
        return [list(map(float, v)) if isinstance(v, list) else None for v in data["embeddings"]]
    out = []
    for part in parts:
        data = call("/api/embeddings", {"model": EMBED_MODEL, "prompt": f"search_document: {part[:7000]}"}, timeout=60)
        out.append(list(map(float, data["embedding"])) if data and isinstance(data.get("embedding"), list) else None)
    return out


def embed_query(query):
    if not ready() or not model_ready(EMBED_MODEL):
        return None
    data = call("/api/embed", {"model": EMBED_MODEL, "input": [f"search_query: {query[:7000]}"]}, timeout=60)
    if data and isinstance(data.get("embeddings"), list) and data["embeddings"]:
        return list(map(float, data["embeddings"][0]))
    data = call("/api/embeddings", {"model": EMBED_MODEL, "prompt": f"search_query: {query[:7000]}"}, timeout=60)
    return list(map(float, data["embedding"])) if data and isinstance(data.get("embedding"), list) else None


def rerank(query, candidates):
    if not candidates or not ready() or not model_ready(CHAT_MODEL):
        return candidates
    compact = [{"id": i, "title": x["title"], "type": x["doc_type"], "summary": x["summary"][:500], "passage": x.get("chunk", "")[:1200]} for i, x in enumerate(candidates)]
    prompt = (
        "Strictly rank document relevance. Score each candidate 0-100 for how directly useful it is to answer the query. "
        "Do not reward generic words or merely similar filenames. Return JSON array only with id and score.\n"
        f"QUERY: {query}\nCANDIDATES: {json.dumps(compact, ensure_ascii=False)}"
    )
    data = call("/api/generate", {"model": CHAT_MODEL, "prompt": prompt, "stream": False}, timeout=150)
    raw = str((data or {}).get("response") or "")
    match = re.search(r"\[.*\]", raw, re.S)
    if not match:
        return candidates
    try:
        scores = json.loads(match.group(0))
        mapping = {int(x["id"]): max(0.0, min(100.0, float(x["score"]))) for x in scores if isinstance(x, dict)}
        out = []
        for i, item in enumerate(candidates):
            x = dict(item)
            x["relevance"] = mapping.get(i, 0.0)
            out.append(x)
        return sorted([x for x in out if x["relevance"] >= 35], key=lambda x: x["relevance"], reverse=True)
    except Exception:
        return candidates


def index_v2(path: Path):
    st = path.stat()
    digest = legacy.sha(path)
    with db() as c:
        old = c.execute("SELECT id,sha FROM docs WHERE path=?", (str(path),)).fetchone()
        if old and old["sha"] == digest:
            have = c.execute("SELECT 1 FROM chunks WHERE doc_id=? AND model=? LIMIT 1", (old["id"], EMBED_MODEL)).fetchone()
            if have or not model_ready(EMBED_MODEL):
                return int(old["id"]), "skipped"
    body = legacy.text(path)
    title, doc_type, summary = legacy.metadata(path, body)
    parts = legacy.chunk_text(body)
    vectors = embed_documents(parts)
    with db() as c:
        old = c.execute("SELECT id FROM docs WHERE path=?", (str(path),)).fetchone()
        if old:
            doc_id = int(old["id"])
            c.execute("DELETE FROM fts WHERE doc_id=?", (doc_id,))
            c.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
            c.execute("UPDATE docs SET name=?,ext=?,size=?,mtime=?,sha=?,title=?,doc_type=?,summary=?,content=? WHERE id=?", (path.name,path.suffix.lower(),st.st_size,st.st_mtime,digest,title,doc_type,summary,body,doc_id))
        else:
            cur = c.execute("INSERT INTO docs(path,name,ext,size,mtime,sha,title,doc_type,summary,content) VALUES(?,?,?,?,?,?,?,?,?,?)", (str(path),path.name,path.suffix.lower(),st.st_size,st.st_mtime,digest,title,doc_type,summary,body))
            doc_id = int(cur.lastrowid)
        c.execute("INSERT INTO fts(doc_id,path,name,title,doc_type,summary,content) VALUES(?,?,?,?,?,?,?)", (doc_id,str(path),path.name,title,doc_type,summary,body))
        for i, part in enumerate(parts):
            vec = vectors[i] if i < len(vectors) else None
            c.execute("INSERT INTO chunks(doc_id,chunk_no,text,embedding,model) VALUES(?,?,?,?,?)", (doc_id,i,part,json.dumps(vec) if vec else None,EMBED_MODEL if vec else None))
    return doc_id, "indexed"


def semantic_v2(query, limit=30):
    qv = embed_query(query)
    if not qv:
        return []
    with db() as c:
        rows = c.execute("SELECT ch.doc_id,ch.text,ch.embedding,d.name,d.path,d.title,d.doc_type,d.summary FROM chunks ch JOIN docs d ON d.id=ch.doc_id WHERE ch.model=?", (EMBED_MODEL,)).fetchall()
    best = {}
    for r in rows:
        try:
            score = cosine(qv, json.loads(r["embedding"]))
        except Exception:
            continue
        item = {"id":r["doc_id"],"name":r["name"],"path":r["path"],"title":r["title"],"doc_type":r["doc_type"],"summary":r["summary"],"chunk":r["text"],"semantic":score}
        if item["id"] not in best or score > best[item["id"]]["semantic"]:
            best[item["id"]] = item
    return sorted(best.values(), key=lambda x:x["semantic"], reverse=True)[:limit]


def lexical_v2(query, limit=30):
    terms = [x for x in re.findall(r"[\w-]+", query, re.UNICODE) if len(x) > 1][:10]
    if not terms:
        return []
    expression = " OR ".join('"' + x.replace('"', '') + '"*' for x in terms)
    with db() as c:
        rows = c.execute("SELECT d.id,d.name,d.path,d.title,d.doc_type,d.summary,bm25(fts) score FROM fts JOIN docs d ON d.id=fts.doc_id WHERE fts MATCH ? ORDER BY score LIMIT ?", (expression, min(limit, 50))).fetchall()
    if not rows:
        return []
    vals = [float(r["score"]) for r in rows]
    lo, hi = min(vals), max(vals)
    return [{**dict(r), "lexical": 1.0 if hi == lo else max(0.0, min(1.0, 1 - (float(r["score"]) - lo) / (hi - lo)))} for r in rows]


def search_v2(query, limit=20):
    semantic = semantic_v2(query, 30)
    lexical = lexical_v2(query, 30)
    merged = {}
    for item in semantic:
        merged[item["id"]] = dict(item, retrieval="semantic")
    for item in lexical:
        if item["id"] in merged:
            merged[item["id"]]["lexical"] = item["lexical"]
            merged[item["id"]]["retrieval"] = "semantic+keyword"
        else:
            merged[item["id"]] = dict(item, retrieval="keyword")
    items = list(merged.values())
    for item in items:
        sem = float(item.get("semantic", 0.0))
        lex = float(item.get("lexical", 0.0))
        item["base_score"] = 0.88 * sem + 0.12 * lex if sem else 0.18 * lex
    items.sort(key=lambda x:x["base_score"], reverse=True)
    if semantic:
        threshold = max(0.30, semantic[0]["semantic"] * 0.60)
        items = [x for x in items if float(x.get("semantic",0.0)) >= threshold][:16]
    else:
        items = items[:16]
    items = rerank(query, items)
    for item in items:
        item.setdefault("relevance", round(float(item["base_score"]) * 100, 1))
    return items[:limit]


legacy.OLLAMA = OLLAMA
legacy.OLLAMA_MODEL = CHAT_MODEL
legacy.MODEL = CHAT_MODEL
legacy.index = index_v2
legacy.hybrid_results = search_v2


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=50)


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


def answer_v2(question, hits):
    if not hits:
        return "Saya tidak menemukan dokumen yang cukup relevan untuk menjawab pertanyaan tersebut."
    context = "\n\n---\n\n".join(f"FILE: {x['name']}\nPATH: {x['path']}\nTITLE: {x['title']}\nTYPE: {x['doc_type']}\nPASSAGE: {x.get('chunk','')}" for x in hits[:8])
    if ready() and model_ready(CHAT_MODEL):
        prompt = "Answer only from the supplied document evidence. Do not invent facts. If evidence is insufficient, say so. Cite filenames. Reply in the same language as the question.\n\nQUESTION:\n" + question + "\n\nEVIDENCE:\n" + context
        data = call("/api/chat", {"model": CHAT_MODEL, "stream": False, "messages": [{"role":"user","content":prompt}]}, timeout=180)
        result = str((((data or {}).get("message") or {}).get("content")) or "").strip()
        if result:
            return result
    return "Dokumen paling relevan:\n" + "\n".join(f"- {x['title']} ({x.get('relevance',0):.0f}%)" for x in hits)


def status_endpoint():
    with db() as c:
        documents = int(c.execute("SELECT COUNT(*) FROM docs").fetchone()[0])
        embedded = int(c.execute("SELECT COUNT(DISTINCT doc_id) FROM chunks WHERE model=?", (EMBED_MODEL,)).fetchone()[0])
    return {"documents": documents, "embedded_documents": embedded, "semantic_ready": ready() and model_ready(EMBED_MODEL), "chat_ready": ready() and model_ready(CHAT_MODEL), "chat_model": CHAT_MODEL, "embed_model": EMBED_MODEL}


def reindex_endpoint():
    if not ready() or not model_ready(EMBED_MODEL):
        raise legacy.HTTPException(503, f"Embedding model {EMBED_MODEL} is not ready")
    with db() as c:
        paths = [r["path"] for r in c.execute("SELECT path FROM docs ORDER BY id").fetchall()]
    ok = err = 0
    for p in paths:
        try:
            index_v2(Path(p)); ok += 1
        except Exception:
            err += 1
    return {"documents": len(paths), "reindexed": ok, "errors": err}


def rename_endpoint(req):
    safe = Path(req.new_name).name
    if safe != req.new_name or any(ch in safe for ch in '<>:"/\\|?*'):
        raise legacy.HTTPException(400, "Invalid Windows filename")
    with db() as c:
        row = c.execute("SELECT path FROM docs WHERE id=?", (req.id,)).fetchone()
    if not row:
        raise legacy.HTTPException(404, "Document not found")
    old = Path(row["path"])
    if not old.exists():
        raise legacy.HTTPException(404, "Original file no longer exists")
    new = old.with_name(safe)
    if new.exists() and new.resolve() != old.resolve():
        raise legacy.HTTPException(409, "Target filename already exists")
    old.rename(new)
    index_v2(new)
    with db() as c:
        c.execute("DELETE FROM docs WHERE path=?", (str(old),))
        c.execute("DELETE FROM fts WHERE path=?", (str(old),))
    return {"ok": True, "new_path": str(new)}


def search_endpoint(req: SearchRequest):
    return {"results": search_v2(req.query, req.limit), "semantic_ready": bool(semantic_v2(req.query, 1))}


def ask_endpoint(req: AskRequest):
    hits = search_v2(req.question, 10)
    return {"answer": answer_v2(req.question, hits), "sources": [{"id":x["id"],"name":x["name"],"path":x["path"],"title":x["title"],"relevance":x.get("relevance",0)} for x in hits]}


for route in legacy.app.router.routes:
    if not isinstance(route, APIRoute):
        continue
    if route.path == "/api/search":
        route.endpoint = search_endpoint
        route.app = route.get_route_handler()
    elif route.path == "/api/ask":
        route.endpoint = ask_endpoint
        route.app = route.get_route_handler()
    elif route.path == "/api/status":
        route.endpoint = status_endpoint
        route.app = route.get_route_handler()
    elif route.path == "/api/reindex-semantic":
        route.endpoint = reindex_endpoint
        route.app = route.get_route_handler()
    elif route.path == "/api/rename":
        route.endpoint = rename_endpoint
        route.app = route.get_route_handler()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("runner:legacy.app", host="127.0.0.1", port=int(os.getenv("PORT", "8787")))
