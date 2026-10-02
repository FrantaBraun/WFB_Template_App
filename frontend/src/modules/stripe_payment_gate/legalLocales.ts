/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Texts of the legal pages (see LegalPages.tsx), merged into this module's
// i18n namespace under `legal`. {{placeholders}} are filled from
// public/legal.json via legalVars(). These are a TEMPLATE written for a
// Czech provider selling online to consumers in the EU and beyond - every
// deployment must review them against its actual business (goods vs.
// digital content vs. services, VAT status, delivery, ...) before going
// live. The module README lists what each page must contain and why.
//
// On the ThoughtAuction branch the Terms and Privacy texts are adapted to
// that application (its content rules, checks, strikes, anonymity of
// authors and the value formula). The numbers they quote come from
// public/legal.json's `params`, and a backend test
// (tests/test_modules_boards_legal.py) keeps them equal to what boards
// actually enforces - change either side and that test tells you.

const cs = {
  loading: 'Načítání…',
  notConfigured:
    'Údaje poskytovatele nejsou vyplněné. Doplňte je v souboru public/legal.json (název, IČO, sídlo, e-mail) – bez nich stránka nesplňuje zákonné požadavky.',
  effectiveFrom: 'Platné od {{effectiveFrom}}',
  vatPayer: 'Plátce DPH',
  notVatPayer: 'Neplátce DPH',
  nav: {
    about: 'O nás',
    terms: 'Pravidla a podmínky',
    privacy: 'Ochrana osobních údajů',
    cookies: 'Cookies',
  },
  about: {
    title: 'O nás',
    providerHeading: 'Provozovatel a poskytovatel služeb',
    fields: {
      name: 'Název / jméno',
      ico: 'IČO',
      dic: 'DIČ',
      vat: 'DPH',
      address: 'Sídlo / místo podnikání',
      registration: 'Zápis v rejstříku',
      email: 'E-mail',
      phone: 'Telefon',
    },
    sections: [
      { title: 'Co nabízíme', paragraphs: ['{{service}}'] },
      {
        title: 'Zákaznická podpora',
        paragraphs: [
          'S dotazy, reklamacemi nebo žádostí o odstoupení od smlouvy se na nás obracejte e-mailem na {{email}} nebo telefonicky na {{phone}}. Odpovídáme zpravidla do 2 pracovních dnů.',
        ],
      },
      {
        title: 'Platby',
        paragraphs: [
          'Platby probíhají bezhotovostně přes platební bránu Stripe (Stripe Payments Europe, Ltd., Irsko). Údaje o platební kartě zadáváte přímo na zabezpečené stránce Stripe – k nám se nikdy nedostanou. Platby jsou chráněny ověřením 3-D Secure.',
          'Ceny jsou uvedeny u každé nabídky a před zaplacením se zobrazí konečná částka včetně měny. Platit lze z České republiky, jiných států EU i ze zemí mimo EU.',
        ],
      },
      {
        title: 'Dozorové orgány',
        paragraphs: [
          'Dozor nad ochranou spotřebitele vykonává Česká obchodní inspekce (www.coi.gov.cz), dozor nad ochranou osobních údajů Úřad pro ochranu osobních údajů (www.uoou.gov.cz). Živnostenské podnikání dozoruje příslušný živnostenský úřad.',
        ],
      },
    ],
  },
  terms: {
    title: 'Pravidla a podmínky',
    sections: [
      {
        title: '1. Úvodní ustanovení',
        paragraphs: [
          'Tato pravidla a podmínky upravují používání webu {{web}} (dále jen „služba“) a vzájemná práva a povinnosti mezi poskytovatelem {{name}}, IČO {{ico}}, se sídlem {{address}}, {{registration}} (dále jen „poskytovatel“), a uživatelem služby, včetně uzavírání smluv na dálku o placených funkcích služby.',
          'Uživatelem může být spotřebitel i podnikatel. Ustanovení o právech spotřebitele se použijí pouze na uživatele, který je spotřebitelem. Kontaktní údaje poskytovatele: e-mail {{email}}, telefon {{phone}}; zprávu lze poslat také kontaktním formulářem na webu.',
          'Používáním služby, zejména zveřejněním příspěvku nebo kategorie, uživatel s těmito pravidly a podmínkami souhlasí.',
        ],
      },
      {
        title: '2. Co služba je a jak funguje',
        paragraphs: [
          '{{service}}',
          'Obsah služby si může přečíst kdokoli. Přidat příspěvek, založit kategorii a vyjádřit souznění může jen přihlášený uživatel s účtem u přihlašovací služby auth.withfbraun.com.',
          'Příspěvek tvoří nadpis (nejvýše {{postTitleMax}} znaků) a text (nejvýše {{postBodyMax}} znaků včetně mezer; emotikony jsou povoleny). Kategorii tvoří název (nejvýše {{categoryTitleMax}} znaků) a krátký popis (nejvýše {{categoryDescriptionMax}} znaků včetně mezer); adresa kategorie se vytvoří z jejího názvu.',
        ],
      },
      {
        title: '3. Anonymita a odpovědnost za obsah',
        paragraphs: [
          'Příspěvky i kategorie se zveřejňují bez uvedení autora.',
          'Poskytovatel však ke každému příspěvku a kategorii neveřejně uchovává, z jakého účtu vznikl. Autora nezveřejňuje; údaj používá jen k moderaci a k ochraně práv a vydá ho jen tehdy, když to vyžaduje právní předpis nebo rozhodnutí orgánu veřejné moci.',
          'Souznění s příspěvkem je neveřejné: u příspěvku se zobrazuje pouze jejich počet a nikdo, ani autor příspěvku, nevidí, kdo je vyjádřil.',
          'Za zveřejněný obsah odpovídá jeho autor. Autor prohlašuje, že je oprávněn obsah zveřejnit a že jím neporušuje práva třetích osob, a zveřejněním uděluje poskytovateli nevýhradní bezúplatné oprávnění obsah na službě zobrazovat po dobu jeho zveřejnění.',
        ],
      },
      {
        title: '4. Hodnota a pořadí příspěvků',
        paragraphs: [
          'Příspěvky v kategorii jsou řazeny podle hodnoty, od nejvyšší. Hodnota příspěvku je zaplacená částka (1 USD = {{pointsPerUsd}} bodů) plus počet souznění ({{pointsPerResonance}} bod za každé) minus stáří příspěvku ({{pointsPerDay}} bod za každý celý uplynulý den).',
          'Jeden uživatel může s jedním příspěvkem souznít nejvýše jednou. Autor může za svůj příspěvek platit opakovaně; platby se sčítají a každá z nich zvýší hodnotu příspěvku o zaplacenou částku.',
          'Hodnota se stářím průběžně snižuje, a pořadí se proto mění. Zaplacením není zaručena žádná konkrétní pozice ani doba zobrazení.',
        ],
      },
      {
        title: '5. Pravidla obsahu',
        paragraphs: ['Na službě je zakázáno zveřejňovat obsah (příspěvky i kategorie), který:'],
        items: [
          'obsahuje vulgární nebo urážlivé výrazy mířící na osoby,',
          'šíří nenávist nebo diskriminaci, například z důvodu rasy, národnosti, náboženství, pohlaví nebo sexuální orientace,',
          'obsahuje výhrůžky, vyzývá k násilí nebo k sebepoškozování,',
          'je spam, podvod nebo reklama, zejména odkazy na komerční nebo podvodné weby,',
          'obsahuje osobní údaje jiných osob, například e-mail nebo telefon,',
          'je sexuálního charakteru nevhodného pro veřejný web nebo je jakkoli nezákonný,',
          'záměrně šíří dezinformace, které mohou způsobit újmu,',
          'je psán křikem, stále dokola opakuje stejná slova nebo znaky nebo je nesrozumitelný.',
        ],
      },
      {
        title: 'Téma kategorie',
        paragraphs: ['Příspěvek musí také odpovídat tématu kategorie, ve které je zveřejněn, tedy jejímu názvu a popisu.'],
      },
      {
        title: '6. Kontrola obsahu',
        paragraphs: [
          'Každý příspěvek i každá kategorie se před zveřejněním automaticky zkontrolují. Kontrola v procentech vyhodnotí, jak pravděpodobně obsah porušuje pravidla, a u příspěvku také, nakolik neodpovídá tématu kategorie. Pro obě hodnoty platí:',
        ],
        items: [
          'nad {{warnPercent}} %: zobrazí se upozornění, že byste měli obsah upravit,',
          'nad {{riskPercent}} %: obsah je označen jako potenciálně závadný; zveřejnit ho lze jen po vašem výslovném potvrzení a při podrobnějším posouzení může být zablokován a smazán bez náhrady zaplacené částky,',
          'nad {{blockPercent}} %: obsah je závadný a jeho zveřejnění není povoleno.',
        ],
      },
      {
        title: 'Posouzení člověkem',
        paragraphs: [
          'Při upozornění i při odmítnutí se autorovi zobrazí důvod a konkrétní aspekty, kvůli kterým k němu došlo.',
          'Kromě automatické kontroly může kterýkoli zveřejněný příspěvek kdykoli ručně posoudit administrátor. Příspěvek, který porušuje pravidla, označí jako závadný a zablokuje; autorovi sdělí důvod oznámením v aplikaci.',
          'Automatická kontrola je jen pomůcka a může se mýlit. Pokud se domníváte, že byl váš obsah posouzen chybně, napište nám; posoudíme to a odpovíme.',
        ],
      },
      {
        title: '7. Důsledky porušení pravidel',
        paragraphs: [
          'Příspěvek označený jako závadný se odstraní a za již zaplacené částky se nevrací žádná náhrada. Tím nejsou dotčena zákonná práva spotřebitele.',
          'Jakmile počet příspěvků téhož uživatele, které administrátor označil jako závadné, dosáhne {{strikeLimit}} v období {{strikePeriodDays}} dnů, účet uživatele se zablokuje a všechny jeho zveřejněné příspěvky se odeberou, rovněž bez náhrady.',
          'Zablokovaný uživatel může službu dál číst, ale nemůže přidávat příspěvky a kategorie ani vyjadřovat souznění. Poskytovatel může blokaci zrušit; po jejím zrušení se dřívější závadné příspěvky do limitu už nepočítají.',
          'Proti označení příspěvku za závadný i proti zablokování účtu můžete podat námitku kontaktním formulářem nebo e-mailem na {{email}}. Poskytovatel ji nechá posoudit člověkem a odpoví.',
        ],
      },
      {
        title: '8. Uzavření smlouvy o placené službě',
        paragraphs: [
          'Zvýšení hodnoty příspěvku je placená služba. Nabídka na webu je výzvou k podání návrhu na uzavření smlouvy; uživatel podává návrh stisknutím tlačítka „Objednat a zaplatit“ a před jeho stisknutím může zadané údaje zkontrolovat a opravit.',
          'Smlouva je uzavřena okamžikem úspěšného provedení platby. Poskytovatel uživateli uzavření smlouvy potvrdí e-mailem. Smlouva se uzavírá v českém nebo anglickém jazyce, poskytovatel ji archivuje v elektronické podobě a uživateli je na vyžádání přístupná.',
          'Náklady na prostředky komunikace na dálku (internet, telefon) nese uživatel a neliší se od běžné sazby.',
        ],
      },
      {
        title: '9. Cena a platební podmínky',
        paragraphs: [
          'Cenou je částka, kterou uživatel zvolí, v celých amerických dolarech (USD) od {{minAmountUsd}} do {{maxAmountUsd}} USD za jednu platbu; zobrazí se mu před potvrzením platby včetně měny a je konečná. Poskytovatel je: {{vatStatement}}.',
          'Platí se bezhotovostně předem prostřednictvím platební brány Stripe (Stripe Payments Europe, Ltd., Irsko), a to platební kartou nebo jiným způsobem nabídnutým v platební bráně. Údaje o platební kartě zpracovává výhradně Stripe; poskytovatel k nim nemá přístup.',
          'Případné poplatky za převod měny účtuje banka uživatele. Poskytovatel zašle uživateli e-mailem potvrzení o uzavření smlouvy spolu s dokladem o přijaté platbě; je-li poskytovatel plátcem DPH, vystaví a zašle také daňový doklad. Doklady o platbách jsou uživateli kdykoli k dispozici i v aplikaci v části „Moje doklady“.',
        ],
      },
      {
        title: '10. Poskytnutí služby',
        paragraphs: [
          'Služba je poskytnuta bez zbytečného odkladu po připsání platby tím, že se zaplacená částka promítne do hodnoty příspěvku podle čl. 4. Uživatel při platbě výslovně žádá o okamžité poskytnutí služby.',
        ],
      },
      {
        title: '11. Odstoupení od smlouvy (spotřebitel)',
        paragraphs: [
          'Spotřebitel má právo odstoupit od smlouvy bez udání důvodu do 14 dnů ode dne uzavření smlouvy. Odstoupení lze zaslat na e-mail {{email}}, lze využít vzorový formulář níže. Lhůta je zachována, je-li oznámení odesláno před jejím uplynutím.',
          'Poskytovatel vrátí přijaté peníze do 14 dnů od odstoupení, a to stejným platebním prostředkem, jakým byla platba provedena. Pokud spotřebitel výslovně požádal o zahájení poskytování služby před uplynutím lhůty pro odstoupení, uhradí poměrnou část ceny za plnění poskytnuté do okamžiku odstoupení.',
          'Spotřebitel nemůže odstoupit od smlouvy o službě, která byla s jeho předchozím výslovným souhlasem před uplynutím lhůty pro odstoupení zcela poskytnuta a o jejímž důsledku byl poučen. Službu podle čl. 8 poskytujeme ihned po zaplacení, proto spotřebitel při platbě výslovně žádá o její okamžité poskytnutí a bere na vědomí, že po jejím úplném poskytnutí právo odstoupit od smlouvy ztrácí.',
        ],
      },
      {
        title: '12. Práva z vadného plnění a reklamace',
        paragraphs: [
          'Práva z vadného plnění se řídí občanským zákoníkem. Reklamaci lze uplatnit e-mailem na {{email}}; uživatel v ní popíše vadu a navrhne způsob vyřízení. Poskytovatel potvrdí přijetí reklamace a vyřídí ji bez zbytečného odkladu, nejpozději do 30 dnů, pokud se se spotřebitelem nedohodne na delší lhůtě. O vyřízení vydá písemné potvrzení.',
        ],
      },
      {
        title: '13. Mimosoudní řešení sporů',
        paragraphs: [
          'K mimosoudnímu řešení spotřebitelských sporů je příslušná Česká obchodní inspekce, Ústřední inspektorát – oddělení ADR, Gorazdova 1969/24, 120 00 Praha 2, www.adr.coi.cz. Spotřebitelé z jiných států EU se mohou obrátit také na Evropské spotřebitelské centrum ve svém státě (síť ECC-Net).',
          'Stížnosti lze podat poskytovateli na e-mail {{email}} nebo dozorovému orgánu, kterým je Česká obchodní inspekce.',
        ],
      },
      {
        title: '14. Uživatelé z jiných států',
        paragraphs: [
          'Služba je určena uživatelům z České republiky, jiných členských států EU i ze zemí mimo EU. Smlouva se řídí českým právem. Je-li uživatel spotřebitelem s obvyklým bydlištěm v jiném státě, nezbavuje ho tato volba ochrany, kterou mu poskytují kogentní ustanovení práva státu jeho bydliště.',
          'U uživatelů z jiných států může být cena zatížena daní z přidané hodnoty podle státu uživatele; konečná cena se vždy zobrazí před zaplacením.',
        ],
      },
      {
        title: '15. Ochrana osobních údajů',
        paragraphs: [
          'Zpracování osobních údajů se řídí dokumentem Ochrana osobních údajů zveřejněným na tomto webu.',
        ],
      },
      {
        title: '16. Závěrečná ustanovení',
        paragraphs: [
          'Poskytovatel může tato pravidla a podmínky měnit; o změně informuje na webu. Na smlouvu o placené službě se použije znění účinné v okamžiku jejího uzavření. Tato pravidla a podmínky jsou účinné od {{effectiveFrom}}.',
        ],
      },
      {
        title: 'Příloha: vzorový formulář pro odstoupení od smlouvy',
        paragraphs: ['(vyplňte a zašlete jej, pouze pokud chcete odstoupit od smlouvy)'],
        items: [
          'Adresát: {{name}}, {{address}}, e-mail {{email}}',
          'Oznamuji, že tímto odstupuji od smlouvy o poskytnutí služby (zvýšení hodnoty příspěvku):',
          'Datum uzavření smlouvy (zaplacení):',
          'Jméno a příjmení spotřebitele:',
          'Adresa spotřebitele:',
          'Číslo platby:',
          'Podpis (pouze pokud je formulář zasílán v listinné podobě) a datum:',
        ],
      },
    ],
  },
  privacy: {
    title: 'Ochrana osobních údajů',
    dpo: 'Pověřence pro ochranu osobních údajů kontaktujte na {{email}}.',
    sections: [
      {
        title: 'Správce osobních údajů',
        paragraphs: [
          'Správcem osobních údajů je {{name}}, IČO {{ico}}, se sídlem {{address}}. Ve věcech ochrany osobních údajů nás kontaktujte na {{email}} nebo {{phone}}.',
        ],
      },
      {
        title: 'Jaké údaje zpracováváme',
        items: [
          'Údaje o účtu: e-mail, jméno a další údaje profilu, které spravuje centrální přihlašovací služba auth.withfbraun.com.',
          'Obsah, který zveřejníte: příspěvky a kategorie (nadpis, text, popis). Zobrazují se veřejně a bez uvedení autora.',
          'Vazba obsahu na váš účet: u každého příspěvku a kategorie neveřejně uchováváme, z jakého účtu a kdy vznikl.',
          'Souznění: záznam, že váš účet vyjádřil souznění s příspěvkem. Je neveřejný; zobrazuje se jen počet a nikdo, ani autor příspěvku, nevidí, kdo souznil.',
          'Údaje z moderace: výsledek automatické kontroly obsahu (procenta a nalezené důvody), rozhodnutí administrátora o zablokování příspěvku včetně důvodu, oznámení, která jsme vám v aplikaci poslali, a stav účtu (zablokován, od kdy a proč).',
          'Údaje o platbách: předmět, částka, měna, stav a identifikátory platby, vystavený doklad (číslo, datum a údaje na něm uvedené) a e-mail, na který byl odeslán. Údaje o platební kartě zpracovává výhradně Stripe – my je nevidíme ani neukládáme.',
          'Komunikace: obsah zpráv z kontaktního formuláře a e-mailů, které nám zašlete (např. námitky, dotazy).',
          'Technické údaje: IP adresa, čas a typ požadavku v provozních záznamech serveru.',
        ],
      },
      {
        title: 'Proč údaje zpracováváme',
        items: [
          'provoz služby: zobrazení zveřejněného obsahu a řazení příspěvků podle hodnoty,',
          'uzavření a plnění smlouvy o placené službě, včetně přijetí platby a zákaznické podpory,',
          'moderace obsahu a prosazování pravidel: ochrana práv a bezpečí uživatelů i třetích osob a předcházení opakovanému porušování pravidel,',
          'plnění zákonných povinností, zejména účetních a daňových,',
          'zabezpečení služby, předcházení podvodům a ochrana našich právních nároků.',
        ],
      },
      {
        title: 'Komu údaje předáváme',
        items: [
          'Veřejnosti: obsah, který zveřejníte, vidí kdokoli, bez uvedení autora. Vaši totožnost nezveřejňujeme.',
          'Stripe Payments Europe, Ltd. (Irsko) – zpracování plateb a ochrana proti podvodům; pro vlastní zákonné povinnosti vystupuje jako samostatný správce (stripe.com/privacy).',
          'Provozovatel přihlašovací služby auth.withfbraun.com – správa uživatelských účtů.',
          'Poskytovatelé hostingu, e-mailu a účetních služeb, kteří údaje zpracovávají pouze podle našich pokynů.',
          'Orgány veřejné moci, pokud to vyžaduje zákon.',
        ],
      },
      {
        title: 'Jak dlouho údaje uchováváme',
        paragraphs: [
          'Údaje o účtu po dobu trvání účtu. Zveřejněný obsah po dobu jeho zveřejnění. Vazbu obsahu na účet a údaje z moderace po dobu trvání účtu a poté po dobu promlčecí lhůty případných nároků; zablokované a odebrané příspěvky uchováváme neveřejně po dobu nutnou k posouzení opakovaných porušení pravidel a k ochraně našich právních nároků. Souznění po dobu existence příspěvku. Údaje o platbách a daňové doklady po dobu stanovenou účetními a daňovými předpisy (zpravidla 10 let). Komunikaci po dobu nutnou k vyřízení věci a promlčecí lhůty případných nároků. Provozní záznamy nejvýše několik týdnů.',
        ],
      },
    ],
    gdprSections: [
      {
        title: 'Právní základy zpracování (GDPR)',
        items: [
          'plnění smlouvy – čl. 6 odst. 1 písm. b) GDPR (provoz služby a placené funkce),',
          'plnění právní povinnosti – čl. 6 odst. 1 písm. c) GDPR,',
          'oprávněný zájem na moderaci obsahu, zabezpečení služby, předcházení podvodům a ochraně nároků – čl. 6 odst. 1 písm. f) GDPR.',
        ],
        paragraphs: [
          'Poskytnutí údajů potřebných k vytvoření účtu a ke zveřejnění obsahu je smluvním požadavkem – bez nich službu nelze používat.',
        ],
      },
      {
        title: 'Automatizované kontroly a rozhodování',
        paragraphs: [
          'Obsah se před zveřejněním kontroluje automaticky (porovnání s pravidly a s tématem kategorie) a Stripe může platby automaticky prověřovat kvůli ochraně proti podvodům. O zablokování příspěvku vždy rozhoduje administrátor, tedy člověk.',
          'Zablokování účtu nastane automaticky, jakmile počet příspěvků, které administrátor označil jako závadné, dosáhne limitu uvedeného v pravidlech ({{strikeLimit}} v období {{strikePeriodDays}} dnů). Protože má na vás významný dopad, máte právo požádat o přezkoumání člověkem, vyjádřit své stanovisko a rozhodnutí napadnout (čl. 22 GDPR) – použijte kontaktní formulář nebo e-mail {{email}}.',
        ],
      },
      {
        title: 'Předávání mimo EU/EHP',
        paragraphs: [
          'Stripe a někteří další zpracovatelé mohou údaje předávat do USA. Předání probíhá na základě rámce EU–USA pro ochranu osobních údajů (Data Privacy Framework) nebo standardních smluvních doložek schválených Evropskou komisí.',
        ],
      },
      {
        title: 'Vaše práva',
        items: [
          'právo na přístup ke svým údajům a na jejich opravu,',
          'právo na výmaz, na omezení zpracování a na přenositelnost údajů,',
          'právo vznést námitku proti zpracování na základě oprávněného zájmu,',
          'právo na přezkoumání člověkem u automatizovaných rozhodnutí s významným dopadem,',
          'právo podat stížnost u Úřadu pro ochranu osobních údajů, Pplk. Sochora 27, 170 00 Praha 7, www.uoou.gov.cz, nebo u dozorového úřadu ve státě EU, kde máte bydliště či pracujete.',
        ],
        paragraphs: ['Svá práva uplatníte e-mailem na {{email}} nebo kontaktním formulářem. Odpovíme nejpozději do jednoho měsíce.'],
      },
    ],
  },
  cookies: {
    title: 'Informace o cookies',
    tableHeading: 'Co ukládáme ve vašem prohlížeči',
    columns: { name: 'Název', purpose: 'Účel', duration: 'Doba uložení' },
    sections: [
      {
        title: 'Používáme pouze technické cookies',
        paragraphs: [
          'Tento web používá výhradně technické (nezbytné) cookies a obdobné technologie – konkrétně místní úložiště prohlížeče (localStorage). Slouží jen k tomu, aby web fungoval: udržují vaše přihlášení a pamatují si zvolený jazyk a vzhled.',
          'Nepoužíváme analytické, marketingové ani reklamní cookies a nesledujeme vás napříč weby. Technické cookies nevyžadují váš souhlas (§ 89 odst. 3 zákona č. 127/2005 Sb., o elektronických komunikacích, a čl. 5 odst. 3 směrnice 2002/58/ES), proto se nezobrazuje lišta se souhlasem.',
        ],
      },
    ],
    storage: [
      { name: 'access_token', purpose: 'Přihlášení – krátkodobý přístupový token', duration: 'Do odhlášení (token platí cca 15 minut)' },
      { name: 'refresh_token', purpose: 'Přihlášení – obnovení přístupového tokenu bez nového přihlašování', duration: 'Do odhlášení' },
      { name: 'i18nextLng', purpose: 'Zapamatování zvoleného jazyka', duration: 'Do smazání v prohlížeči' },
      { name: 'dark_mode', purpose: 'Zapamatování světlého / tmavého vzhledu', duration: 'Do smazání v prohlížeči' },
    ],
    closingSections: [
      {
        title: 'Platební brána Stripe',
        paragraphs: [
          'Platbu dokončujete na zabezpečené stránce Stripe (checkout.stripe.com), která je provozována mimo tento web. Stripe tam používá vlastní cookies nezbytné pro provedení platby a ochranu proti podvodům; řídí se zásadami Stripe (stripe.com/cookies-policy/legal).',
        ],
      },
      {
        title: 'Jak údaje smazat',
        paragraphs: [
          'Uložené údaje můžete kdykoli smazat v nastavení prohlížeče (vymazání dat webu). Odhlášením se přihlašovací tokeny smažou automaticky. Bez technických cookies nemusí web správně fungovat, např. nepůjde zůstat přihlášen.',
        ],
      },
    ],
  },
}

