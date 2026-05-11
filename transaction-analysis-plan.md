# Transaction Analysis Plan Saham Indonesia

## Tujuan

Membangun sistem analisis saham Indonesia yang tidak hanya mengandalkan chart teknikal OHLCV, tetapi dimulai dari konteks pasar: sentimen berita, makro global, rotasi sektor, market movers, aktivitas bandar/smart money, lalu baru melakukan konfirmasi teknikal dan risk-reward pada saham kandidat.

Pendekatan terbaru menggunakan **RapidAPI_IDX sebagai data engine utama**, **RapidAPI_News sebagai sumber berita global/business**, dan **OHLC.dev sebagai fallback/cross-check OHLCV**.

## Batas Kuota

### RapidAPI_IDX

- Kuota target: 1,000 request/bulan.
- Peran: data utama untuk IDX market, sector, stock-specific analysis, broker/smart-money, technical, dan risk-reward.

### RapidAPI_News

- Kuota target: 100 request/bulan.
- Peran: global/business news sentiment.
- Source tersedia:
  - WSJ
  - Bloomberg
  - Benzinga
  - FinancialTimes
  - MarketWatch
  - NYT-Business
  - Coindesk

### OHLC.dev

- Kuota Basic: 1,000 request/bulan.
- Peran: fallback/cross-check raw OHLCV, bukan core source utama.

## Prinsip Utama

1. Jangan brute-force semua saham.
2. Pakai top-down filter dari news, macro, sector rotation, market mover, dan trending stocks.
3. Jalankan stock-specific analysis hanya untuk kandidat paling kuat.
4. Batasi kandidat final menjadi 1–5 saham per hari.
5. Cache semua response agar tidak request ulang data yang sama.
6. Gunakan OHLC.dev hanya jika data OHLCV dari RapidAPI_IDX kurang cukup atau perlu cross-check.
7. Untuk free tier, prioritaskan daily report, bukan polling intraday agresif.

## Arsitektur High-Level

```text
RapidAPI_News / RapidAPI_IDX Global Context
        ↓
Hermes Agent Orchestrator
        ↓
Sector Rotation + Market Mover Scan
        ↓
Candidate Merge & Ranking
        ↓
Stock-Specific Transaction Analysis
        ↓
Technical + Risk Confirmation
        ↓
Trading Thesis / Dashboard / Alert
```

## Hermes Agent Orchestrator

Hermes agent yang sudah online di VPS digunakan sebagai orkestrator multi-agent.

Model utama:

- Claude Sonnet 4.5

Peran Hermes:

- menjalankan beberapa agent paralel,
- mengatur budget request harian,
- mengambil berita dari RapidAPI_News secara hemat,
- mengambil market/sector data dari RapidAPI_IDX,
- memilih kandidat saham,
- menjalankan analisis stock-specific hanya pada kandidat terbatas,
- menghasilkan laporan akhir.

Contoh agent di bawah Hermes:

```text
Hermes Orchestrator
├── Request Budget Manager
├── News Sentiment Agent
├── Global Macro Agent
├── Sector Rotation Agent
├── Market Mover Agent
├── Candidate Ranking Agent
├── Smart Money / Bandar Agent
├── Technical & Risk Agent
└── Thesis Writer Agent
```

## Data Source Layer

## A. RapidAPI_News — News Sentiment

Endpoint utama:

- `rss(source, limit)`
- `source()`

Gunakan untuk:

- global business headlines,
- US market sentiment,
- commodities/economy context,
- crypto/global risk sentiment jika relevan,
- narasi makro untuk IHSG.

Strategi hemat kuota 100 request/bulan:

```text
1 request/hari × 20 hari bursa = 20 request/bulan
3 source utama × 20 hari = 60 request/bulan
5 source utama × 20 hari = 100 request/bulan
```

Rekomendasi mode:

### Conservative News Mode

Ambil 1 source/hari:

- Bloomberg atau MarketWatch.

Estimasi:

```text
20 request/bulan
```

### Normal News Mode

Ambil 3 source/hari:

