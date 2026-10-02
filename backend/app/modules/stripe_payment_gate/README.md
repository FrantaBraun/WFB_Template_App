# Modul `stripe_payment_gate` – platební brána Stripe

Manuál k modulu platební brány Stripe: co modul dělá, jak ho zapnout a napojit na vlastní aplikaci a jaké **povinné informace** musí web s online platbami zveřejnit (Česko, EU, zákazníci mimo EU, požadavky Stripe).

> ⚠️ **Právní texty v modulu jsou vzor, ne právní rada.** Jsou psané pro českého podnikatele, který prodává online spotřebitelům v ČR, EU i mimo EU. Před spuštěním každé aplikace je projděte vůči skutečnému byznysu (zboží × digitální obsah × služby, plátce/neplátce DPH, doprava, předplatné, …) a ideálně je nechte zkontrolovat právníkem.

---

## 1. Co modul umí

| Část | Co dělá |
|---|---|
| **Zahájení platby** | `POST /api/modules/stripe_payment_gate/checkout` založí platbu a Stripe Checkout Session. Prohlížeč přesměruje na hostovanou platební stránku Stripe (karty, Apple/Google Pay, další metody podle nastavení účtu Stripe; 3-D Secure/SCA řeší Stripe). |
| **Zachycení výsledku** | Webhook `POST /api/modules/stripe_payment_gate/webhook` s ověřeným podpisem, záložně ruční kontrola session u Stripe při načtení výsledkové stránky. `on_paid` se spustí **právě jednou** (zámek řádku). |
| **Výsledková stránka** | `/platba/vysledek`: zaplaceno / čeká se na potvrzení (dotazuje se znovu) / zrušeno / selhalo / vypršelo. |
| **Tlačítko** | `<PayButton>`: popisek „Objednat a zaplatit“, odkazy na obchodní podmínky a ochranu údajů, volitelný souhlas se ztrátou práva na odstoupení u digitálního obsahu. |
| **Povinné stránky** | `/o-nas`, `/obchodni-podminky`, `/ochrana-osobnich-udaju`, `/cookies` – vícejazyčné (cs/en), odkazy v patičce, údaje poskytovatele z `public/legal.json`. |

Modul **neřeší** (záměrně, závisí na konkrétní aplikaci): co se platí a za kolik (to určuje zaregistrovaný „účel platby“), co se stane po zaplacení, vystavení daňového dokladu, vracení peněz (refundace se dělají v Stripe Dashboardu a modul je zatím nezaznamenává – viz „Omezení“).

---

## 2. Zapnutí a konfigurace

### Backend

- `backend/modules.json` (verzovaný v gitu): přidat `"stripe_payment_gate"` do `enabled`.
- `backend/.env`:

```
STRIPE_SECRET_KEY=sk_test_...        # sk_live_... v produkci
STRIPE_WEBHOOK_SECRET=whsec_...
FRONTEND_URL=https://moje-aplikace.cz   # z něj se skládají návratové URL z platby
```

Bez obou klíčů vrací endpointy modulu `503` (nikdy nefungují jen napůl). Tabulka `stripe_payments` se vytváří migrací vždy, bez ohledu na to, jestli je modul zapnutý.

### Stripe Dashboard

1. **Webhook** → endpoint `https://<APP_BASE_URL>/api/modules/stripe_payment_gate/webhook`, události:
   `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`. Podpisový klíč endpointu = `STRIPE_WEBHOOK_SECRET`.
2. **Nastavení → Veřejné údaje firmy** (Public business details): název, podpora (e-mail/telefon), URL obchodních podmínek a ochrany osobních údajů – Stripe je zobrazuje na platební stránce a v potvrzeních.
3. **Platební metody**: zapněte, co chcete nabízet. Pomalé metody (převod, SEPA debet) projdou stavem „čeká na potvrzení“ – modul to umí.
4. Lokální vývoj: `stripe listen --forward-to localhost:8000/api/modules/stripe_payment_gate/webhook` (vypíše dočasný `whsec_...`).

### Frontend

- `public/modules.json`: přidat `"stripe_payment_gate"` do `enabled`.
- `public/legal.json`: vyplnit údaje poskytovatele (viz kapitola 4). Dokud chybí název, IČO, sídlo nebo e-mail, zobrazují právní stránky žlutou výstrahu.

---

## 3. Napojení na aplikaci

### Backend – registrace účelu platby

Cenu **vždy** určuje backend. Prohlížeč posílá jen `purpose` + `payload` (např. id objednávky), nikdy částku.

