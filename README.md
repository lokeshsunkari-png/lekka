# Lekka — Every rupee, counted

Mee sontha money app. **Claude avasaram ledu.** Phone lo install avutundi, internet lekunda panichestundi.
Agents prathi gantaki market, news, IPO updates techchi pedatayi. Ivi GitHub lo free ga run avutayi.

```
┌──────────────── YOUR PHONE (works offline) ────────────────┐
│ Lekka app (installed)                                       │
│  • expenses, income, invest, udhaar, tally, advisor, plan   │
│  • data: IndexedDB + local copy + 21 daily restore points   │
└──────┬─────────────────────────────────┬────────────────────┘
       │ reads (only when online)         │ syncs (optional, when online)
┌──────▼───────────────┐         ┌───────▼────────────────────┐
│ GitHub (free)        │         │ Google Firebase (free)     │
│  🛰️ Market agent  1h │         │  your entries, your Google │
│  🛰️ News agent    3h │         │  login only — every device │
│  → data/*.json       │         │  shows same data live      │
└──────────────────────┘         └────────────────────────────┘
```

> **Privacy:** mee expenses **eppudu GitHub ki vellavu**. GitHub lo unde data market prices, news matrame. Mee personal data phone lo untundi. Cloud sync on chesthe mee sontha Firebase account lo kuda untundi (mee Google login tho matrame open avutundi).

---

## Step 1 · Publish the app and agents (15 min, one time, laptop is easiest)

1. **github.com** lo free account create cheyyandi. Username note cheskondi (udaharanaki `lokesh-sk`).
2. Top right **＋ → New repository** → Name: `lekka` → **Public** select cheyyandi → **Create repository**.
3. **"uploading an existing file"** link nokkandi → ee ZIP lo unna **anni files and folders** drag cheyyandi (`.github` folder kuda) → **Commit changes**.
   - `.github` folder kanapadakapothe: **Add file → Create new file** → name lo `.github/workflows/agents.yml` ani type chesi, ZIP lo unna aa file content paste chesi commit cheyyandi.
4. **Settings → Pages** → Source: *Deploy from a branch* → Branch: `main` / `(root)` → **Save**.
5. **Settings → Actions → General** → *Workflow permissions*: **Read and write permissions** → **Save**.
6. **Actions** tab → *"I understand… enable"* → **Lekka agents** → **Run workflow**. 1 nimisham lo green ✓ vastundi.
7. 2–3 nimishala tarvata app ikkada open avutundi: **`https://<username>.github.io/lekka/`**

## Step 2 · Install on your phone

1. Aa link ni phone lo **Chrome** lo open cheyyandi.
2. **⋮ menu → Install app** (leda *Add to Home screen*). Home screen meeda Lekka icon vastundi.
3. App open chesi Home lo **🛰️ Agent alerts → Turn on notifications** nokkandi.
4. Offline voice kosam: Gboard → Settings → Voice typing → **Offline speech recognition** → **Telugu** + **English (India)** download cheyyandi.

Ippati nunchi app internet lekunda open avutundi. Agents data mobile data unnappudu automatic ga update avutundi.

## Step 3 · Move your existing data

| From | How |
|---|---|
| Lekka inside Claude | ⚙️ → Backup & Excel → **Backup** (text copy avutundi) → WhatsApp "Message yourself" lo paste → kotha app lo ⚙️ → **Restore / merge** → paste → **Merge** |
| Old offline HTML file | Aa file lo ⚙️ → **Backup** (file download avutundi) → kotha app lo ⚙️ → **Restore / merge** → aa file choose → **Merge** |

Merge **eppudu data delete cheyyadu**. Missing unna entries ni add chestundi, rendu chotla unte kotha version unchutundi.

## Step 4 · Cloud sync: multiple devices + phone poina data safe (10 min, free)