- Bloomberg
- MarketWatch
- FinancialTimes

Estimasi:

```text
60 request/bulan
```

### Full News Mode

Ambil 5 source/hari:

- Bloomberg
- MarketWatch
- FinancialTimes
- WSJ
- Benzinga

Estimasi:

```text
100 request/bulan
```

Default awal: **Normal News Mode**.

## B. RapidAPI_IDX — Market & Global Context

Endpoint prioritas:

- `getGlobalMarketOverview`
- `getGlobalImpactAnalysis`
- `getIndicesImpact`
- `getCommoditiesImpact`
- `getForexIdrImpact`
- `getEconomicCalendar`
- `getTodayCorporateActions`

Catatan:

- `getMorningBriefing` sempat return 401 Unauthorized, jadi jangan dijadikan dependency utama sampai subscription/permission dipastikan.

Gunakan untuk:

- risk-on/risk-off global,
- IHSG correlation dengan global indices,
- dampak komoditas ke saham IDX,
- dampak USD/IDR ke exporter/importer,
- economic event,
- corporate action harian.

## C. RapidAPI_IDX — Sector & Market Screening

Endpoint prioritas:

- `getSectorRotation`
- `getSectorCorrelation(sector)`
- `getTrendingStocks`
- `getMarketMover(moverType)`
- `getBreakoutAlerts`
- `getMultiMarketScreener`

Gunakan untuk:

- menentukan hot/cold sector,
- market phase,
- top stocks per sector,
- top value/volume/frequency,
- net foreign buy/sell,
- breakout candidate,
- saham dengan commodity/forex exposure.

`getSectorRotation` sangat penting karena output sudah mencakup:

- market phase,
- hot sectors,
- cold sectors,
- momentum score,
- foreign flow,
- top stocks per sector,
- overweight/underweight recommendation.

## D. RapidAPI_IDX — Stock-Specific Transaction Analysis

Endpoint prioritas tinggi:

- `getSmartMoneyFlow(symbol)`
- `getBandarAccumulation(symbol)`
- `getBandarDistribution(symbol)`
- `getRetailBandarSentiment(symbol)`
- `getWhaleTransactions(symbol)`
- `getBrokerSummary(symbol)`
- `getBrokerTradeChart(symbol)`
- `getForeignOwnership(symbol)`
- `getInsiderTradingBySymbol(symbol)`
- `getPumpDumpDetection(symbol)`

Gunakan untuk:

- deteksi akumulasi/distribusi bandar,
- smart money flow,
- whale activity,
- retail vs bandar divergence,
- broker net buy/sell,
- foreign ownership/flow,
- insider/major holder movement,
- risiko pump & dump.

Endpoint ini adalah inti dari transaction analysis karena lebih dekat ke aliran transaksi daripada sekadar OHLCV.

## E. RapidAPI_IDX — Technical & Risk Confirmation

Endpoint prioritas:

- `getTechnicalAnalysis(symbol)`
- `calculateRiskReward(symbol)`
- `getLatestOHLCV(symbol, timeframe, limit)`
- `getOHLCV(symbol, timeframe, from, to)`
- `getOrderbook(symbol)`
- `getRunningTrade(symbols, limit, ...)`
- `getTradebookChart(symbol)`

Gunakan untuk:

- konfirmasi trend,
- support/resistance,
- breakout,
- ATR/volatility,
- risk-reward,
- position sizing,
- running trade/orderbook/tradebook jika kuota memungkinkan.

Karena `getOrderbook`, `getRunningTrade`, dan `getTradebookChart` bersifat real-time/no-cache, gunakan hanya untuk kandidat final atau sesi intraday terbatas.

## F. OHLC.dev — Fallback / Cross-Check

OHLC.dev tetap berguna untuk:

- backup raw OHLCV,
- cross-check candle dari RapidAPI_IDX,
- historical OHLCV cache,
- validasi sederhana jika endpoint RapidAPI_IDX gagal.

Strategi:

- Jangan dipakai untuk full-market scan.
- Hit hanya 1–5 saham final.
- Cache hasil lokal.

