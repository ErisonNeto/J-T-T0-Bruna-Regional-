"""T0 da Bruna / João Melo | Dashboard SLA + Shipping Time | JT API."""
from __future__ import annotations
import csv, os, io
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
API_URL = os.getenv('JT_API_URL', 'https://jt-api.rockettechbr.com.br').strip().rstrip('/')
API_KEY = os.getenv('JT_API_KEY', '').strip()
DATA_SOURCE = os.getenv('T0_DATA_SOURCE', 'api').strip().lower()
TABLE = 't0_joao_melo_diario'
CSV = ROOT / 't0_centro_oeste_01_a_10_preparado.csv'
META = 70.0
# 10/11 foi extraído ainda durante o dia; ignorá-lo até validação posterior.
EXCLUDED_DATES = {'2026-11-10'}
app = FastAPI(title='J&T | T0 Bruna — Centro-Oeste')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')


def parse_query(payload):
    if isinstance(payload, list): return payload
    if not isinstance(payload, dict): raise ValueError('Resposta da API inesperada')
    rows = payload.get('rows') or []
    if rows and isinstance(rows[0], list):
        cols = payload.get('colunas') or []
        if len(cols) != len(rows[0]): raise ValueError('Colunas da API inconsistentes')
        return [dict(zip(cols, row)) for row in rows]
    if rows and not isinstance(rows[0], dict): raise ValueError('Linhas da API invalidas')
    return rows


def dataset():
    if DATA_SOURCE == 'csv':
        with CSV.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f, delimiter=';'))
    elif DATA_SOURCE == 'api':
        if not API_KEY: raise HTTPException(503, 'JT_API_KEY ausente no .env')
        try:
            r = requests.post(API_URL + '/query', headers={'X-API-Key': API_KEY},
                json={'sql': f'SELECT data::text AS data, codigo_base, base, uf, rm, sc, total_pedidos, t0_ok, t0_perdido, taxa_t0 FROM public.{TABLE} ORDER BY data, codigo_base', 'params': []},
                timeout=(15, 120))
            r.raise_for_status()
            rows = parse_query(r.json())
        except Exception as exc:
            raise HTTPException(502, f'Falha consultando PostgreSQL pela JT API: {exc}') from exc
    else:
        raise HTTPException(500, 'T0_DATA_SOURCE deve ser csv ou api')
    # Evita contaminação com registros da Orlean e com snapshot parcial de 10/11.
    return [r for r in rows if str(r.get('rm') or '').strip() == 'JOAO MELO SILVA'
            and str(r.get('data') or '')[:10] not in EXCLUDED_DATES]


def stats(items):
    total=sum(int(float(x.get('total_pedidos') or 0)) for x in items)
    ok=sum(int(float(x.get('t0_ok') or 0)) for x in items)
    return {'total':total,'ok':ok,'perdido':total-ok,
            'taxa':round(100*ok/total,2) if total else 0}


def breakdown(items, key):
    groups=defaultdict(list)
    for item in items: groups[str(item.get(key) or 'Não informado')].append(item)
    return [{'nome':k,**stats(v)} for k,v in groups.items()]


def get_default(rows):
    dates=sorted({str(r['data'])[:10] for r in rows if r.get('data')})
    d1=(date.today()-timedelta(days=1)).isoformat()
    return d1 if d1 in dates else next((d for d in reversed(dates) if d<=d1), dates[-1] if dates else d1)

@app.get('/')
def home(): return FileResponse(ROOT/'templates'/'index.html')

@app.get('/api/health')
def health(): return {'ok': True, 'fonte': DATA_SOURCE, 'tabela':TABLE}

@app.get('/api/filtros')
def filtros():
    rows=dataset()
    return {'datas':sorted({str(r['data'])[:10] for r in rows},reverse=True),
            'data_padrao':get_default(rows), 'fonte':DATA_SOURCE,
            **{key:sorted({str(r.get(key) or '').strip() for r in rows if str(r.get(key) or '').strip()})
               for key in ('uf','rm','sc','base')}}

