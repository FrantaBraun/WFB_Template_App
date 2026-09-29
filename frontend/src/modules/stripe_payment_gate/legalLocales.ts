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

const cs = {
  loading: 'Načítání…',
  notConfigured:
    'Údaje poskytovatele nejsou vyplněné. Doplňte je v souboru public/legal.json (název, IČO, sídlo, e-mail) – bez nich stránka nesplňuje zákonné požadavky.',
  effectiveFrom: 'Platné od {{effectiveFrom}}',
  vatPayer: 'Plátce DPH',
  notVatPayer: 'Neplátce DPH',
  nav: {
    about: 'O nás',
    terms: 'Obchodní podmínky',
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
    title: 'Obchodní podmínky',
    sections: [
      {
        title: '1. Úvodní ustanovení',
        paragraphs: [
          'Tyto obchodní podmínky upravují vzájemná práva a povinnosti mezi poskytovatelem {{name}}, IČO {{ico}}, se sídlem {{address}}, {{registration}} (dále jen „poskytovatel“), a zákazníkem při uzavírání smluv na dálku prostřednictvím webu {{web}}.',
          'Zákazníkem může být spotřebitel i podnikatel. Ustanovení o právech spotřebitele se použijí pouze na zákazníka, který je spotřebitelem. Kontaktní údaje poskytovatele: e-mail {{email}}, telefon {{phone}}.',
        ],
      },
      {
        title: '2. Předmět smlouvy',
        paragraphs: [
          '{{service}}',
          'Podrobný popis, rozsah a cena plnění jsou uvedeny u konkrétní nabídky na webu.',
        ],
      },
      {
        title: '3. Uzavření smlouvy',
        paragraphs: [
          'Prezentace nabídky na webu je výzvou k podání návrhu na uzavření smlouvy. Zákazník podává návrh stisknutím tlačítka „Objednat a zaplatit“; před jeho stisknutím může zadané údaje zkontrolovat a opravit.',
          'Smlouva je uzavřena okamžikem úspěšného provedení platby. Poskytovatel zákazníkovi uzavření smlouvy potvrdí na e-mail. Smlouva se uzavírá v českém nebo anglickém jazyce, poskytovatel ji archivuje v elektronické podobě a zákazníkovi je na vyžádání přístupná.',
          'Náklady na prostředky komunikace na dálku (internet, telefon) nese zákazník a neliší se od běžné sazby.',
        ],
      },
      {
        title: '4. Cena a platební podmínky',
        paragraphs: [
          'Ceny jsou uvedeny u jednotlivých nabídek a jsou konečné. Poskytovatel je: {{vatStatement}}. Konečná cena včetně měny se zákazníkovi zobrazí před potvrzením platby.',
          'Platí se bezhotovostně předem prostřednictvím platební brány Stripe (Stripe Payments Europe, Ltd., Irsko), a to platební kartou nebo jiným způsobem nabídnutým v platební bráně. Údaje o platební kartě zpracovává výhradně Stripe; poskytovatel k nim nemá přístup.',
          'Případné poplatky za převod měny účtuje banka zákazníka. Daňový doklad vystaví poskytovatel v elektronické podobě a zašle jej zákazníkovi e-mailem.',
        ],
      },
      {
        title: '5. Poskytnutí plnění',
        paragraphs: [
          'Není-li u nabídky uvedeno jinak, poskytovatel zpřístupní digitální obsah nebo zahájí poskytování služby bez zbytečného odkladu po připsání platby. U zboží jsou způsob, cena a lhůta dodání uvedeny u nabídky.',
        ],
      },
      {
        title: '6. Odstoupení od smlouvy (spotřebitel)',
        paragraphs: [
          'Spotřebitel má právo odstoupit od smlouvy bez udání důvodu do 14 dnů ode dne uzavření smlouvy, u zboží ode dne jeho převzetí. Odstoupení lze zaslat na e-mail {{email}}, lze využít vzorový formulář níže. Lhůta je zachována, je-li oznámení odesláno před jejím uplynutím.',
          'Poskytovatel vrátí přijaté peníze do 14 dnů od odstoupení, a to stejným platebním prostředkem, jakým byla platba provedena. Pokud spotřebitel výslovně požádal o zahájení poskytování služby před uplynutím lhůty pro odstoupení, uhradí poměrnou část ceny za plnění poskytnuté do okamžiku odstoupení.',
          'Spotřebitel nemůže odstoupit zejména od smlouvy o dodání digitálního obsahu, který nebyl dodán na hmotném nosiči, pokud byl dodán s jeho předchozím výslovným souhlasem před uplynutím lhůty pro odstoupení a byl poučen, že tím právo na odstoupení ztrácí, a od smlouvy o službách, které byly s jeho výslovným souhlasem zcela poskytnuty.',
        ],
      },
      {
        title: '7. Práva z vadného plnění a reklamace',
        paragraphs: [
          'Práva z vadného plnění se řídí občanským zákoníkem. Reklamaci lze uplatnit e-mailem na {{email}}; zákazník v ní popíše vadu a navrhne způsob vyřízení. Poskytovatel potvrdí přijetí reklamace a vyřídí ji bez zbytečného odkladu, nejpozději do 30 dnů, pokud se se spotřebitelem nedohodne na delší lhůtě. O vyřízení vydá písemné potvrzení.',
        ],
      },
      {
        title: '8. Mimosoudní řešení sporů',
        paragraphs: [
          'K mimosoudnímu řešení spotřebitelských sporů je příslušná Česká obchodní inspekce, Ústřední inspektorát – oddělení ADR, Gorazdova 1969/24, 120 00 Praha 2, www.adr.coi.cz. Spotřebitelé z jiných států EU se mohou obrátit také na Evropské spotřebitelské centrum ve svém státě (síť ECC-Net).',
          'Stížnosti lze podat poskytovateli na e-mail {{email}} nebo dozorovému orgánu, kterým je Česká obchodní inspekce.',
        ],
      },
      {
        title: '9. Zahraniční zákazníci',
        paragraphs: [
          'Nabídka je určena zákazníkům z České republiky, jiných členských států EU i ze zemí mimo EU. Smlouva se řídí českým právem. Je-li zákazník spotřebitelem s obvyklým bydlištěm v jiném státě, nezbavuje ho tato volba ochrany, kterou mu poskytují kogentní ustanovení práva státu jeho bydliště.',
          'U zákazníků z jiných států může být cena zatížena daní z přidané hodnoty podle státu zákazníka; konečná cena se vždy zobrazí před zaplacením. Případná cla, dovozní poplatky a daně mimo EU nese zákazník, není-li u nabídky uvedeno jinak.',
        ],
      },
      {
        title: '10. Ochrana osobních údajů',
        paragraphs: [
          'Zpracování osobních údajů se řídí dokumentem Ochrana osobních údajů zveřejněným na tomto webu.',
        ],
      },
      {
        title: '11. Závěrečná ustanovení',
        paragraphs: [
          'Poskytovatel může obchodní podmínky měnit; na smlouvu se použije znění účinné v okamžiku jejího uzavření. Tyto obchodní podmínky jsou účinné od {{effectiveFrom}}.',
        ],
      },
      {
        title: 'Příloha: vzorový formulář pro odstoupení od smlouvy',
        paragraphs: ['(vyplňte a zašlete jej, pouze pokud chcete odstoupit od smlouvy)'],
        items: [
          'Adresát: {{name}}, {{address}}, e-mail {{email}}',
          'Oznamuji, že tímto odstupuji od smlouvy o (název zboží / služby / digitálního obsahu):',
          'Datum objednání / datum převzetí:',
          'Jméno a příjmení spotřebitele:',
          'Adresa spotřebitele:',
          'Číslo platby nebo objednávky:',
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
          'Údaje o platbách: předmět, částka, měna, stav a identifikátory platby. Údaje o platební kartě zpracovává výhradně Stripe – my je nevidíme ani neukládáme.',
          'Komunikace: obsah e-mailů a zpráv, které nám zašlete (např. reklamace, dotazy).',
          'Technické údaje: IP adresa, čas a typ požadavku v provozních záznamech serveru.',
        ],
      },
      {
        title: 'Proč údaje zpracováváme',
        items: [
          'uzavření a plnění smlouvy, včetně přijetí platby a zákaznické podpory,',
          'plnění zákonných povinností, zejména účetních a daňových,',
          'zabezpečení služby, předcházení podvodům a ochrana našich právních nároků.',
        ],
      },
      {
        title: 'Komu údaje předáváme',
        items: [
          'Stripe Payments Europe, Ltd. (Irsko) – zpracování plateb a ochrana proti podvodům; pro vlastní zákonné povinnosti vystupuje jako samostatný správce (stripe.com/privacy).',
          'Provozovatel přihlašovací služby auth.withfbraun.com – správa uživatelských účtů.',
          'Poskytovatelé hostingu, e-mailu a účetních služeb, kteří údaje zpracovávají pouze podle našich pokynů.',
          'Orgány veřejné moci, pokud to vyžaduje zákon.',
        ],
      },
      {
        title: 'Jak dlouho údaje uchováváme',
        paragraphs: [
          'Údaje o účtu po dobu trvání účtu. Údaje o platbách a daňové doklady po dobu stanovenou účetními a daňovými předpisy (zpravidla 10 let). Komunikaci po dobu nutnou k vyřízení věci a promlčecí lhůty případných nároků. Provozní záznamy nejvýše několik týdnů.',
        ],
      },
    ],
    gdprSections: [
      {
        title: 'Právní základy zpracování (GDPR)',
        items: [
          'plnění smlouvy – čl. 6 odst. 1 písm. b) GDPR,',
          'plnění právní povinnosti – čl. 6 odst. 1 písm. c) GDPR,',
          'oprávněný zájem na zabezpečení služby, předcházení podvodům a ochraně nároků – čl. 6 odst. 1 písm. f) GDPR.',
        ],
        paragraphs: [
          'Poskytnutí údajů potřebných k uzavření smlouvy je smluvním požadavkem – bez nich nelze smlouvu uzavřít. Automatizované rozhodování ani profilování s právními účinky neprovádíme; Stripe může platby automaticky prověřovat kvůli ochraně proti podvodům.',
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
          'právo podat stížnost u Úřadu pro ochranu osobních údajů, Pplk. Sochora 27, 170 00 Praha 7, www.uoou.gov.cz, nebo u dozorového úřadu ve státě EU, kde máte bydliště či pracujete.',
        ],
        paragraphs: ['Svá práva uplatníte e-mailem na {{email}}. Odpovíme nejpozději do jednoho měsíce.'],
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
          'These terms and conditions govern the rights and obligations between the provider {{name}}, Company ID {{ico}}, registered at {{address}}, {{registration}} (the “provider”), and the customer when concluding distance contracts through the website {{web}}.',
          'The customer may be a consumer or a business. Provisions on consumer rights apply only to customers who are consumers. Provider contact: email {{email}}, phone {{phone}}.',
        ],
      },
      {
        title: '2. Subject of the contract',
        paragraphs: [
          '{{service}}',
          'A detailed description, scope and price are given with each offer on the website.',
        ],
      },
      {
        title: '3. Conclusion of the contract',
        paragraphs: [
          'Offers presented on the website are an invitation to submit an order. The customer submits an order by pressing the “Order and pay” button; before doing so, they can review and correct the data entered.',
          'The contract is concluded once the payment has been successfully completed. The provider confirms the contract to the customer by email. Contracts are concluded in Czech or English; the provider archives them electronically and makes them available to the customer on request.',
          'The costs of distance communication (internet, phone) are borne by the customer and do not differ from the standard rate.',
        ],
      },
      {
        title: '4. Price and payment terms',
        paragraphs: [
          'Prices are stated with each offer and are final. The provider is: {{vatStatement}}. The final price including currency is displayed to the customer before the payment is confirmed.',
          'Payment is made in advance, cashless, through the Stripe payment gateway (Stripe Payments Europe, Ltd., Ireland), by payment card or another method offered by the gateway. Card details are processed exclusively by Stripe; the provider has no access to them.',
          'Any currency conversion fees are charged by the customer’s bank. The provider issues the tax document electronically and sends it to the customer by email.',
        ],
      },
      {
        title: '5. Delivery',
        paragraphs: [
          'Unless stated otherwise with the offer, the provider makes digital content available or starts providing the service without undue delay after the payment has been received. For goods, the delivery method, cost and time are stated with the offer.',
        ],
      },
      {
        title: '6. Right of withdrawal (consumers)',
        paragraphs: [
          'A consumer may withdraw from the contract without giving any reason within 14 days of concluding it, or for goods within 14 days of receiving them. The withdrawal can be sent to {{email}}; the model form below may be used. The deadline is met if the notice is sent before it expires.',
          'The provider refunds the payment within 14 days of the withdrawal, using the same payment method as the original payment. If the consumer expressly requested that the service start before the withdrawal period ends, they pay a proportionate part of the price for what was provided up to the withdrawal.',
          'In particular, a consumer cannot withdraw from a contract for digital content not supplied on a tangible medium if it was supplied with their prior express consent before the withdrawal period ended and they acknowledged losing the right of withdrawal, nor from a service contract once the service has been fully performed with their express consent.',
        ],
      },
      {
        title: '7. Defective performance and complaints',
        paragraphs: [
          'Rights arising from defective performance are governed by the Czech Civil Code. Complaints can be made by email to {{email}}, describing the defect and the proposed remedy. The provider confirms receipt and settles the complaint without undue delay, within 30 days at the latest unless a longer period is agreed with the consumer, and issues a written confirmation of how it was settled.',
        ],
      },
      {
        title: '8. Out-of-court dispute resolution',
        paragraphs: [
          'Out-of-court resolution of consumer disputes is handled by the Czech Trade Inspection Authority, Central Inspectorate - ADR Department, Gorazdova 1969/24, 120 00 Prague 2, www.adr.coi.cz. Consumers from other EU countries may also contact the European Consumer Centre in their country (ECC-Net).',
          'Complaints can be sent to the provider at {{email}} or to the supervisory authority, the Czech Trade Inspection Authority.',
        ],
      },
      {
        title: '9. Customers outside the Czech Republic',
        paragraphs: [
          'The offer is intended for customers from the Czech Republic, other EU member states and countries outside the EU. The contract is governed by Czech law. Where the customer is a consumer habitually resident in another country, this choice of law does not deprive them of the protection afforded by the mandatory provisions of the law of their country of residence.',
          'For customers from other countries, the price may include value added tax of the customer’s country; the final price is always shown before payment. Any customs duties, import fees and taxes outside the EU are borne by the customer unless stated otherwise with the offer.',
        ],
      },
      {
        title: '10. Personal data protection',
        paragraphs: ['Personal data processing is governed by the Privacy policy published on this website.'],
      },
      {
        title: '11. Final provisions',
        paragraphs: [
          'The provider may amend these terms; the version in effect when the contract was concluded applies to it. These terms and conditions are effective from {{effectiveFrom}}.',
        ],
      },
      {
        title: 'Annex: model withdrawal form',
        paragraphs: ['(complete and return this form only if you wish to withdraw from the contract)'],
        items: [
          'To: {{name}}, {{address}}, email {{email}}',
          'I hereby give notice that I withdraw from my contract for (goods / service / digital content):',
          'Ordered on / received on:',
          'Name of consumer:',
          'Address of consumer:',
          'Payment or order number:',
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
          'Payment data: subject, amount, currency, status and identifiers of the payment. Card details are processed exclusively by Stripe - we never see or store them.',
          'Communication: the content of emails and messages you send us (e.g. complaints, questions).',
          'Technical data: IP address, time and type of request in the server’s operational logs.',
        ],
      },
      {
        title: 'Why we process it',
        items: [
          'to conclude and perform the contract, including accepting payment and customer support,',
          'to comply with legal obligations, in particular accounting and tax obligations,',
          'to keep the service secure, prevent fraud and protect our legal claims.',
        ],
      },
      {
        title: 'Who we share it with',
        items: [
          'Stripe Payments Europe, Ltd. (Ireland) - payment processing and fraud prevention; an independent controller for its own legal obligations (stripe.com/privacy).',
          'The operator of the sign-in service auth.withfbraun.com - user account management.',
          'Hosting, email and accounting service providers, processing data only on our instructions.',
          'Public authorities, where required by law.',
        ],
      },
      {
        title: 'How long we keep it',
        paragraphs: [
          'Account data for as long as the account exists. Payment data and tax documents for the period required by accounting and tax law (usually 10 years). Communication for as long as needed to handle the matter and for the limitation period of any claims. Operational logs for a few weeks at most.',
        ],
      },
    ],
    gdprSections: [
      {
        title: 'Legal bases (GDPR)',
        items: [
          'performance of a contract - Art. 6(1)(b) GDPR,',
          'compliance with a legal obligation - Art. 6(1)(c) GDPR,',
          'legitimate interest in keeping the service secure, preventing fraud and protecting claims - Art. 6(1)(f) GDPR.',
        ],
        paragraphs: [
          'Providing the data needed to conclude the contract is a contractual requirement - the contract cannot be concluded without it. We do not carry out automated decision-making or profiling with legal effects; Stripe may screen payments automatically to prevent fraud.',
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
          'the right to lodge a complaint with the Czech Office for Personal Data Protection, Pplk. Sochora 27, 170 00 Prague 7, www.uoou.gov.cz, or with the supervisory authority of the EU country where you live or work.',
        ],
        paragraphs: ['To exercise your rights, email us at {{email}}. We reply within one month at the latest.'],
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