```python
# např. v app/modules/<vas_modul>/__init__.py (spustí se při startu)
from app.modules.stripe_payment_gate.purposes import (
    PaymentPurpose, PaymentQuote, PaymentRejected, register_purpose,
)

async def resolve(db, user, payload):              # výchozí událost
    order = await db.get(Order, uuid.UUID(payload["order_id"]))
    if order is None or order.user_id != user.id:
        raise PaymentRejected("Order not found", status_code=404)
    if order.paid:
        raise PaymentRejected("Already paid", status_code=409)
    return PaymentQuote(
        amount=order.total_minor,     # v haléřích/centech: 19900 = 199,00 Kč
        currency="czk",
        description=f"Objednávka {order.number}",
        reference=str(order.id),
        return_path=f"/objednavky/{order.id}",
    )

async def on_paid(db, payment):                     # zpracování po zaplacení
    order = await db.get(Order, uuid.UUID(payment.reference))
    order.paid = True                               # commitne modul (stejná transakce)

register_purpose(PaymentPurpose(key="order", resolve=resolve, on_paid=on_paid))
```

- `require_user=False` povolí platbu i nepřihlášeným (např. dar).
- `required_consents=("terms", "digital_content_waiver")` předepíše souhlasy, bez kterých se platba vůbec nezačne (422 ještě před založením platby a před voláním Stripe) - tlačítko je sbírá, ale požadavek, který tlačítko obejde, nesmí obejít i souhlas, např. výslovnou žádost o okamžité plnění.
- `after_paid(db, payment)` se spustí jednou, **až po commitu** transakce, která platbu označila za zaplacenou - místo pro věci, které nesmějí proběhnout, když se transakce vrátí zpět, a nesmějí platbu shodit, když selžou (typicky potvrzovací e-mail). Výjimka se zaloguje a spolkne; co hook mění, musí sám commitnout. Co musí být atomické s platbou, patří do `on_paid`.
- E-mail platícího (z přihlášení) se ukládá do `payment.extra["customer_email"]`, aby ho `after_paid` měl po ruce, i když z platby zná jen její řádek.
- Výjimka v `on_paid` vrátí celou transakci zpět, webhook odpoví `500` a Stripe ho zopakuje – `on_paid` proto musí být idempotentní vůči vlastním vedlejším efektům mimo DB (e-maily posílejte až po úspěchu, nebo si hlídejte stav).
- Platbu lze zahájit i z Pythonu: `service.create_payment(db, settings, purpose_key=..., payload=..., user=...)`.

### Frontend

```tsx
import PayButton from '../stripe_payment_gate/PayButton'

<PayButton purpose="order" payload={{ order_id }} />
<PayButton purpose="ebook" payload={{ book_id }} digitalContent />   // digitální obsah ihned
```

Vlastní ovládací prvek: `startCheckout(purpose, payload, consents)` z `checkout.ts`. **Pak ale musíte u tlačítka sami zobrazit** odkaz na obchodní podmínky a ochranu údajů a posílat `consents: ['terms']` jen tehdy, když byly opravdu zobrazené.

Souhlasy (`terms`, `digital_content_waiver`) se ukládají k platbě do `stripe_payments.extra` (`consents`, `consented_at`) jako důkaz – důkazní břemeno o poučení spotřebitele nese poskytovatel.

---

## 4. Povinné stránky a `public/legal.json`

```json
{
  "provider": {
    "name": "Jan Novák",                        // nebo "Firma s.r.o."
    "ico": "12345678",
    "dic": "CZ12345678",                        // prázdné, pokud nemáte
    "vatPayer": false,                          // plátce DPH?
    "address": "Ulice 1, 110 00 Praha 1, Česká republika",
    "registration": {
      "cs": "fyzická osoba podnikající dle živnostenského zákona, zapsaná v živnostenském rejstříku",
      "en": "sole trader registered in the Czech Trade Register"
    },
    "email": "info@example.cz",
    "phone": "+420 123 456 789",
    "web": "https://example.cz"                 // prázdné = aktuální doména
  },
  "service": { "cs": "Popis toho, co prodáváte (celou větou).", "en": "..." },
  "dpoEmail": "",                               // pověřenec pro ochranu OÚ, jen pokud je jmenován
  "effectiveFrom": "2026-10-01",                // účinnost obchodních podmínek
  "gdpr": true,
  "extraStorage": [                             // další technické cookies/úložiště vaší aplikace
    { "name": "cart", "purpose": { "cs": "Obsah košíku", "en": "Cart contents" }, "duration": { "cs": "7 dní", "en": "7 days" } }
  ]
}
```

Textová pole mohou být řetězec (stejný pro všechny jazyky) nebo objekt `{ "cs": …, "en": … }`. Texty stránek jsou v `frontend/src/modules/stripe_payment_gate/legalLocales.ts` (cs + en). Nový jazyk přidáte doplněním klíče tam i do `SUPPORTED_LANGUAGES`.