@app.get('/api/dashboard')
def dashboard(data_ini: str='',data_fim: str='',uf: str='',rm: str='',sc: str='',base: str=''):
    rows=dataset()
    if not data_ini and not data_fim: data_ini=data_fim=get_default(rows)
    else: data_ini=data_ini or data_fim; data_fim=data_fim or data_ini
    try:
        date.fromisoformat(data_ini)
        date.fromisoformat(data_fim)
    except ValueError:
        raise HTTPException(400, 'Informe datas válidas no formato AAAA-MM-DD')
    if data_ini>data_fim: raise HTTPException(400,'Data inicial maior que a final')
    filtered=[r for r in rows if data_ini<=str(r.get('data') or '')[:10]<=data_fim
        and (not uf or r.get('uf')==uf)
        and (not rm or r.get('rm')==rm)
        and (not sc or r.get('sc')==sc)
        and (not base or r.get('base')==base)]
    anchor=date.fromisoformat(data_fim)
    week_start=anchor-timedelta(days=anchor.weekday()+7)
    week_end=week_start+timedelta(days=6)
    same=anchor-timedelta(days=7)
    week_ini=(date.fromisoformat(data_ini)-timedelta(days=7)).isoformat()
    week_fim=same.isoformat()
    def scoped(start, end):
        return [r for r in rows if start<=str(r.get('data') or '')[:10]<=end
            and (not uf or r.get('uf')==uf) and (not rm or r.get('rm')==rm)
            and (not sc or r.get('sc')==sc) and (not base or r.get('base')==base)]
    previous=scoped(week_ini, week_fim)
    last_week=scoped(week_start.isoformat(), week_end.isoformat())
    same_day=scoped(same.isoformat(), same.isoformat())
    def comparison(items, start, end):
        return {**stats(items), 'disponivel':bool(items), 'data_ini':start, 'data_fim':end,
                'dias_disponiveis':len({str(r['data'])[:10] for r in items})}
    def comparisons(items_week, items_same):
        return {'semana_passada':comparison(items_week, week_start.isoformat(), week_end.isoformat()),
                'mesmo_dia':comparison(items_same, same.isoformat(), same.isoformat())}
    evolucao=sorted(breakdown(filtered,'data'),key=lambda x:x['nome'])
    scs=sorted(breakdown(filtered,'sc'),key=lambda x:(x['taxa'],-x['total']))
    for item in scs:
        item.update(comparisons([r for r in last_week if str(r.get('sc') or 'Não informado')==item['nome']], [r for r in same_day if str(r.get('sc') or 'Não informado')==item['nome']]))
    bases=sorted(breakdown(filtered,'base'),key=lambda x:(x['taxa'],-x['total']))
    ufs=sorted(breakdown(filtered,'uf'),key=lambda x:x['nome'])
    return {**comparisons(last_week, same_day), 'meta': META,'kpis':stats(filtered),'comparativo_anterior':stats(previous),
        'comparativo_disponivel':bool(previous), 'evolucao':evolucao,'sc':scs,
        'piores_bases':bases,'uf':ufs,'total_bases':len(bases),'fonte':DATA_SOURCE,
        'filtros_aplicados':{'data_ini':data_ini,'data_fim':data_fim,
            'uf':uf,'rm':rm,'sc':sc,'base':base}}

@app.get('/api/exportar')
def exportar(data_ini: str='', data_fim: str='', uf: str='', rm: str='', sc: str='', base: str=''):
    result=dashboard(data_ini, data_fim, uf, rm, sc, base)
    out=io.StringIO(newline='')
    writer=csv.writer(out, delimiter=';')
    writer.writerow(['Base','Pedidos avaliados','T0 OK','T0 perdido','T0 (%)','Meta (%)'])
    for item in result['piores_bases']:
        writer.writerow([item['nome'],item['total'],item['ok'],item['perdido'],str(item['taxa']).replace('.',','), META])
    return Response(content=out.getvalue().encode('utf-8-sig'), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition':'attachment; filename="T0_Bruna_bases.csv"'})