## Daily Analysis Flow

## Step 1 — Request Budget Check

Sebelum menjalankan pipeline, Hermes menghitung sisa budget bulanan.

Mode default:

```text
RapidAPI_News: max 3 request/hari
RapidAPI_IDX: max 25 request/hari
OHLC.dev: max 5 request/hari, fallback only
```

Dengan 20 hari bursa:

```text
RapidAPI_News: 3 × 20 = 60 request/bulan
RapidAPI_IDX: 25 × 20 = 500 request/bulan
OHLC.dev: 5 × 20 = 100 request/bulan
```

Sisa kuota IDX sekitar 500 request/bulan untuk eksperimen, retry terbatas, dan analisis intraday sesekali.

## Step 2 — News Sentiment Scan

Ambil headline dari RapidAPI_News.

Default source:

- Bloomberg
- MarketWatch
- FinancialTimes

Output:

```text
Global news sentiment: risk-on / neutral / risk-off
Key themes:
1. Fed rate expectation
2. Commodity movement
3. China/Asia market sentiment
4. Banking/tech/energy global pressure
```

## Step 3 — Global & Macro Context

Gunakan RapidAPI_IDX global tools.

Endpoint default harian:

- `getGlobalMarketOverview`
- `getCommoditiesImpact`
- `getForexIdrImpact`
- `getIndicesImpact`

Output:

```text
Global sentiment: neutral-risk-off
Commodity bias: gold positive, coal weak, oil neutral
Currency pressure: USD/IDR stronger
Likely IDX impact: exporters benefit, importers pressured
```

## Step 4 — Sector Rotation & Market Phase

Gunakan:

- `getSectorRotation`

Opsional jika sektor tertentu menarik:

- `getSectorCorrelation(sector)`

Output:

```text
Market phase: late contraction
Hot sector: Healthcare
Cold sectors: Energy, Financials, Consumer, Property
Action: focus only on leading/improving sectors unless contrarian setup is strong
```

## Step 5 — Market Mover & Attention Scan

Gunakan secukupnya:

- `getTrendingStocks`
- `getMarketMover(top-value)`
- `getMarketMover(top-volume)`
- `getMarketMover(top-frequency)`
- `getMarketMover(net-foreign-buy)`
- `getMarketMover(net-foreign-sell)`
- `getBreakoutAlerts`

Untuk hemat kuota, default harian cukup:

```text
getTrendingStocks = 1 request
getMarketMover(top-value) = 1 request
getMarketMover(net-foreign-buy) = 1 request
getBreakoutAlerts = 1 request
```

Output:

```text
Attention candidates:
- saham trending
- saham top value
- saham dengan net foreign buy
- saham breakout alert
```

## Step 6 — Candidate Merge & Pre-Ranking

Gabungkan kandidat dari:

- hot sector top stocks,
- trending stocks,
- market movers,
- net foreign buy/sell,
- breakout alerts,
- commodity/forex screener jika relevan,
- corporate actions.

Skor awal:

```text
Preliminary Candidate Score =
  0.25 * sector_momentum_score
+ 0.20 * market_attention_score
+ 0.20 * foreign_flow_score
+ 0.15 * news_theme_alignment
+ 0.10 * liquidity_score
+ 0.10 * corporate_action_relevance
```

Ambil hanya top 5–10 kandidat untuk analisis lanjutan.

## Step 7 — Stock-Specific Transaction Analysis

Untuk top kandidat, jalankan bertahap agar hemat kuota.

### Pass 1 — Lightweight Stock Check

Untuk top 5 kandidat:

- `getTechnicalAnalysis(symbol)`
- `calculateRiskReward(symbol)`

Estimasi:

```text
5 saham × 2 endpoint = 10 request
```

Filter menjadi top 3.

### Pass 2 — Transaction/Bandar Check

Untuk top 3 kandidat:

- `getSmartMoneyFlow(symbol)`
- `getBandarAccumulation(symbol)`
- `getBandarDistribution(symbol)`
- `getRetailBandarSentiment(symbol)`

Estimasi:

