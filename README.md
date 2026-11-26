# Running Plan 2026–2027

App pessoal do plano anual de corrida (meta: baixar o tempo na meia maratona). Projeto de hobby, separado do Hub Rafael.

- **App** (`index.html`): treino do dia com planejado x feito, calendário mensal, 51 semanas, evolução (carga, forma, volume, intensidade, força, recuperação, previsão de prova), zonas por FC e ritmo, registro manual com esforço percebido e notas, `.FIT` para o relógio e agenda `.ics`. Menu lateral no computador; atalhos H, C, S, E, T, A e setas.
- **Login e dados** (Supabase, projeto `running-plan`, região São Paulo): "Entrar com a Microsoft" e todos os registros num banco. Abre igual em qualquer aparelho; cada alteração guarda a versão anterior (tabela `history`).
- **Ponte Garmin, ida** (`tools/garmin_sync.py`): envia e agenda os treinos no Garmin Connect, todo domingo.
- **Ponte Garmin, volta** (`tools/garmin_results.py`): a cada 2 horas busca corridas, força, sono, VFC, FC de repouso, prontidão e previsões e grava no banco.
- **Cópia de segurança** (`backup.yml`): toda segunda, o banco inteiro vai para `backup/running-plan.json` neste repositório.
- **Hospedagem**: Azure Static Web Apps (plano gratuito) em https://brave-wave-02129a510.8.azurestaticapps.net

> **Mantenha o repositório privado** (a cópia de segurança semanal tem dados de saúde). Deixe o GitHub Pages desligado.

## Segurança
- Só o e-mail da tabela `allowed_emails` consegue criar conta; qualquer outra conta Microsoft é recusada no cadastro.
- Regras de acesso (RLS) em todas as tabelas: cada usuário só lê e grava o que é seu.
- No site vai só a chave **pública** (`sb_publishable_…`), protegida pelas regras. A chave **secreta** (`sb_secret_…`) fica apenas no segredo `SUPABASE_SECRET_KEY` do GitHub, usada pelos robôs.
- Pastas internas (`tools/`, `backup/`, `.github/`) não são servidas pelo site.

## Configuração (uma vez)
O passo a passo completo está no documento `running-plan-passos-supabase` do projeto Running & Fitness. Resumo:
1. **Azure, Registros de aplicativo**: app "Running Plan", só contas pessoais Microsoft, redirect **Web** `https://daeokijmcstzxiaryaks.supabase.co/auth/v1/callback`, segredo do cliente (o **Valor**).
2. **Supabase, Authentication**: provedor Azure com o Client ID, o Valor do segredo e Tenant URL `https://login.microsoftonline.com/9188040d-6c67-4c5b-b112-36a304b66dad`; em URL Configuration, Site URL e Redirect URL do site.
3. **GitHub, segredos**: `AZURE_STATIC_WEB_APPS_API_TOKEN`, `SUPABASE_SECRET_KEY`, `GARMIN_TOKENS`.
4. Entrar uma vez no site (cria o seu usuário) e rodar os fluxos em Actions.

## Garmin
No computador, com Python 3.10+:
```bash
pip install -r requirements.txt
python tools/garmin_login.py      # imprime o GARMIN_TOKENS (trate como senha)
```
Em **Actions**: "Enviar treinos ao Garmin" (primeiro com "Só simular") e "Buscar resultados do Garmin". Depois rodam sozinhos.

Como o app usa os dados:
- **Casamento**: cada corrida vai para o treino planejado do mesmo dia; se o dia não tinha treino, tenta o anterior ou o seguinte, desde que a corrida tenha ao menos 60% da duração planejada.
- **Status**: feito (75% ou mais da distância planejada), parcial ou não feito.
- **Carga**: TRIMP de Banister (duração x intensidade pela FC; sem FC, pelo esforço percebido). Corridas e força na mesma escala. Condicionamento = 42 dias, fadiga = 7 dias, forma = a diferença.
- **Prontidão**: FC de repouso 5 bpm acima do normal, VFC fora da faixa ou sono abaixo de 6 h sugerem trocar o treino de qualidade por regenerativo.

Rodar sem o GitHub: exporte `GARMIN_TOKENS` e `SUPABASE_SECRET_KEY` e use `python tools/garmin_sync.py --dry-run` ou `python tools/garmin_results.py --days 30`. Sem a chave do Supabase, o robô de resultados grava em `data/*.json` (só para teste). `python tools/garmin_results.py --sample /tmp/exemplo` gera dados fictícios.

Limites: a ponte usa a biblioteca **não oficial** [python-garminconnect](https://github.com/cyberjunky/python-garminconnect). Se o login falhar, gere o token de novo. Sem internet, use **Baixar para o relógio** e copie o `.FIT` para `GARMIN/NewFiles`.

## Prévia local
`python -m http.server` na pasta e abra `http://localhost:8000`. Sem login no Supabase o app vai para a tela de entrar; `?hoje=2027-05-29` simula outra data.

## Arquivos
| Arquivo | Para quê |
| --- | --- |
| `index.html` | O app |
| `login.html` | Tela de entrada com a Microsoft (via Supabase) |
| `assets/supabase.js` | Biblioteca do Supabase, hospedada no próprio site |
| `plan.json` | As 51 semanas (de 23/11/2026), 201 treinos, provas e zonas |
| `staticwebapp.config.json` | Cabeçalhos de segurança e pastas internas bloqueadas |
| `tools/supa.py` | Acesso dos robôs ao banco (chave secreta) |
| `tools/garmin_login.py` | Login único no Garmin, gera o `GARMIN_TOKENS` |
| `tools/garmin_sync.py` | Envia e agenda treinos no Garmin Connect |
| `tools/garmin_results.py` | Busca resultados e recuperação; `--export` faz a cópia de segurança |
| `tools/build_plan.py` | Gera o `plan.json` |
| `.github/workflows/deploy-azure.yml` | Publica o app no Azure quando o app muda |
| `.github/workflows/garmin-sync.yml` | Envio semanal ao Garmin + botão manual |
| `.github/workflows/garmin-results.yml` | Busca de resultados a cada 2 horas |
| `.github/workflows/backup.yml` | Cópia de segurança semanal do banco |
| `assets/rp-*` | Logo, ícones do app, favicon e manifesto |

## Banco (Supabase `running-plan`)
`activities` (Garmin e manuais, exclusão só marca `deleted_at`), `wellness_days`, `race_predictions`, `notes` (esforço e notas), `progress` (marcações), `settings`, `sent_workouts`, `robot_runs`, `history` (versão anterior de cada alteração), `allowed_emails`.
