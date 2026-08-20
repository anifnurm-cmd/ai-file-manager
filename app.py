from __future__
import hashlib, json, os, re, sqlite3
from pathlib import Path
from urllib.request import Request, urlopen
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data.db"
DB.parent.mkdir(exist_ok=True)
OLLAMA = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
EXTS = {'.txt','.md','.csv','.json','.xml','.log','.pdf','.docx','.xlsx','.xlsm','.pptx','.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}

HTML = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI File Manager</title><style>
:root{font:15px system-ui;color:#eaf1f8;background:#0b1119}body{margin:0;background:linear-gradient(135deg,#0b1119,#152338);min-height:100vh}.wrap{max-width:1050px;margin:auto;padding:30px 18px}header{display:flex;justify-content:space-between;gap:20px;align-items:start}h1{margin:4px 0 8px;font-size:38px}h2{margin:0 0 12px}.muted{color:#91a2b7}.pill{padding:8px 12px;border:1px solid #30445e;border-radius:999px}.card{background:#111b29dd;border:1px solid #263951;border-radius:16px;padding:18px;margin:15px 0}.row{display:flex;gap:10px}.row>*{flex:1}input,textarea{background:#0b1420;border:1px solid #30445e;color:#eef5ff;border-radius:10px;padding:11px;font:inherit}button{background:#6db4ff;color:#06101b;border:0;border-radius:10px;padding:11px 16px;font-weight:800;cursor:pointer}button:disabled{opacity:.5}.results{display:grid;gap:10px;margin-top:12px}.item{display:flex;justify-content:space-between;gap:12px;background:#0b1420;border:1px solid #22344c;border-radius:11px;padding:12px}.item small{color:#8195ad}.answer{white-space:pre-wrap;line-height:1.6;margin-top:12px}.src{margin-top:8px;color:#a8bad0}.err{color:#ffb0b0}@media(max-width:700px){header,.row{flex-direction:column}h1{font-size:30px}}
</style></head><body><div class="wrap"><header><div><div class="muted">LOCAL-FIRST DOCUMENT AI</div><h1>AI File Manager</h1><div class="muted">Read mixed documents, remember their contents, search them, ask questions, and safely rename files.</div></div><div class="pill" id="ai">Checking AI…</div></header>
<div class="card"><h2>1. Index a folder</h2><div class="row"><input id="folder" placeholder="C:\\Users\\You\\Documents"><button onclick="scan()">Scan</button></div><div id="scanmsg" class="muted"></div></div>
<div class="card"><h2>2. Ask your files</h2><div class="row"><textarea id="q" rows="3" placeholder="What documents mention Renstra? Summarize the proposal files…"></textarea><button onclick="ask()">Ask</button></div><div id="answer" class="answer muted">No question yet.</div><div id="sources"></div></div>
<div class="card"><h2>3. Search and rename</h2><div class="row"><input id="s" placeholder="Search by title, text, summary or type"><button onclick="searchFiles()">Search</button></div><div id="results" class="results"></div></div>
<div class="muted">Files remain local. Ollama is optional; without it, the app still indexes, searches and generates safe heuristic metadata.</div></div>
<script>
const $=x=>document.getElementById(x);async function api(u,o={}){let r=await fetch(u,{headers:{'Content-Type':'application/json'},...o}),d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');return d}
async function status(){let d=await api('/api/ai');$('ai').textContent=d.available?'AI: '+d.model:'AI: offline'}status();
async function scan(){let p=$('folder').value;$('scanmsg').textContent='Scanning…';try{let d=await api('/api/scan',{method:'POST',body:JSON.stringify({path:p})});$('scanmsg').textContent=`Seen ${d.seen}; indexed ${d.indexed}; skipped ${d.skipped}; errors ${d.errors}.`;searchFiles()}catch(e){$('scanmsg').innerHTML='<span class="err">'+e.message+'</span>'}}
async function searchFiles(){let q=$('s').value;if(!q)return;try{let d=await api('/api/search',{method:'POST',body:JSON.stringify({query:q})});$('results').innerHTML=d.results.map(x=>`<div class="item"><div><b>${esc(x.title||x.name)}</b><br><small>${esc(x.path)} · ${esc(x.type)}</small><div class="muted">${esc(x.summary||'')}</div></div><button onclick="rename(${x.id},${JSON.stringify(x.name)})">Rename</button></div>`).join('')||'<div class="muted">No results.</div>'}catch(e){$('results').textContent=e.message}}
async function ask(){let q=$('q').value;if(!q)return;$('answer').textContent='Thinking…';try{let d=await api('/api/ask',{method:'POST',body:JSON.stringify({question:q})});$('answer').textContent=d.answer;$('sources').innerHTML=d.sources.map(x=>`<div class="src">• ${esc(x.title||x.name)} — ${esc(x.path)}</div>`).join('')}catch(e){$('answer').textContent=e.message}}
async function rename(id,old){let n=prompt('New filename',old);if(!n)return;try{await api('/api/rename',{method:'POST',body:JSON.stringify({id,new_name:n})});searchFiles()}catch(e){alert(e.message)}}function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
</script></body></html>'''

app = FastAPI(title='AI File Manager', version='0.1.0')

def con():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
with con() as c:
    c.executescript('''CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY,path TEXT UNIQUE,name TEXT,ext TEXT,size INTEGER,mtime REAL,sha TEXT,title TEXT,type TEXT,summary TEXT,content TEXT); CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(path UNINDEXED,name,title,type,summary,content);''')

def sha(p):
    h=hashlib.sha256();
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def text(p):
    e=p.suffix.lower()
    try:
        if e in {'.txt','.md','.csv','.json','.xml','.log'}: return p.read_text(errors='ignore')
        if e=='.pdf':
            import fitz
            return '\n'.join(pg.get_text() for pg in fitz.open(p))
        if e=='.docx':
            from docx import Document
            d=Document(p); a=[x.text for x in d.paragraphs]
            for t in d.tables: a += [' | '.join(x.text for x in r.cells) for r in t.rows]
            return '\n'.join(a)
        if e in {'.xlsx','.xlsm'}:
            from openpyxl import load_workbook
            w=load_workbook(p,read_only=True,data_only=True); a=[]
            for s in w.worksheets:
                a.append('[SHEET] '+s.title)
                for r in s.iter_rows(values_only=True):
                    if any(v is not None for v in r): a.append(' | '.join('' if v is None else str(v) for v in r))
            return '\n'.join(a)
        if e=='.pptx':
            from pptx import Presentation
            d=Presentation(p); return '\n'.join(sh.text for sl in d.slides for sh in sl.shapes if hasattr(sh,'text'))
        if e in {'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}:
            import pytesseract
            from PIL import Image
            return pytesseract.image_to_string(Image.open(p))
    except Exception: return ''
    return ''

def clean(s): return re.sub(r'\s+',' ',s or '').strip()
def metadata(p,body):
    lines=[clean(x) for x in body.splitlines() if clean(x)]
    title=next((x for x in lines[:30] if 8<=len(x)<=140),p.stem.replace('_',' ').replace('-',' '))[:160]
    low=(p.name+' '+body[:5000]).lower()
    typ='dokumen'
    for name,words in [('surat',['surat','nomor surat']),('proposal',['proposal']),('laporan',['laporan','kesimpulan']),('notulen',['notulen','notula','hasil rapat']),('data peserta didik',['nisn','peserta didik','siswa']),('undangan',['undangan'])]:
        if any(w in low for w in words): typ=name; break
    summary=' '.join(re.split(r'(?<=[.!?])\s+',clean(body))[:3])[:700] or 'No extractable text.'
    return title,typ,summary

def ai(prompt):
    try:
        q=json.dumps({'model':MODEL,'prompt':prompt,'stream':False}).encode(); r=Request(OLLAMA+'/api/generate',data=q,headers={'Content-Type':'application/json'},method='POST')
        with urlopen(r,timeout=90) as z: return json.loads(z.read())['response']
    except Exception: return None

def index(p):
    st=p.stat(); h=sha(p)
    with con() as c:
        old=c.execute('select sha,mtime from files where path=?',(str(p),)).fetchone()
        if old and old['sha']==h and abs(old['mtime']-st.st_mtime)<.1:return 'skipped'
    body=clean(text(p)); title,typ,summary=metadata(p,body)
    richer=ai(f'Return JSON only: {json.dumps({"title":title,"type":typ,"summary":summary})}. Improve only if supported by this content:\n{body[:8000]}')
    if richer:
        m=re.search(r'\{.*\}',richer,re.S)
        if m:
            try:
                x=json.loads(m.group()); title=str(x.get('title') or title)[:160]; typ=str(x.get('type') or typ)[:80]; summary=str(x.get('summary') or summary)[:700]
            except Exception: pass
    with con() as c:
        c.execute('INSERT INTO files(path,name,ext,size,mtime,sha,title,type,summary,content) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET name=excluded.name,ext=excluded.ext,size=excluded.size,mtime=excluded.mtime,sha=excluded.sha,title=excluded.title,type=excluded.type,summary=excluded.summary,content=excluded.content',(str(p),p.name,p.suffix.lower(),st.st_size,st.st_mtime,h,title,typ,summary,body))
        c.execute('DELETE FROM fts WHERE path=?',(str(p),)); c.execute('INSERT INTO fts(path,name,title,type,summary,content) VALUES(?,?,?,?,?,?)',(str(p),p.name,title,typ,summary,body))
    return 'indexed'

class Scan(BaseModel): path:str=Field(min_length=1)
class Query(BaseModel): query:str=Field(min_length=1); limit:int=20
class Ask(BaseModel): question:str=Field(min_length=1)
class Rename(BaseModel): id:int; new_name:str=Field(min_length=1,max_length=240)

def rows(q,args=()):
    with con() as c:return [dict(x) for x in c.execute(q,args).fetchall()]

@app.get('/',response_class=HTMLResponse)
def home(): return HTML
@app.get('/health')
def health(): return {'ok':True,'version':app.version}
@app.get('/api/ai')
def ai_status():
    try:
        with urlopen(Request(OLLAMA+'/api/tags'),timeout=3): pass
        return {'available':True,'model':MODEL}
    except Exception:return {'available':False,'model':MODEL}
@app.post('/api/scan')
def scan(r:Scan):
    root=Path(r.path)
    if not root.is_dir():raise HTTPException(400,'Folder does not exist or is not accessible')
    seen=indexed=skipped=errors=0
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() in EXTS:
            seen+=1
            try:
                x=index(p); indexed+=x=='indexed'; skipped+=x=='skipped'
            except Exception: errors+=1
    return {'seen':seen,'indexed':indexed,'skipped':skipped,'errors':errors}
@app.post('/api/search')
def search(r:Query):
    toks=[t for t in re.split(r'\s+',r.query.strip()) if t][:8]
    expr=' AND '.join('"'+t.replace('"','')+'"*' for t in toks)
    try: return {'results':rows('SELECT files.id,files.name,files.path,files.title,files.type,files.summary FROM fts JOIN files ON files.path=fts.path WHERE fts MATCH ? LIMIT ?', (expr,max(1,min(r.limit,50))))}
    except sqlite3.OperationalError:return {'results':[]}
@app.post('/api/ask')
def askq(r:Ask):
    hits=search(Query(query=r.question,limit=8))['results'];
    if not hits:return {'answer':'No matching indexed documents found.','sources':[]}
    ctx='\n\n'.join(f"FILE {x['name']}\nPATH {x['path']}\nTITLE {x['title']}\nSUMMARY {x['summary']}" for x in hits)
    out=ai(f'Answer only from these file records. Do not invent facts. Reply in the language of the question.\nQUESTION: {r.question}\n\n{ctx}')
    return {'answer':out or 'I found relevant files, but Ollama is not available for a generated answer.','sources':hits}
@app.post('/api/rename')
def rename(r:Rename):
    n=Path(r.new_name).name
    if not n or any(x in n for x in '<>:"/\\|?*'):raise HTTPException(400,'Invalid Windows filename')
    with con() as c: f=c.execute('select path from files where id=?',(r.id,)).fetchone()
    if not f:raise HTTPException(404,'File not found')
    old=Path(f['path']); new=old.with_name(n)
    if not old.exists():raise HTTPException(404,'Original file no longer exists')
    if new.exists() and new!=old:raise HTTPException(409,'Target filename already exists')
    old.rename(new); index(new)
    with con() as c:c.execute('delete from files where path=?',(str(old),));c.execute('delete from fts where path=?',(str(old),))
    return {'ok':True,'new_path':str(new)}

if __name__=='__main__':
    import uvicorn
    uvicorn.run('app:app',host='127.0.0.1',port=int(os.getenv('PORT','8787')))
