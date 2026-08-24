import os
from pathlib import Path

os.environ['AFM_DATA_DIR'] = str(Path(__file__).parent / 'runner-data')
import runner


def test_semantic_primary_filters_keyword_noise(monkeypatch):
    sem = [
        {'id': 1, 'name': 'renstra.pdf', 'path': 'renstra.pdf', 'title': 'Renstra', 'doc_type': 'proposal', 'summary': 'strategic plan', 'chunk': 'sasaran strategis', 'semantic': .88},
        {'id': 2, 'name': 'recipe.pdf', 'path': 'recipe.pdf', 'title': 'Recipe', 'doc_type': 'dokumen', 'summary': 'food', 'chunk': 'nasi goreng', 'semantic': .12},
    ]
    lex = [{**sem[1], 'lexical': 1.0}, {**sem[0], 'lexical': .1}]
    monkeypatch.setattr(runner, 'semantic_v2', lambda q, limit=30: sem)
    monkeypatch.setattr(runner, 'lexical_v2', lambda q, limit=30: lex)
    monkeypatch.setattr(runner, 'rerank', lambda q, c: c)
    out = runner.search_v2('renstra madrasah', 20)
    assert [x['id'] for x in out] == [1]


def test_reranker_discards_unrelated(monkeypatch):
    candidates = [
        {'id': 1, 'name': 'a.pdf', 'path': 'a.pdf', 'title': 'Relevant', 'doc_type': 'proposal', 'summary': 'good', 'chunk': 'answer'},
        {'id': 2, 'name': 'b.pdf', 'path': 'b.pdf', 'title': 'Noise', 'doc_type': 'dokumen', 'summary': 'noise', 'chunk': 'unrelated'},
    ]
    monkeypatch.setattr(runner, 'ready', lambda: True)
    monkeypatch.setattr(runner, 'model_ready', lambda name: True)
    monkeypatch.setattr(runner, 'call', lambda *a, **k: {'response': '[{"id":0,"score":94},{"id":1,"score":8}]'})
    out = runner.rerank('question', candidates)
    assert len(out) == 1 and out[0]['id'] == 1 and out[0]['relevance'] == 94


def test_lexical_is_only_a_small_boost(monkeypatch):
    sem = [{'id':1,'name':'good','path':'good','title':'Good','doc_type':'dokumen','summary':'good','chunk':'good','semantic':.70}]
    lex = [{'id':2,'name':'noise','path':'noise','title':'Noise','doc_type':'dokumen','summary':'noise','lexical':1.0}]
    monkeypatch.setattr(runner,'semantic_v2',lambda q,limit=30:sem)
    monkeypatch.setattr(runner,'lexical_v2',lambda q,limit=30:lex)
    monkeypatch.setattr(runner,'rerank',lambda q,c:c)
    out=runner.search_v2('q',10)
    assert out[0]['id']==1


def test_reranker_threshold_rejects_low_relevance(monkeypatch):
    candidates=[{'id':1,'name':'a','path':'a','title':'A','doc_type':'dokumen','summary':'a','chunk':'a'}]
    monkeypatch.setattr(runner,'ready',lambda:True)
    monkeypatch.setattr(runner,'model_ready',lambda name:True)
    monkeypatch.setattr(runner,'call',lambda *a,**k:{'response':'[{"id":0,"score":34}]'})
    assert runner.rerank('q',candidates)==[]


def test_app_health():
    from fastapi.testclient import TestClient
    client=TestClient(runner.legacy.app)
    response=client.get('/health')
    assert response.status_code==200
    assert response.json()['ok'] is True