```text
3 saham × 4 endpoint = 12 request
```

### Pass 3 — Deep Check untuk Final 1–2 Saham

Untuk final 1–2 saham:

- `getWhaleTransactions(symbol)`
- `getBrokerSummary(symbol)`
- `getPumpDumpDetection(symbol)`
- `getOrderbook(symbol)` jika butuh intraday
- `getRunningTrade(symbols)` jika butuh intraday
- `getTradebookChart(symbol)` jika butuh intraday

Estimasi normal:

```text
2 saham × 3 endpoint = 6 request
```

Estimasi intraday optional:

```text
2 saham × 3 real-time endpoint = 6 request tambahan
```

## Step 8 — Final Confirmation & Thesis

Gabungkan semua score.

```text
Final Score =
  0.20 * sector_rotation_score
+ 0.15 * news_macro_alignment
+ 0.15 * market_mover_score
+ 0.20 * smart_money_score
+ 0.15 * bandar_accumulation_score
+ 0.10 * technical_confirmation_score
+ 0.05 * risk_reward_score
```

Format laporan:

```text
Market Context:
- Global sentiment: neutral-risk-off
- IDX market phase: late contraction
- Hot sector: Healthcare

Top Candidate:
- HEAL

Why:
- Sector rotation supports Healthcare
- Stock appears in sector top list
- Smart money / bandar check positive or neutral
- Technical structure acceptable
- Risk-reward acceptable

Risk:
- Market breadth weak
- Avoid chasing if already extended
- Invalid if support breaks with high volume

Action Style:
- Watchlist / wait pullback / breakout confirmation
```

## Request Budget Strategy

## Default Daily Budget

```text
RapidAPI_News:
- 3 RSS source requests

RapidAPI_IDX:
- 4 global/macro requests
- 1 sector rotation request
- 4 market screening requests
- 10 lightweight stock check requests
- 12 transaction/bandar check requests
- 6 deep check requests

Total IDX: ~37 request/hari
```

Jika 20 hari bursa:

```text
37 × 20 = 740 RapidAPI_IDX request/bulan
3 × 20 = 60 RapidAPI_News request/bulan
```

Masih dalam kuota:

```text
RapidAPI_IDX: 740 / 1,000
RapidAPI_News: 60 / 100
```

## Conservative Daily Budget

Untuk lebih aman:

```text
RapidAPI_News: 1 request/hari
RapidAPI_IDX: 20 request/hari
```

Estimasi bulanan:

```text
RapidAPI_News: 20 / 100
RapidAPI_IDX: 400 / 1,000
```

## Expanded Daily Budget

Untuk hari penting saja:

```text
RapidAPI_News: 5 request/hari
RapidAPI_IDX: 50 request/hari
```

Pakai hanya saat:

- market sangat volatil,
- ada FOMC/BI rate decision,
- commodity shock,
- IHSG breakdown/breakout,
- banyak corporate action penting.

## Caching Strategy

Simpan response lokal berdasarkan:

```text
provider
endpoint
params_hash
symbol
analysis_date
fetched_at
raw_response
normalized_json
ttl
```

TTL rekomendasi:

```text
Global overview: 1 trading day
News RSS: 1 trading day
Sector rotation: 1 trading day
Trending stocks: 1 trading day
Market movers: 1 trading day
Technical analysis: 1 trading day
Risk reward: 1 trading day
Smart money/bandar: 1 trading day
Broker summary: 1 trading day
Orderbook/running trade: minutes-level, only if intraday mode
Historical OHLCV: permanent cache
```

Aturan:

- Data historical tidak perlu di-fetch ulang.
- Jangan retry agresif jika request gagal.
- Jika endpoint 401/403, tandai disabled sampai subscription diperbaiki.
- Simpan raw response dan normalized result.
- Semua agent wajib cek cache sebelum request API.

## Minimal Database Schema

### api_usage

```text
id
provider
endpoint
request_date
request_count
monthly_quota
created_at
```

### api_cache

```text
id
provider
endpoint
params_hash
symbol
analysis_date
raw_response
normalized_json
ttl_expires_at
fetched_at
```

