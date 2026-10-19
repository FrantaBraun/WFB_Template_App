/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// The legal pages' texts, Czech. A DRAFT for a lawyer to read before launch
// (retention periods, the list of recipients and the consumer wording in
// particular). {{placeholders}} are filled from the provider details in
// backend/.env (see ../legal/LegalShell.tsx); a value that is not set shows as a dash.
import type { LegalSection } from './types'

const provider = [
  'Jméno: {{name}}',
  'IČO: {{ico}}',
  'DIČ: {{dic}}',
  'Sídlo / místo podnikání: {{address}}',
  'Zápis: {{registration}}',
  'E-mail: {{email}}',
  'Telefon: {{phone}}',
]

export const legalCs: { privacy: LegalSection[]; terms: LegalSection[]; cookies: LegalSection[] } = {
  privacy: [
    {
      title: 'Kdo je správcem osobních údajů',
      items: provider,
      paragraphs: ['S dotazy k osobním údajům a s uplatněním svých práv se na mě můžete obrátit na {{dpoEmail}}.'],
    },
    {
      title: 'Kontaktní formulář a e-mail',
      paragraphs: [
        'Pokud mi napíšete přes kontaktní formulář nebo e-mailem, zpracovávám Vaši e-mailovou adresu (případně jméno) a obsah zprávy. Formulář zprávu odešle e-mailem, neukládá ji do databáze webu.',
      ],
      items: [
        'Účel: vyřízení Vašeho dotazu a jednání o případné spolupráci.',
        'Právní základ: opatření přijatá před uzavřením smlouvy na Vaši žádost a můj oprávněný zájem odpovědět na Váš dotaz (čl. 6 odst. 1 písm. b) a f) GDPR).',
        'Doba uložení: po dobu vyřízení dotazu; pokud ke spolupráci nedojde, zprávu smažu nejpozději do 12 měsíců.',
      ],
    },
    {
      title: 'Spolupráce a zakázky',
      paragraphs: [
        'Pokud se domluvíme na spolupráci, zpracovávám identifikační a kontaktní údaje Vaše (případně Vašich zaměstnanců), údaje o zakázce a fakturační údaje. Vedu je v evidenci partnerů a zakázek, ke které má přístup jen správce webu.',
      ],
      items: [
        'Účel: plnění smlouvy, komunikace při zakázce, fakturace, účetnictví a daně.',
        'Právní základ: plnění smlouvy a splnění právní povinnosti (čl. 6 odst. 1 písm. b) a c) GDPR).',
        'Doba uložení: po dobu spolupráce a poté po dobu, kterou právní předpisy stanoví pro účetní a daňové doklady.',
      ],
    },
    {
      title: 'Přihlášení správce',
      paragraphs: [
        'Přihlásit se může jen správce webu. Návštěvníci nemají účet a kvůli přihlášení se o nich nezpracovávají žádné údaje. Účet správce vede autorizační služba auth.withfbraun.com, kterou provozuji já.',
      ],
    },
    {
      title: 'Provozní záznamy',
      paragraphs: [
        'Webový server zaznamenává technické údaje o každém požadavku – IP adresu, čas, požadovanou adresu a typ prohlížeče. Slouží k zajištění bezpečnosti a provozu webu (oprávněný zájem, čl. 6 odst. 1 písm. f) GDPR) a uchovávají se jen po dobu, po kterou se provozní záznamy ukládají.',
      ],
    },
    {
      title: 'Komu údaje předávám',
      paragraphs: [
        'Údaje neprodávám ani je nepředávám pro marketingové účely. Přístup k nim mohou mít jen poskytovatelé služeb, které k provozu potřebuji (hosting, e-mail, účetní nebo daňový poradce), a orgány veřejné moci, pokud mi to ukládá zákon.',
        'Pokud by poskytovatel některé z těchto služeb sídlil mimo Evropský hospodářský prostor, zajistím, aby předání bylo kryté standardními smluvními doložkami nebo rozhodnutím o odpovídající ochraně.',
      ],
    },
    {
      title: 'Automatizované rozhodování',
      paragraphs: ['K automatizovanému rozhodování ani profilování, které by mělo právní účinky, nedochází.'],
    },
    {
      title: 'Vaše práva',
      paragraphs: ['Máte právo:'],
      items: [
        'na přístup ke svým osobním údajům,',
        'na opravu nepřesných údajů,',
        'na výmaz údajů, pokud pominul důvod jejich zpracování,',
        'na omezení zpracování,',
        'na přenositelnost údajů, které jste mi poskytli,',
        'vznést námitku proti zpracování založenému na oprávněném zájmu,',
        'podat stížnost u Úřadu pro ochranu osobních údajů (www.uoou.gov.cz).',
      ],
    },
    {
      title: 'Jak se svými právy naložit',
      paragraphs: ['Napište mi na {{dpoEmail}}. Odpovím Vám nejpozději do jednoho měsíce.'],
    },
    {
      title: 'Zabezpečení',
      paragraphs: [
        'Údaje chráním přiměřenými technickými a organizačními opatřeními, mimo jiné šifrovaným přenosem (HTTPS), omezeným přístupem a pravidelnými bezpečnostními opravami.',
      ],
    },
    {
      title: 'Cookies',
      paragraphs: ['Web nepoužívá analytické ani reklamní cookies. Podrobnosti najdete na stránce Cookies.'],
    },
    {
      title: 'Změny těchto zásad',
      paragraphs: ['Zásady mohu aktualizovat. Platí vždy znění zveřejněné na této stránce, s uvedeným datem účinnosti.'],
    },
  ],
  terms: [
    {
      title: 'Provozovatel webu',
      items: provider,
    },
    {
      title: 'O čem tento web je',
      paragraphs: [
        'Web slouží k prezentaci mých služeb a zkušeností. Informace na něm mají informativní charakter a nejsou návrhem na uzavření smlouvy. Ceník je orientační.',
      ],
    },
    {
      title: 'Spolupráce',
      paragraphs: [
        'Jednotlivé zakázky se řídí individuální smlouvou nebo odsouhlasenou nabídkou, ve které se dohodneme na rozsahu, ceně, termínech a podmínkách provozu.',
        'Cena se skládá z platby za implementaci a servisního poplatku za provoz. Servisní poplatek zahrnuje plný provoz řešení, bezpečnostní opravy a drobné úpravy na základě žádosti. Větší úpravy se řeší vždy individuálně a konkrétně.',
        'Každé řešení je dodáno včetně administrace obsahu a dokumentace.',
      ],
    },
    {
      title: 'Obsah webu',
      paragraphs: [
        'Texty a grafika tohoto webu jsou chráněny autorským právem. Bez mého souhlasu je nelze kopírovat ani šířit nad rámec zákonných výjimek. Odkazy na weby třetích stran vedou na obsah, za který neodpovídám.',
      ],
    },
    {
      title: 'Odpovědnost',
      paragraphs: [
        'Snažím se, aby informace na webu byly správné a aktuální, nezaručuji však jejich úplnost. Za škodu vzniklou použitím informací z webu neodpovídám, pokud zákon nestanoví jinak.',
      ],
    },
    {
      title: 'Spotřebitelé',
      paragraphs: [
        'Je-li klientem spotřebitel, řídí se vztah také zákonnou úpravou ochrany spotřebitele. Spotřebitel má právo na mimosoudní řešení sporu; příslušným subjektem je Česká obchodní inspekce (www.coi.cz, adr.coi.cz).',
      ],
    },
    {
      title: 'Ochrana osobních údajů',
      paragraphs: ['Jak nakládám s osobními údaji, popisují zásady ochrany osobních údajů.'],
    },
    {
      title: 'Rozhodné právo a změny',
      paragraphs: [
        'Vztahy se řídí právním řádem České republiky. Tyto podmínky mohu aktualizovat; platí znění zveřejněné na této stránce, s uvedeným datem účinnosti.',
      ],
    },
  ],
  cookies: [
    {
      title: 'Co web ukládá',
      paragraphs: [
        'Web nepoužívá analytické, marketingové ani žádné cookies třetích stran. Ukládá jen malé množství technických údajů v místním úložišti prohlížeče (localStorage), které jsou nutné k tomu, aby web fungoval a pamatoval si Vaše nastavení. K takovému úložišti se souhlas nevyžaduje.',
      ],
    },
    {
      title: 'Přehled údajů',
      items: [
        'i18nextLng – zvolený jazyk webu. Uchovává se, dokud ho nesmažete.',
        'dark_mode – zvolený světlý nebo tmavý režim. Uchovává se, dokud ho nesmažete.',
        'access_token, refresh_token – přihlášení správce webu. Vytvářejí se jen po přihlášení správce, návštěvníkům nikdy; zanikají odhlášením.',
      ],
    },
    {
      title: 'Jak údaje smazat',
      paragraphs: ['Místní úložiště můžete kdykoli smazat v nastavení prohlížeče. Web pak použije výchozí nastavení.'],
    },
    {
      title: 'Změny',
      paragraphs: ['Pokud by web v budoucnu začal používat další úložiště nebo analytiku, tato stránka i zásady ochrany osobních údajů se před tím aktualizují.'],
    },
  ],
}