| Stránka | Obsah | Proč |
|---|---|---|
| **O nás** `/o-nas` | název/jméno, IČO, DIČ, plátcovství DPH, sídlo, zápis v rejstříku, e-mail, telefon, popis nabídky, zákaznická podpora, platby, dozorové orgány | § 435 OZ (identifikace podnikatele na webu), § 1811 a § 1820 OZ (informace před uzavřením smlouvy), požadavek Stripe na kontakt zákaznické podpory |
| **Obchodní podmínky** `/obchodni-podminky` | uzavření smlouvy, cena a platba, dodání, odstoupení 14 dní + vzorový formulář, reklamace, ADR (ČOI), zahraniční zákazníci, účinnost | § 1811, § 1820, § 1826a, § 1829–1837 OZ, § 14 a § 19 zákona o ochraně spotřebitele, požadavek Stripe na refund/cancellation policy |
| **Ochrana osobních údajů** `/ochrana-osobnich-udaju` | správce, jaké údaje, účely, příjemci (Stripe, auth.withfbraun.com, hosting), doba uchování; s `gdpr: true` navíc právní základy, předávání mimo EU, práva a stížnost u ÚOOÚ | čl. 13 GDPR, požadavek Stripe na privacy policy |
| **Cookies** `/cookies` | jen technické úložiště (`access_token`, `refresh_token`, `i18nextLng`, `dark_mode` v localStorage) + Stripe na vlastní doméně | § 89 odst. 3 ZEK / čl. 5 odst. 3 směrnice ePrivacy – nezbytné cookies nevyžadují souhlas, ale je nutné o nich informovat |

**`gdpr: true` nechte zapnuté vždy, když platí zákazníci z EU** – GDPR se vztahuje na správce usazeného v EU i na správce mimo EU, který nabízí zboží či služby lidem v EU (čl. 3 GDPR). Vypnout ho dává smysl jen u provozovatele mimo EU, který EU zákazníkům nic nenabízí.

**Když aplikace přidá cokoli netechnického** (Google Analytics, Meta Pixel, reklamní nebo A/B nástroje, vložená videa YouTube, …), stránka Cookies přestává platit a **je nutná cookie lišta se souhlasem předem** – modul ji nemá.

---

## 5. Checklist povinností pro online platby

### Česko / EU (vždy)

- [ ] Vyplněný `public/legal.json` a zkontrolované texty stránek.
- [ ] **Tlačítko** jednoznačně říká, že objednávka zavazuje k platbě (§ 1826a OZ) – výchozí „Objednat a zaplatit“; nepřepisujte na „Pokračovat“ apod.
- [ ] **Cena**: konečná, včetně DPH (je-li plátce), měna zobrazená před zaplacením; u zboží náklady na dopravu.
- [ ] **Potvrzení smlouvy** e-mailem po zaplacení (§ 1824 OZ) – posílejte z `on_paid`, ideálně s obchodními podmínkami v příloze (PDF/text). Modul e-mail neposílá.
- [ ] **Daňový doklad / faktura** – Stripe český daňový doklad automaticky nevystaví; vystavte ho v účetním systému nebo zapněte Stripe Invoicing a ověřte náležitosti podle zákona o DPH.
- [ ] **Digitální obsah** doručovaný hned: použijte `<PayButton digitalContent />`. Bez výslovného souhlasu spotřebitel právo na odstoupení **neztrácí** (§ 1837 písm. l) OZ) a může do 14 dní žádat peníze zpět. Souhlas mu navíc potvrďte v e-mailu s potvrzením smlouvy (údaj je v `payment.extra["consents"]`).
- [ ] **Služby** zahájené ve lhůtě pro odstoupení: spotřebitel musí o zahájení výslovně požádat; při odstoupení platí poměrnou část (§ 1834 OZ).
- [ ] **Předplatné / opakované platby**: modul je neumí (jen jednorázové). Předplatné vyžaduje navíc informace o délce závazku, obnově a výpovědi a u automaticky prodlužovaných smluv se spotřebiteli platí zvláštní pravidla – řešit zvlášť, včetně kontroly právníkem.
- [ ] **Reklamace** vyřídit do 30 dnů a vydat potvrzení o uplatnění i vyřízení (§ 19 ZOS).
- [ ] **Recenze a slevy**, pokud je web zobrazuje: informace, zda a jak se ověřuje, že recenze pocházejí od skutečných zákazníků, a u slev uvedení nejnižší ceny za 30 dní před slevou (§ 12a ZOS).
- [ ] **Přístupnost**: od 28. 6. 2025 platí pro e-commerce zákon č. 424/2023 Sb. (European Accessibility Act); výjimka pro mikropodniky (< 10 zaměstnanců a obrat/bilance do 2 mil. EUR). Pokud se výjimka nevztahuje, je nutné prohlášení o přístupnosti.
- ℹ️ **Odkaz na evropskou platformu ODR už není potřeba** – platforma byla k 20. 7. 2025 zrušena (nařízení (EU) 2024/3228). Pokud ho máte ve starých podmínkách, odstraňte ho. ADR přes ČOI zůstává povinné uvádět.
- ℹ️ EET je od 1. 1. 2023 zrušená, pro platby kartou online se neřeší.

