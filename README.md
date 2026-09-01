# ✈️ flight-tracker — Itacaré / Ano Novo 2026–2027

Rastreador de voos flexível e multi-provedor, feito sob medida para **monitorar
as melhores ofertas de passagem para passar o Réveillon em Itacaré (BA)**.

Diferente do Google Voos, ele entende as suas **regras específicas de viagem** e
ranqueia as opções por **custo efetivo** — não só o preço da passagem, mas o
custo e o tempo de deslocamento em São Paulo e na Bahia (inclusive o fato de
**Salvador ser bem mais longe de Itacaré que Ilhéus**). Quando aparece algo novo
ou melhor, ele te avisa **na hora, por email e WhatsApp**.

---

## O que ele monitora (suas regras)

| Regra | Como está configurado |
|---|---|
| Janela de datas | 24-dez-2026 a 07-jan-2027 |
| Duração | entre **6 e 14 noites** |
| Bloco inegociável | **30-dez a 03-jan** sempre dentro da viagem (viaja até 30/12, volta só a partir de 03/01) |
| Origem (SP) | **Congonhas (CGH)** › Guarulhos (GRU) › Viracopos (VCP) |
| Destino (BA) | **Ilhéus (IOS)** › Salvador (SSA) |
| Companhia | **LATAM** preferida, mas aceita outras |
| Passageiros | **2** (principal) e também rastreia **1** |
| Objetivo | menor gasto **e** menor tempo de transporte, contando aluguel de carro e a distância extra de Salvador |

Tudo isso vive em [`config.yaml`](config.yaml) e é fácil de ajustar.

São **32 combinações de datas** válidas × 6 rotas × 2 tamanhos de grupo,
buscadas em vários provedores a cada ciclo.

---

## Como ele decide o que é "melhor": custo efetivo

O preço da passagem sozinho engana. Uma passagem barata para **Salvador** pode
sair mais cara no fim, porque de Salvador até Itacaré são ~4–5h (com ferry,
combustível e mais diárias de carro), contra ~1h15 saindo de **Ilhéus**. Então o
ranking usa:

```
custo_efetivo = passagem
              + custo de solo em SP     (aeroporto ⇄ sua casa)
              + custo de solo na BA     (aeroporto ⇄ Itacaré; ferry/combustível de Salvador)
              + valor do tempo          (horas de transporte × R$/hora)
              + preferência de cia       (leve empurrão pró-LATAM)
              + penalidade de escala     (leve empurrão pró-voo direto)
```

A passagem domina o cálculo; os outros termos servem de **desempate** e fazem
Ilhéus ganhar de uma Salvador só um pouquinho mais barata. Todos os pesos
(R$/hora, penalidades, custos de solo de cada aeroporto) são ajustáveis em
`config.yaml`, na seção `scoring` e nos blocos `origins`/`destinations`.

Exemplo real de saída (dados de demonstração):

```
--- 2 passageiro(s) ---
 1.   R$ 2.513 efet. (passagem R$ 2.333) | CGH→IOS AD direto | 28/12→04/01 (7n)
 2.   R$ 2.590 efet. (passagem R$ 1.568) | VCP→SSA G3 direto | 28/12→04/01 (7n)
 3. ★ R$ 2.671 efet. (passagem R$ 1.971) | CGH→SSA LA direto | 28/12→04/01 (7n)
```

Repare: a opção 2 tem a **passagem mais barata** (R$ 1.568), mas cai para 2º
lugar porque o transporte por Salvador + Viracopos come a diferença.

---

## De onde vêm os preços (provedores)

Nenhuma API sozinha tem "todos os voos", então o tracker **agrega vários
provedores** e junta os resultados (removendo duplicatas e ficando com a fonte
mais barata). Cada um é opcional: sem credencial, ele é ignorado em silêncio.

