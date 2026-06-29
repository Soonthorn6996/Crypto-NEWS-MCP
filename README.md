# 🪙 Crypto News & Market MCP Server

MCP Server (Python) สำหรับดึงข้อมูล Crypto จากแหล่ง **ฟรีทั้งหมด** ออกแบบมาให้ deploy เป็น
**MCP Online** บน Railway แล้วเชื่อมเข้ากับ Claude ได้ทันที

## ✨ Tools ที่มีให้ใช้งาน

| Tool | หน้าที่ | แหล่งข้อมูล | ต้องใช้ key? |
|---|---|---|---|
| `get_crypto_price` | ราคา / market cap / %เปลี่ยนแปลง 24h | CoinGecko | ❌ |
| `get_market_overview` | ภาพรวมตลาด + Top N เหรียญ + BTC dominance | CoinGecko | ❌ |
| `get_trending_coins` | เหรียญกระแสแรงใน 24h | CoinGecko | ❌ |
| `get_fear_greed_index` | ดัชนีความกลัว/โลภ | Alternative.me | ❌ |
| `get_crypto_news` | ข่าวล่าสุดจาก CoinDesk/Cointelegraph/Decrypt/Bitcoin Magazine | RSS | ❌ |
| `search_coin` | ค้นหา CoinGecko id จากชื่อ/symbol | CoinGecko | ❌ |
| `get_cryptopanic_news` | ข่าว + sentiment (votes) | CryptoPanic | ✅ (optional) |

> 6 ใน 7 tool ทำงานได้ทันทีโดย **ไม่ต้องมี API key เลย**

---

## 📁 โครงสร้างไฟล์

```
News CRYPTO API/
├── server.py          # ตัว MCP server (FastMCP + Streamable HTTP)
├── requirements.txt   # dependencies
├── railway.json       # config สำหรับ Railway
├── Procfile           # start command สำรอง
├── .python-version    # ระบุ Python 3.12 ให้ Nixpacks
├── .env.example       # ตัวอย่างตัวแปร env (ทุกตัว optional)
└── .gitignore
```

---

## 🧪 1) ทดสอบบนเครื่อง (Local)

```bash
# สร้าง virtual env
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
python server.py
```

Server จะรันที่ `http://localhost:8000/mcp`

ทดสอบด้วย MCP Inspector:
```bash
npx @modelcontextprotocol/inspector
# ใส่ URL: http://localhost:8000/mcp  | Transport: Streamable HTTP
```

---

## 🚂 2) Deploy ขึ้น Railway

### วิธีที่แนะนำ: ผ่าน GitHub
1. push โค้ดทั้งหมดนี้ขึ้น GitHub repo
2. ไปที่ [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. เลือก repo นี้ → Railway จะอ่าน `railway.json` + `requirements.txt` แล้ว build อัตโนมัติ
4. ไปที่ tab **Settings → Networking → Generate Domain** เพื่อเปิด public URL
5. (ถ้าจะใช้ CryptoPanic) ไปที่ tab **Variables** เพิ่ม `CRYPTOPANIC_TOKEN`

> Railway จะ inject ตัวแปร `PORT` ให้เอง — โค้ดอ่านค่านี้อยู่แล้ว ไม่ต้องตั้งเพิ่ม

### วิธีผ่าน CLI
```bash
npm i -g @railway/cli
railway login
railway init
railway up
railway domain          # เปิด public URL
```

หลัง deploy จะได้ URL ประมาณ:
```
https://your-app.up.railway.app/mcp
```

---

## 🔌 3) เชื่อมต่อกับ Claude

### Claude Code (CLI)
```bash
claude mcp add --transport http crypto-news https://your-app.up.railway.app/mcp
```

### Claude.ai / Claude Desktop (Custom Connector)
1. **Settings → Connectors → Add custom connector**
2. ใส่ URL: `https://your-app.up.railway.app/mcp`
3. บันทึก แล้วเริ่มถามได้เลย เช่น:
   - "ราคา BTC, ETH, SOL ตอนนี้เท่าไหร่ (อ้างอิง THB)"
   - "ภาพรวมตลาด crypto วันนี้เป็นยังไง"
   - "ดัชนี Fear & Greed ตอนนี้"
   - "ข่าว crypto ล่าสุด 5 ข่าว"

---

## 🔑 ตัวแปร Environment (ทุกตัว optional)

| ตัวแปร | ใช้ทำอะไร | ไม่ใส่จะเป็นยังไง |
|---|---|---|
| `COINGECKO_DEMO_KEY` | เพิ่ม rate limit CoinGecko | ใช้ได้ปกติ แต่ rate limit ต่ำกว่า |
| `CRYPTOPANIC_TOKEN` | เปิด tool `get_cryptopanic_news` | tool นี้จะแจ้งให้ไปสมัคร (tool อื่นใช้ได้หมด) |
| `PORT` | พอร์ตที่รัน | Railway ตั้งให้เอง / local = 8000 |

---

## ⚠️ หมายเหตุ

- **ความปลอดภัย:** URL นี้เป็น public — ใครมี URL ก็เรียกได้ แต่ข้อมูลทั้งหมดเป็นข้อมูลสาธารณะ (read-only) จึงเสี่ยงต่ำ ถ้าต้องการจำกัดการเข้าถึง แนะนำเพิ่มชั้น auth ภายหลัง
- **Rate limit:** CoinGecko free มีโควต้าจำกัด ถ้าเจอ error 429 ให้เว้นช่วงแล้วลองใหม่ หรือใส่ `COINGECKO_DEMO_KEY`
- ข้อมูลทั้งหมดเพื่อการศึกษาเท่านั้น ไม่ใช่คำชี้ชวนในการลงทุน