### Zákazníci z jiných států EU

- **DPH**: u digitálních a elektronicky poskytovaných služeb spotřebitelům (B2C) se po překročení limitu 10 000 EUR ročně (celkem za EU) účtuje **DPH státu zákazníka** – registrace do režimu **OSS** (One Stop Shop). Totéž pro zásilkový prodej zboží. Pro neplátce DPH: poskytnutí služby spotřebiteli z EU může znamenat povinnost registrace – ověřte s účetní. Ceny pak mohou být pro různé státy různé; `resolve()` dostává `user`, a může tedy cenu počítat podle země zákazníka (Stripe Tax to umí automaticky – modul ho zatím nezapíná).
- **Spotřebitelské právo**: volba českého práva spotřebitele nezbavuje ochrany podle práva jeho státu (čl. 6 nařízení Řím I) – v podmínkách je to uvedeno.
- **Jazyk**: podmínky musí být srozumitelné – pokud web cíleně nabízí v dalším jazyce, přeložte do něj i právní stránky (přidat jazyk do `legalLocales.ts`).
- **ADR pro zahraniční spotřebitele**: Evropské spotřebitelské centrum (ECC-Net) – uvedeno v podmínkách.
- Měnu volí `resolve()`; Stripe umí i více měn, zákazník vidí konečnou částku před platbou.

### Zákazníci mimo EU

- **Daně**: řada zemí zdaňuje digitální služby i od zahraničních prodejců – např. **Spojené království** (VAT, registrace od 1. prodeje B2C digitálních služeb), **Švýcarsko** (MWST od obratu 100 000 CHF celosvětově), **Norsko** (VOEC), **USA** (sales tax podle státu po překročení prahů „economic nexus“), Kanada, Austrálie (GST). Před aktivním prodejem do dané země ověřte s daňovým poradcem nebo zapněte Stripe Tax.
- **Clo a dovozní poplatky** u zboží nese podle podmínek zákazník – uvádějte to i u nabídky.
- **Sankce a exportní omezení**: neprodávejte do sankcionovaných zemí/osobám (sankční seznamy EU); Stripe některé země sám blokuje. Pokud zboží podléhá exportní kontrole (dual-use), musí to být v podmínkách.
- **Ochrana údajů**: pro zákazníky mimo EU dál platí GDPR (správce je v EU); některé státy mají vlastní pravidla (UK GDPR, kalifornské CCPA u větších firem) – u běžného malého e-shopu z ČR stačí stávající text.

### Požadavky Stripe na web (ověřuje při aktivaci účtu)

- [ ] jasný popis nabízeného zboží/služeb a cen s měnou,
- [ ] kontakt na zákaznickou podporu (e-mail, telefon, adresa) – stránka O nás,
- [ ] podmínky vrácení peněz, zrušení a reklamací – Obchodní podmínky čl. 6–7,
- [ ] ochrana osobních údajů – stránka Ochrana osobních údajů,
- [ ] u zboží dodací podmínky (doplňte do čl. 5 obchodních podmínek),
- [ ] případná právní/exportní omezení,
- [ ] web musí být veřejně dostupný a funkční v okamžiku aktivace (ne „under construction“).

---

## 6. Testování

- Backend: `backend/tests/test_modules_stripe_payment_gate_router.py` (vše mockováno přes respx, nikdy nevolá Stripe).
- Ruční test v testovacím režimu Stripe: karta `4242 4242 4242 4242`, libovolné budoucí datum a CVC; `4000 0027 6000 3184` vyvolá 3-D Secure; `4000 0000 0000 0002` zamítnutí.

## 7. Omezení a možná rozšíření

- Jedna položka na platbu (název = `description`); košík s více položkami vyžaduje rozšíření `create_checkout_session`.
- **Refundace** (`charge.refunded`) a **spory/chargebacky** (`charge.dispute.created`) modul nezaznamenává – stav platby zůstane `paid`. Pokud na tom aplikace závisí, přidejte zpracování těchto událostí do webhooku.
- Stripe Tax, předplatné (Subscriptions) a automatické faktury nejsou zapnuté.
- Stav `pending` po zrušení na straně Stripe přejde na `expired` až po vypršení session (standardně 24 h).
