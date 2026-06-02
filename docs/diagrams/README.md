# 簡報架構圖 (Mermaid)

報告用的系統 / 架構圖,Mermaid 原始碼 + 渲染 PNG。

## 目錄
- `clean/` — **乾淨可攜版** mermaid(無 logo、純文字),直接貼進 [mermaid.live](https://mermaid.live) 或簡報外掛即可渲染。
- `src/` — **美化版** mermaid 模板,用 `@@logo@@` token 內嵌技術 logo + 配色 class。
- `logos/` — 技術 logo SVG(devicon)。
- `png/` — 已渲染輸出。
- `theme.json` / `puppeteer.json` / `build.py` — 渲染管線。

## 圖對應簡報頁
| 檔 | 簡報頁 | 內容 |
|---|---|---|
| `05-logical-architecture` | 5 | 系統架構圖 (Modular Monolith) |
| `06-cloud-native-deployment` | 6 | GKE 部署拓樸 |
| `08-er-diagram` | 8 | 資料模型 ER |
| `09-seq-report-submit` | 9 | 核心流程① 員工提交回報 |
| `10-seq-manager-remind` | 10 | 核心流程② 主管催報 |
| `00-request-lifecycle` | 加分 | Request 三條路徑 |

## 重新渲染美化版
```bash
cd docs/diagrams
python3 build.py        # 把 src/ 的 @@logo@@ 內嵌成 data URI → build/
export PUPPETEER_EXECUTABLE_PATH="<chrome-for-testing 路徑>"
npx -y @mermaid-js/mermaid-cli@11 -i build/01-deployment.mmd \
    -o png/01-deployment.png -c theme.json -p puppeteer.json -b white -s 2.5
```

> 內容已對齊實際程式碼:讀路徑先走 Redis 統計快取(5s)→ miss 才打讀副本;
> 密碼雜湊為 bcrypt;PgBouncer ×3→6 / 2000→100;HPA backend 3-60、frontend 2-10;
> Grafana 16 面板、5 條告警。