### news_items

```text
id
source
published_at
title
summary
url
sentiment_score
themes
created_at
```

### market_context

```text
id
analysis_date
global_sentiment
commodity_bias
forex_bias
indices_bias
summary
created_at
```

### sector_scores

```text
id
analysis_date
sector
sector_id
momentum_score
status
foreign_flow
avg_return_today
recommendation
final_score
reason
```

### market_movers

```text
id
analysis_date
mover_type
symbol
name
price
change_percent
value
rank
created_at
```

### stock_candidates

```text
id
analysis_date
symbol
sector
theme
candidate_reason
pre_score
technical_score
smart_money_score
bandar_score
risk_reward_score
final_score
status
```

### stock_transaction_analysis

```text
id
analysis_date
symbol
smart_money_summary
bandar_accumulation_summary
bandar_distribution_summary
retail_bandar_sentiment
whale_summary
broker_summary
pump_dump_risk
created_at
```

### analysis_reports

```text
id
analysis_date
report_type
summary
recommendations
risks
request_usage_summary
created_at
```

## MVP Scope

## MVP 1 — RapidAPI_IDX-First Daily Report

Input:

- RapidAPI_News RSS,
- RapidAPI_IDX global context,
- RapidAPI_IDX sector rotation,
- RapidAPI_IDX market movers,
- RapidAPI_IDX stock-specific analysis untuk kandidat terbatas.

Output:

- markdown report harian,
- market context,
- top sectors,
- top candidates,
- smart money/bandar summary,
- trading thesis,
- request usage summary.

## MVP 2 — Hermes Multi-Agent Orchestration

Hermes menjalankan:

- request budget manager,
- news sentiment agent,
- global macro agent,
- sector rotation agent,
- market mover agent,
- candidate ranking agent,
- smart money/bandar agent,
- technical/risk agent,
- thesis writer agent.

Output:

- daily report otomatis,
- cache data,
- request budget tracking,
- top 1–5 saham final.

## MVP 3 — Intraday Optional Mode

Intraday mode hanya untuk final 1–2 saham.

Endpoint tambahan:

- `getOrderbook`
- `getRunningTrade`
- `getTradebookChart`
- `getLatestOHLCV` intraday

Gunakan hanya jika:

- ada setup menarik,
- kuota masih aman,
- user memang ingin entry/exit intraday.

## MVP 4 — Dashboard

Dashboard lokal untuk:

- historical reports,
- sector heat,
- market movers,
- candidate ranking,
- smart money/bandar result,
- risk-reward,
- request usage tracking.

## Open Questions

1. Endpoint RapidAPI_IDX mana saja yang aktif di subscription saat ini?
2. `getMorningBriefing` perlu subscription tambahan atau salah permission?
3. RapidAPI_News source mana yang kualitasnya paling bagus untuk market Indonesia?
4. Apakah target utama daily swing, intraday, atau positional?
5. Hermes agent bisa dipanggil via API/CLI dari local project atau harus via VPS endpoint?
6. Perlu report otomatis jam berapa: sebelum market open, saat market berjalan, atau setelah close?
7. Apakah OHLC.dev masih diperlukan jika RapidAPI_IDX OHLCV cukup stabil?

## Rekomendasi Awal

Mulai dari MVP 1 dengan mode hemat:

1. Gunakan RapidAPI_News Normal News Mode: 3 request/hari.
2. Gunakan RapidAPI_IDX sekitar 20–37 request/hari.
3. Ambil sector rotation sebagai filter utama.
4. Ambil market movers dan trending stocks sebagai attention filter.
5. Pilih top 5 kandidat.
6. Jalankan technical + risk check untuk top 5.
7. Jalankan smart money/bandar check untuk top 3.
8. Jalankan deep check untuk final 1–2 saham.
9. Generate report markdown dengan request usage summary.
10. Evaluasi kualitas sinyal selama 2–4 minggu.

Jika sinyalnya berguna, lanjut ke Hermes multi-agent orchestration dan dashboard.