1. **console.firebase.google.com** → **Add project** → name `lekka` → Analytics **off** → Create.
2. **Build → Authentication → Get started → Google → Enable** → Save.
3. **Authentication → Settings → Authorized domains → Add domain** → `<username>.github.io`
4. **Build → Firestore Database → Create database** → location **asia-south1 (Mumbai)** → *production mode*.
5. **Firestore → Rules** tab → ee rules paste chesi **Publish** cheyyandi:
   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{db}/documents {
       match /users/{uid}/{document=**} {
         allow read, write: if request.auth != null && request.auth.uid == uid;
       }
     }
   }
   ```
6. **⚙️ Project settings → Your apps → `</>` (Web)** → nickname `lekka` → Register → `firebaseConfig = {…}` block copy cheyyandi.
7. Lekka → ⚙️ → **🛡️ Data safety → Cloud sync → Set up** → paste → **Connect** → **Sign in** (mee Google account).
8. Laptop / rendo phone lo ade link open chesi, ade config paste chesi, ade Google account tho sign in cheyyandi. Anni devices lo same data live ga kanipistundi.

Free limits (50,000 reads / 20,000 writes per day) roju 100s of entries ki kuda saripotayi. Card details avasaram ledu.

---

## 🛡️ Data safety plan: "emina sare data miss avvakudadu"

| What goes wrong | What protects you | You do |
|---|---|---|
| App crashes mid-entry | Prathi Save rendu chotla (IndexedDB + local copy) ventane write avutundi. App close/background lo kuda flush avutundi | Nothing |
| Browser storage gets cleared / corrupted | Rendu copies lo okati poina rendodi nunchi auto-recover avutundi. Rendu poina latest restore point nunchi | Nothing |
| Wrong edit / accidental delete | 21 daily restore points + 90-day **Recently deleted** | ⚙️ → Data safety → Restore point / View |
| Phone lost, broken, reset | Firebase cloud sync (Layer 3) + weekly backup file in Google Drive (Layer 4) | Kotha phone lo app install → sign in, leda backup file restore |
| Want to see on laptop / second phone | Firebase sync, live | Same link, same Google sign-in |
| No internet for days | Anni offline lo panichestayi. Cloud writes queue lo undi, online raagane sync avutayi | Nothing |
| GitHub / agents down | App cached ga undi, panichestundi. Last prices chupistundi, direct price fallback undi | Nothing |
| Firebase down | Phone copy + restore points + backup file | Nothing |
| Everything else fails | CSV export (⚙️ → Excel) Excel / Google Sheets lo open avutundi | Prathi nela okasari CSV save cheyyandi |

**Mee routine (2 nimishalu/week):** Sunday tally → ⚙️ → **Share backup** → Google Drive. Data safety card lo **5/5 layers active** ani undali.

---

## 🛰️ The agents

| Agent | Runs | What it brings | Your phone uses it for |
|---|---|---|---|
| **Market agent** (`agents/market_agent.py`) | every 10 min in market hours (Mon–Fri 08:30–16:30 IST), hourly otherwise | Nifty, Sensex, India VIX, gold & silver (India estimate), Brent, USD/INR, 1-yr highs/lows | Live Grow cards, portfolio value, alerts (Nifty −2%, >10% correction, gold ±2.5%, oil >$110/<$85, rupee move, VIX >20) |
| **IPO agent** (`agents/ipo_agent.py`) | with the market agent | Open + upcoming IPOs (NSE, news fallback), auto-screen 0–100, SKIP/OPTIONAL/CONSIDER, rough listing-gain guess from subscription | Home → 🚀 IPO radar with a personal verdict (your emergency fund, debt, 5% bucket) |
| **News & geo agent** (`agents/news_agent.py`) | every 3rd run | Headlines: RBI, oil/war, gold, markets, IPOs, geopolitics, rupee, tax | News card with tone + "your rule" for each topic |
| **On-phone agent** (inside the app) | every 2 min while open; Android background check when installed | Your personal alerts: budget overshoot, gold 20% above your average price, etc. | Notifications |

- **Manual refresh:** GitHub → Actions → Lekka agents → **Run workflow**, leda app lo **↻ Refresh now**.
- **Gold duty maarite:** `.github/workflows/agents.yml` lo `GOLD_PREMIUM` (default `1.09` = duty + GST) maarchandi. Mee city rate ki match cheyyalante app lo **Match my jeweller rate** okasari vadandi.
- GitHub "scheduled workflow disabled" ani email pampithe: Actions → Lekka agents → **Enable workflow**.

### Honest limits
- “Every minute” isn't possible for free: GitHub runs agents at most every 5–10 minutes (often a few minutes late). The app checks for new data every 2 minutes while open.
- IPO screens and listing guesses are rough first looks, not predictions. NSE often blocks cloud servers; then the agent falls back to news headlines (fewer details).
- Prices **public data sources** nunchi vastayi: Yahoo Finance chart endpoint, open.er-api.com, gold-api.com. Ivi official exchange feeds kaadu, konni nimishalu late undochu. Okavela okati panicheyyakapothe agent last data ne unchutundi, app direct gold/₹ fallback vadutundi.
- Gold/silver India price **estimate** matrame. Jeweller rate city ni batti, making charges ni batti maarutundi.
- Background notifications Android Chrome lo app install chesinappude vastayi. Chrome rojuki konnisarle allow chestundi, minute-by-minute kaadu.
- AI chat Claude version lo matrame untundi. Migatha advisor rules, "Can I buy?", investment plan anni ikkada Claude lekunda panichestayi.
- Idi education kosam. SEBI-registered advice kaadu.