const en: typeof cs = {
  loading: 'Loading…',
  notConfigured:
    'Provider details are not filled in. Add them to public/legal.json (name, company ID, registered address, email) - without them this page does not meet legal requirements.',
  effectiveFrom: 'Effective from {{effectiveFrom}}',
  vatPayer: 'VAT registered',
  notVatPayer: 'Not VAT registered',
  nav: {
    about: 'About us',
    terms: 'Terms and conditions',
    privacy: 'Privacy policy',
    cookies: 'Cookies',
  },
  about: {
    title: 'About us',
    providerHeading: 'Operator and service provider',
    fields: {
      name: 'Name',
      ico: 'Company ID (IČO)',
      dic: 'VAT ID (DIČ)',
      vat: 'VAT',
      address: 'Registered address',
      registration: 'Registration',
      email: 'Email',
      phone: 'Phone',
    },
    sections: [
      { title: 'What we offer', paragraphs: ['{{service}}'] },
      {
        title: 'Customer support',
        paragraphs: [
          'For questions, complaints or to withdraw from a contract, contact us by email at {{email}} or by phone at {{phone}}. We usually reply within 2 business days.',
        ],
      },
      {
        title: 'Payments',
        paragraphs: [
          'Payments are cashless, through the Stripe payment gateway (Stripe Payments Europe, Ltd., Ireland). You enter your card details directly on Stripe’s secure page - they never reach us. Payments are protected by 3-D Secure authentication.',
          'Prices are shown with every offer, and the final amount including currency is displayed before you pay. Payments are accepted from the Czech Republic, other EU countries and countries outside the EU.',
        ],
      },
      {
        title: 'Supervisory authorities',
        paragraphs: [
          'Consumer protection is supervised by the Czech Trade Inspection Authority (www.coi.gov.cz), personal data protection by the Office for Personal Data Protection (www.uoou.gov.cz). Trade licensing is supervised by the competent Trade Licensing Office.',
        ],
      },
    ],
  },
  terms: {
    title: 'Terms and conditions',
    sections: [
      {
        title: '1. Introductory provisions',
        paragraphs: [
          'These terms and rules govern the use of the website {{web}} (the “service”) and the rights and obligations between the provider {{name}}, Company ID {{ico}}, registered at {{address}}, {{registration}} (the “provider”), and the user of the service, including distance contracts for the service’s paid features.',
          'The user may be a consumer or a business. Provisions on consumer rights apply only to users who are consumers. Provider contact: email {{email}}, phone {{phone}}; you can also send a message through the contact form on the website.',
          'By using the service, in particular by publishing a post or a category, the user agrees to these terms and rules.',
        ],
      },
      {
        title: '2. What the service is and how it works',
        paragraphs: [
          '{{service}}',
          'Anyone can read the content of the service. Only a signed-in user with an account at the sign-in service auth.withfbraun.com can add a post, create a category or resonate.',
          'A post consists of a title (at most {{postTitleMax}} characters) and a text (at most {{postBodyMax}} characters including spaces; emoji are allowed). A category consists of a name (at most {{categoryTitleMax}} characters) and a short description (at most {{categoryDescriptionMax}} characters including spaces); the category’s address is generated from its name.',
        ],
      },
      {
        title: '3. Anonymity and responsibility for content',
        paragraphs: [
          'Posts and categories are published without showing their author.',
          'The provider does, however, keep non-publicly which account each post and category came from. It does not publish the author; the information is used only for moderation and to protect rights, and is disclosed only where a legal provision or a decision of a public authority requires it.',
          'Resonance with a post is not public: a post shows only how many there are, and nobody, not even the post’s author, can see who expressed them.',
          'The author is responsible for the content they publish. The author declares that they are entitled to publish it and that it does not infringe the rights of third parties, and by publishing grants the provider a non-exclusive, royalty-free permission to display the content on the service for as long as it is published.',
        ],
      },
      {
        title: '4. Value and order of posts',
        paragraphs: [
          'Posts in a category are ordered by value, highest first. A post’s value is the amount paid (1 USD = {{pointsPerUsd}} points) plus the number of resonances ({{pointsPerResonance}} point each) minus the post’s age ({{pointsPerDay}} point for every full day that has passed).',
          'One user can resonate with a given post at most once. The author can pay for their post repeatedly; payments add up, and each one raises the post’s value by the amount paid.',
          'Value decreases with age, so the order keeps changing. Paying does not guarantee any particular position or length of display.',
        ],
      },
      {
        title: '5. Content rules',
        paragraphs: ['It is forbidden to publish content (posts and categories) on the service that:'],
        items: [
          'contains vulgar or abusive language aimed at people,',
          'spreads hatred or discrimination, for example on grounds of race, nationality, religion, sex or sexual orientation,',
          'contains threats, or incites violence or self-harm,',
          'is spam, a scam or advertising, in particular links to commercial or fraudulent websites,',
          'contains personal data of other people, such as an email address or phone number,',
          'is of a sexual nature unsuitable for a public website, or is illegal in any way,',
          'deliberately spreads misinformation that may cause harm,',
          'is written in shouting, repeats the same words or characters over and over, or is unintelligible.',
        ],
      },
      {
        title: 'Category topic',
        paragraphs: ['A post must also fit the topic of the category it is published in, that is, its name and description.'],
      },
      {
        title: '6. Content checks',
        paragraphs: [
          'Every post and every category is checked automatically before it is published. The check rates, as a percentage, how likely the content is to break the rules and, for a post, how far it does not fit the category’s topic. For both values:',
        ],
        items: [
          'above {{warnPercent}} %: you are shown a notice that you should edit the content,',
          'above {{riskPercent}} %: the content is marked as potentially violating; it can be published only with your explicit confirmation, and on closer review it may be blocked and deleted without a refund of the amount paid,',
          'above {{blockPercent}} %: the content is violating and may not be published.',
        ],
      },
      {
        title: 'Review by a person',
        paragraphs: [
          'Whether you get a notice or a refusal, the author is shown the reason and the specific aspects behind it.',
          'In addition to the automatic check, an administrator can manually review any published post at any time. A post that breaks the rules is marked as violating and blocked; the administrator tells the author the reason in an in-app notification.',
          'The automatic check is only an aid and can be wrong. If you believe your content was assessed wrongly, write to us; we will look into it and reply.',
        ],
      },
      {
        title: '7. Consequences of breaking the rules',
        paragraphs: [
          'A post marked as violating is removed, and no compensation is paid for amounts already paid. This does not affect a consumer’s statutory rights.',
          'Once the number of a user’s posts that an administrator has marked as violating reaches {{strikeLimit}} within {{strikePeriodDays}} days, the user’s account is blocked and all of their published posts are removed, likewise without compensation.',
          'A blocked user can still read the service but cannot add posts or categories or resonate. The provider may lift the block; once it is lifted, earlier violating posts no longer count towards the limit.',
          'You can object both to a post being marked as violating and to your account being blocked, using the contact form or by email to {{email}}. The provider has a person assess the objection and replies.',
        ],
      },
      {
        title: '8. Conclusion of a contract for a paid service',
        paragraphs: [
          'Raising a post’s value is a paid service. The offer on the website is an invitation to submit an order; the user submits an order by pressing the “Order and pay” button, and before doing so can review and correct the data entered.',
          'The contract is concluded once the payment has been successfully completed. The provider confirms the contract to the user by email. Contracts are concluded in Czech or English; the provider archives them electronically and makes them available to the user on request.',
          'The costs of distance communication (internet, phone) are borne by the user and do not differ from the standard rate.',
        ],
      },
      {
        title: '9. Price and payment terms',
        paragraphs: [
          'The price is the amount the user chooses, in whole US dollars (USD), from {{minAmountUsd}} to {{maxAmountUsd}} USD per payment; it is shown, with its currency, before the payment is confirmed and is final. The provider is: {{vatStatement}}.',
          'Payment is made in advance, cashless, through the Stripe payment gateway (Stripe Payments Europe, Ltd., Ireland), by payment card or another method offered by the gateway. Card details are processed exclusively by Stripe; the provider has no access to them.',
          'Any currency conversion fees are charged by the user’s bank. The provider emails the user a confirmation of the contract together with a document for the payment received; if the provider is a VAT payer, it also issues and sends a tax document. The documents for payments are also available to the user in the app at any time under “My receipts”.',
        ],
      },
      {
        title: '10. Provision of the service',
        paragraphs: [
          'The service is provided without undue delay after the payment has been received, by the amount paid being added to the post’s value under Article 4. By paying, the user expressly requests that the service be provided immediately.',
        ],
      },
      {
        title: '11. Right of withdrawal (consumers)',
        paragraphs: [
          'A consumer may withdraw from the contract without giving any reason within 14 days of concluding it. The withdrawal can be sent to {{email}}; the model form below may be used. The deadline is met if the notice is sent before it expires.',
          'The provider refunds the payment within 14 days of the withdrawal, using the same payment method as the original payment. If the consumer expressly requested that the service start before the withdrawal period ends, they pay a proportionate part of the price for what was provided up to the withdrawal.',
          'A consumer cannot withdraw from a service contract once the service has been fully performed with their prior express consent before the withdrawal period ended and they were informed of the consequence. We provide the service under Article 8 immediately after payment, so by paying the consumer expressly requests that it be provided immediately and acknowledges that once it has been fully provided they lose the right of withdrawal.',
        ],
      },
      {
        title: '12. Defective performance and complaints',
        paragraphs: [
          'Rights arising from defective performance are governed by the Czech Civil Code. Complaints can be made by email to {{email}}, describing the defect and the proposed remedy. The provider confirms receipt and settles the complaint without undue delay, within 30 days at the latest unless a longer period is agreed with the consumer, and issues a written confirmation of how it was settled.',
        ],
      },
      {
        title: '13. Out-of-court dispute resolution',
        paragraphs: [
          'Out-of-court resolution of consumer disputes is handled by the Czech Trade Inspection Authority, Central Inspectorate - ADR Department, Gorazdova 1969/24, 120 00 Prague 2, www.adr.coi.cz. Consumers from other EU countries may also contact the European Consumer Centre in their country (ECC-Net).',
          'Complaints can be sent to the provider at {{email}} or to the supervisory authority, the Czech Trade Inspection Authority.',
        ],
      },
      {
        title: '14. Users outside the Czech Republic',
        paragraphs: [
          'The service is intended for users from the Czech Republic, other EU member states and countries outside the EU. The contract is governed by Czech law. Where the user is a consumer habitually resident in another country, this choice of law does not deprive them of the protection afforded by the mandatory provisions of the law of their country of residence.',
          'For users from other countries, the price may include value added tax of the user’s country; the final price is always shown before payment.',
        ],
      },
      {
        title: '15. Personal data protection',
        paragraphs: ['Personal data processing is governed by the Privacy policy published on this website.'],
      },
      {
        title: '16. Final provisions',
        paragraphs: [
          'The provider may amend these terms and rules and will announce changes on the website. The version in effect when a contract for a paid service was concluded applies to it. These terms and rules are effective from {{effectiveFrom}}.',
        ],
      },
      {
        title: 'Annex: model withdrawal form',
        paragraphs: ['(complete and return this form only if you wish to withdraw from the contract)'],
        items: [
          'To: {{name}}, {{address}}, email {{email}}',
          'I hereby give notice that I withdraw from my contract for the provision of the service (raising a post’s value):',
          'Date of the contract (of payment):',
          'Name of consumer:',
          'Address of consumer:',
          'Payment number:',
          'Signature (only if this form is sent on paper) and date:',
        ],
      },
    ],
  },
  privacy: {
    title: 'Privacy policy',
    dpo: 'You can contact our data protection officer at {{email}}.',
    sections: [
      {
        title: 'Data controller',
        paragraphs: [
          'The controller of your personal data is {{name}}, Company ID {{ico}}, registered at {{address}}. For any data protection matter, contact us at {{email}} or {{phone}}.',
        ],
      },
      {
        title: 'What data we process',
        items: [
          'Account data: email, name and other profile data, managed by the central sign-in service auth.withfbraun.com.',
          'Content you publish: posts and categories (title, text, description). It is shown publicly, without showing the author.',
          'The link between content and your account: for every post and category we keep, non-publicly, which account it came from and when.',
          'Resonance: a record that your account resonated with a post. It is not public; only the count is shown, and nobody, not even the post’s author, can see who resonated.',
          'Moderation data: the result of the automatic content check (percentages and the reasons found), an administrator’s decision to block a post including the reason, the notifications we sent you in the app, and your account’s status (blocked, since when and why).',
          'Payment data: subject, amount, currency, status and identifiers of the payment, the document issued (its number, date and the details stated on it) and the email address it was sent to. Card details are processed exclusively by Stripe - we never see or store them.',
          'Communication: the content of contact-form messages and emails you send us (e.g. objections, questions).',
          'Technical data: IP address, time and type of request in the server’s operational logs.',
        ],
      },
      {
        title: 'Why we process it',
        items: [
          'to run the service: showing published content and ordering posts by value,',
          'to conclude and perform the contract for a paid service, including accepting payment and customer support,',
          'to moderate content and enforce the rules: protecting the rights and safety of users and third parties and preventing repeated rule violations,',
          'to comply with legal obligations, in particular accounting and tax obligations,',
          'to keep the service secure, prevent fraud and protect our legal claims.',
        ],
      },
      {
        title: 'Who we share it with',
        items: [
          'The public: content you publish can be seen by anyone, without showing the author. We do not publish your identity.',
          'Stripe Payments Europe, Ltd. (Ireland) - payment processing and fraud prevention; an independent controller for its own legal obligations (stripe.com/privacy).',
          'The operator of the sign-in service auth.withfbraun.com - user account management.',
          'Hosting, email and accounting service providers, processing data only on our instructions.',
          'Public authorities, where required by law.',
        ],
      },
      {
        title: 'How long we keep it',
        paragraphs: [
          'Account data for as long as the account exists. Published content for as long as it is published. The link between content and an account, and moderation data, for as long as the account exists and then for the limitation period of any claims; blocked and removed posts we keep non-publicly for as long as needed to assess repeated rule violations and to protect our legal claims. Resonance for as long as the post exists. Payment data and tax documents for the period required by accounting and tax law (usually 10 years). Communication for as long as needed to handle the matter and for the limitation period of any claims. Operational logs for a few weeks at most.',
        ],
      },
    ],
    gdprSections: [
      {
        title: 'Legal bases (GDPR)',
        items: [
          'performance of a contract - Art. 6(1)(b) GDPR (running the service and its paid features),',
          'compliance with a legal obligation - Art. 6(1)(c) GDPR,',
          'legitimate interest in moderating content, keeping the service secure, preventing fraud and protecting claims - Art. 6(1)(f) GDPR.',
        ],
        paragraphs: [
          'Providing the data needed to create an account and publish content is a contractual requirement - the service cannot be used without it.',
        ],
      },
      {
        title: 'Automated checks and decisions',
        paragraphs: [
          'Content is checked automatically before it is published (comparison with the rules and with the category’s topic), and Stripe may screen payments automatically to prevent fraud. Blocking a post is always decided by an administrator, that is, a person.',
          'An account is blocked automatically once the number of posts an administrator has marked as violating reaches the limit set in the rules ({{strikeLimit}} within {{strikePeriodDays}} days). Because this has a significant effect on you, you have the right to ask for review by a person, to express your point of view and to contest the decision (Art. 22 GDPR) - use the contact form or email {{email}}.',
        ],
      },
      {
        title: 'Transfers outside the EU/EEA',
        paragraphs: [
          'Stripe and some other processors may transfer data to the USA. Such transfers rely on the EU-U.S. Data Privacy Framework or on standard contractual clauses approved by the European Commission.',
        ],
      },
      {
        title: 'Your rights',
        items: [
          'the right to access and rectify your data,',
          'the right to erasure, to restriction of processing and to data portability,',
          'the right to object to processing based on legitimate interest,',
          'the right to review by a person of automated decisions with a significant effect,',
          'the right to lodge a complaint with the Czech Office for Personal Data Protection, Pplk. Sochora 27, 170 00 Prague 7, www.uoou.gov.cz, or with the supervisory authority of the EU country where you live or work.',
        ],
        paragraphs: ['To exercise your rights, email us at {{email}} or use the contact form. We reply within one month at the latest.'],
      },
    ],
  },
  cookies: {
    title: 'Cookie information',
    tableHeading: 'What we store in your browser',
    columns: { name: 'Name', purpose: 'Purpose', duration: 'Retention' },
    sections: [
      {
        title: 'We only use technical cookies',
        paragraphs: [
          'This website uses only technical (strictly necessary) cookies and similar technologies - specifically the browser’s local storage (localStorage). They exist only to make the website work: they keep you signed in and remember your chosen language and appearance.',
          'We do not use analytics, marketing or advertising cookies, and we do not track you across websites. Strictly necessary cookies do not require your consent (Art. 5(3) of Directive 2002/58/EC and Section 89(3) of Czech Act No. 127/2005 Coll., on Electronic Communications), which is why no consent banner is shown.',
        ],
      },
    ],
    storage: [
      { name: 'access_token', purpose: 'Sign-in - short-lived access token', duration: 'Until sign-out (the token is valid for about 15 minutes)' },
      { name: 'refresh_token', purpose: 'Sign-in - renews the access token without signing in again', duration: 'Until sign-out' },
      { name: 'i18nextLng', purpose: 'Remembers your chosen language', duration: 'Until deleted in the browser' },
      { name: 'dark_mode', purpose: 'Remembers light / dark appearance', duration: 'Until deleted in the browser' },
    ],
    closingSections: [
      {
        title: 'Stripe payment gateway',
        paragraphs: [
          'You complete payments on Stripe’s secure page (checkout.stripe.com), which is operated outside this website. There, Stripe uses its own cookies needed to process the payment and prevent fraud, governed by Stripe’s policies (stripe.com/cookies-policy/legal).',
        ],
      },
      {
        title: 'How to delete this data',
        paragraphs: [
          'You can delete stored data at any time in your browser settings (clear site data). Signing out deletes the sign-in tokens automatically. Without technical cookies the website may not work properly - for example, you will not stay signed in.',
        ],
      },
    ],
  },
}

export const legalLocales = { cs, en }
