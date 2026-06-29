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
├── oauth_provider.py  # OAuth 2.1 provider + หน้า login (สำหรับ Claude.ai/Cowork web)
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
# ไม่ได้ล็อก token
claude mcp add --transport http crypto-news https://your-app.up.railway.app/mcp

# ถ้าล็อกด้วย MCP_BEARER_TOKEN ให้ส่ง header ไปด้วย
claude mcp add --transport http crypto-news https://your-app.up.railway.app/mcp \
  --header "Authorization: Bearer <YOUR_TOKEN>"
```

### Claude.ai / Cowork (Web) — ผ่าน OAuth 2.1
หน้า web รองรับเฉพาะ OAuth (ไม่รองรับ static token) — ต้องตั้งค่า `OAUTH_LOGIN_PASSWORD` ก่อน
1. **Settings → Connectors → Add custom connector**
2. ใส่ URL: `https://your-app.up.railway.app/mcp` (ไม่ต้องกรอก Client ID/Secret)
3. กด connect → ระบบจะเปิดหน้า **login** ของ server → กรอก `OAUTH_LOGIN_PASSWORD`
4. กด "อนุญาต & เชื่อมต่อ" → Claude จะได้รับ token อัตโนมัติ แล้วใช้งานได้เลย เช่น:
   - "ราคา BTC, ETH, SOL ตอนนี้เท่าไหร่ (อ้างอิง THB)"
   - "ภาพรวมตลาด crypto วันนี้เป็นยังไง"
   - "ดัชนี Fear & Greed ตอนนี้"
   - "ข่าว crypto ล่าสุด 5 ข่าว"

> วิธีนี้เป็น OAuth 2.1 เต็มรูปแบบ (Dynamic Client Registration + PKCE) ที่ MCP SDK จัดการให้
> การล็อกที่แท้จริงอยู่ที่หน้า login — ใครไม่รู้ password ก็เชื่อมต่อไม่ได้

---

## 🔑 ตัวแปร Environment (ทุกตัว optional)

| ตัวแปร | ใช้ทำอะไร | ไม่ใส่จะเป็นยังไง |
|---|---|---|
| `OAUTH_LOGIN_PASSWORD` | เปิด **OAuth 2.1** (สำหรับ Claude.ai/Cowork web) — รหัสที่กรอกหน้า login | ไม่เปิด OAuth |
| `PUBLIC_URL` | base URL สาธารณะ (OAuth issuer) | บน Railway อ่านจาก `RAILWAY_PUBLIC_DOMAIN` ให้เอง |
| `MCP_BEARER_TOKEN` | ล็อกแบบ **Bearer** (เหมาะกับ CLI) — ทำงานคู่กับ OAuth ได้ | ไม่เปิด bearer |
| `COINGECKO_DEMO_KEY` | เพิ่ม rate limit CoinGecko | ใช้ได้ปกติ แต่ rate limit ต่ำกว่า |
| `CRYPTOPANIC_TOKEN` | เปิด tool `get_cryptopanic_news` | tool นี้จะแจ้งให้ไปสมัคร (tool อื่นใช้ได้หมด) |
| `PORT` | พอร์ตที่รัน | Railway ตั้งให้เอง / local = 8000 |

> **เลือกโหมด auth อัตโนมัติ:** ตั้ง `OAUTH_LOGIN_PASSWORD` → OAuth · ตั้งแค่ `MCP_BEARER_TOKEN` → Bearer · ไม่ตั้งอะไร → Open
> ตั้งทั้งคู่ได้: web ใช้ OAuth, CLI ใช้ static token เดิม (ทำงานพร้อมกัน)

---

## ⚠️ หมายเหตุ

- **ความปลอดภัย:** ใช้บน web → ตั้ง `OAUTH_LOGIN_PASSWORD` (OAuth 2.1, กั้นด้วยหน้า login) · ใช้บน CLI → ตั้ง `MCP_BEARER_TOKEN` · request ที่ไม่มี/ผิด credential จะได้ HTTP 401 ถ้าไม่ตั้งอะไรเลย server จะเปิดให้ใครก็เรียกได้ (ข้อมูล read-only สาธารณะ เสี่ยงต่ำ แต่ควรล็อกไว้)
- **OAuth state เป็น in-memory:** เมื่อ Railway redeploy/restart token จะหาย ต้อง authorize ใหม่บน web (ยอมรับได้สำหรับ connector ส่วนตัว)
- **Rate limit:** CoinGecko free มีโควต้าจำกัด ถ้าเจอ error 429 ให้เว้นช่วงแล้วลองใหม่ หรือใส่ `COINGECKO_DEMO_KEY`
- ข้อมูลทั้งหมดเพื่อการศึกษาเท่านั้น ไม่ใช่คำชี้ชวนในการลงทุน