| Provedor | O que é | Credencial (grátis) |
|---|---|---|
| **Amadeus** | GDS oficial, inventário amplo | `AMADEUS_CLIENT_ID/SECRET` — [developers.amadeus.com](https://developers.amadeus.com) |
| **Kiwi Tequila** | Agrega low-cost e itinerários mistos | `TEQUILA_API_KEY` — [tequila.kiwi.com](https://tequila.kiwi.com) |
| **SerpApi (Google Flights)** | A visão do próprio Google Voos | `SERPAPI_API_KEY` — [serpapi.com](https://serpapi.com) (100 buscas/mês grátis) |
| **Travelpayouts / Aviasales** | Preços em cache (sinal rápido de queda) | `TRAVELPAYOUTS_TOKEN` — [travelpayouts.com](https://www.travelpayouts.com) |
| **sample** | Dados simulados p/ testar offline | nenhuma |

> **Por que não raspar direto o site da LATAM/GOL/Azul?** Scraping dos sites das
> companhias é instável e costuma violar os termos de uso. Os agregadores acima
> cobrem essas companhias de forma estável e legal — a preferência por LATAM
> continua valendo no ranking (`preferred_airlines`).

Comece com **um** provedor (o Amadeus é o mais fácil de liberar) e vá somando.
Quanto mais provedores, mais cobertura.

---

## Alertas: email + WhatsApp

- **Email (SMTP):** funciona com qualquer servidor. Para Gmail/Workspace, gere um
  *App Password* em [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
  e preencha `SMTP_USER`/`SMTP_PASSWORD`. Destinatário em `config.yaml`.
- **WhatsApp (CallMeBot, grátis):** ative uma vez —
  1. adicione **+34 644 51 95 23** aos contatos;
  2. mande no WhatsApp: `I allow callmebot to send me messages`;
  3. copie a `apikey` que ele responder para `CALLMEBOT_APIKEY` (e seu número em
     `CALLMEBOT_PHONE`).

O tracker só alerta quando há **novidade**: primeira leitura, novo melhor preço
(queda ≥ `min_improvement_brl`) ou passagem atingindo a meta
(`target_price_brl`). Assim você não recebe spam a cada ciclo.

---

## Rodando localmente

```bash
pip install -r requirements.txt
cp .env.example .env        # preencha as credenciais que tiver
cp config.yaml config.local.yaml   # (opcional) ajustes locais

# ver as combinações de datas válidas
python -m flight_tracker dates --config config.yaml

# buscar e mostrar o ranking, SEM alertar nem salvar estado
PYTHONPATH=src python -m flight_tracker run --config config.yaml --dry-run

# testar os canais de alerta
PYTHONPATH=src python -m flight_tracker test-notify --config config.yaml

# execução real (alerta se houver novidade, salva o estado)
PYTHONPATH=src python -m flight_tracker run --config config.yaml
```

Para experimentar **sem nenhuma credencial**, ative o provedor `sample` no
`config.yaml` (`enabled: true`) — ele gera ofertas realistas e determinísticas.

---

## Monitoramento automático (GitHub Actions)

O workflow [`.github/workflows/track.yml`](.github/workflows/track.yml) roda o
tracker **a cada 4 horas** (e no botão *Run workflow*), e commita o estado de
volta para lembrar os melhores preços entre execuções.

Para ativar, adicione os **Secrets** do repositório
(*Settings → Secrets and variables → Actions*):

```
AMADEUS_CLIENT_ID, AMADEUS_CLIENT_SECRET
TEQUILA_API_KEY
SERPAPI_API_KEY
TRAVELPAYOUTS_TOKEN
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
CALLMEBOT_PHONE, CALLMEBOT_APIKEY
```

Você não precisa preencher todos — o que faltar é simplesmente pulado. Com pelo
menos um provedor + o email/WhatsApp configurados, o monitoramento roda sozinho.

---

## Estrutura do projeto

```
src/flight_tracker/
  config.py         carga de config (YAML) + segredos via env
  dates.py          gera os pares de datas válidos a partir das regras
  scoring.py        modelo de "custo efetivo"
  models.py         dataclasses (oferta, opção pontuada, busca)
  state.py          memória entre execuções + decisão de alerta
  report.py         formatação (console, email HTML, WhatsApp)
  tracker.py        orquestração: buscar → juntar → pontuar → alertar
  cli.py            interface de linha de comando
  providers/        amadeus, kiwi_tequila, serpapi, travelpayouts, sample
  notifiers/        email (SMTP), whatsapp (CallMeBot)
tests/              testes de datas, scoring e ponta-a-ponta
config.yaml         SUA configuração (sem segredos)
.github/workflows/  automação agendada
```

Testes: `PYTHONPATH=src python -m pytest -q`

---

## Ajustes rápidos que você pode querer

- Mudar o alvo de preço: `alerts.target_price_brl`.
- Rastrear mais/menos datas: `min_nights`/`max_nights` (o bloco 30-dez↔03-jan é
  garantido pela lógica de `core_start`/`core_end`).
- Mudar o quanto o tempo pesa: `scoring.value_per_hour_brl`.
- Recalibrar Salvador vs Ilhéus: `ground_cost_roundtrip_brl` e `hours_each_way`
  em `destinations`.
- Rodar com mais frequência: ajuste o `cron` no workflow.
