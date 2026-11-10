# T0 Bruna Regional

Painel J&T com filtros de período, UF, R/M, S/C e base. Quatro cards principais, evolução diária, desempenho por S/C e tabela de bases com exportação CSV. Meta T0: 70%.

feito por Erison Neto - Analista de Dados Pleno

## Executar no Windows

Copie `.env.example` para `.env` e configure `JT_API_KEY`. A API deve disponibilizar a tabela `public.t0_joao_melo_diario` pelo endpoint `/query`.

```powershell
py -m pip install -r requirements.txt
py -m uvicorn main:app --host 127.0.0.1 --port 8020
```

Abra http://127.0.0.1:8020.

## Hospedagem

Build: `pip install -r requirements.txt`

Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Health check: `/api/health`

Configure `JT_API_URL`, `JT_API_KEY` e `T0_DATA_SOURCE=api` no ambiente de hospedagem. A chave nunca é enviada ao navegador. O health check confirma a aplicação; não testa a conexão externa.

O repositório contém somente código. Credenciais e bases operacionais devem permanecer fora do GitHub. O snapshot parcial de 10/11/2026 permanece excluído; a data padrão é o último dia disponível até D-1.
