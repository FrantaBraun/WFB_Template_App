/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Event calendar: /events (upcoming list + month listings, calendar and
// year/month archive in the sidebar), /events/:slug (event page) and the
// editors' /events/manage area. EventCalendar and EventCard are exported
// for applications that want them on other pages too (e.g. a home page).
import type { ModuleDefinition } from '../types'
import EventDetailPage from './EventDetailPage'
import EventFormPage from './EventFormPage'
import EventsPage from './EventsPage'
import ManageEventsPage from './ManageEventsPage'

export { default as EventCalendar } from './EventCalendar'
export { EventCard } from './EventsPage'

const eventCalendarModule: ModuleDefinition = {
  key: 'event_calendar',
  routes: [
    { path: '/events', element: <EventsPage /> },
    { path: '/events/manage', element: <ManageEventsPage /> },
    { path: '/events/manage/new', element: <EventFormPage /> },
    { path: '/events/manage/:id', element: <EventFormPage /> },
    { path: '/events/:slug', element: <EventDetailPage /> },
  ],
  nav: [{ to: '/events', labelKey: 'event_calendar:nav.events' }],
  locales: {
    cs: {
      nav: { events: 'Akce' },
      common: { loading: 'Načítání…' },
      calendar: {
        title: 'Kalendář akcí',
        previous: 'Předchozí měsíc',
        next: 'Další měsíc',
        today: 'Dnes',
        noEvents: 'V tomto měsíci nejsou žádné akce.',
        legendEvent: 'Akce',
        legendPinned: 'Připnutá akce',
        dayWithEvents_one: '{{day}}. – {{count}} akce',
        dayWithEvents_few: '{{day}}. – {{count}} akce',
        dayWithEvents_many: '{{day}}. – {{count}} akcí',
        dayWithEvents_other: '{{day}}. – {{count}} akcí',
      },
      archive: { title: 'Archiv', empty: 'Zatím žádné akce.' },
      list: {
        title: 'Nejbližší akce',
        monthTitle: 'Akce – {{month}} {{year}}',
        loadMore: 'Načíst další',
        backToUpcoming: 'Nejbližší akce',
        manage: 'Spravovat akce',
        pinned: 'Připnuto',
        emptyUpcoming: 'Žádné nadcházející akce.',
        emptyMonth: 'V tomto měsíci nejsou žádné akce.',
        error: 'Akce se nepodařilo načíst.',
      },
      detail: { notFound: 'Akce nebyla nalezena.', back: 'Všechny akce', edit: 'Upravit' },
      status: { draft: 'Koncept', published: 'Publikováno', deleted: 'Smazáno' },
      manage: {
        title: 'Správa akcí',
        new: 'Nová akce',
        empty: 'Zatím žádné akce.',
        showDeleted: 'Zobrazit smazané',
        forbidden: 'Na správu akcí nemáte oprávnění.',
      },
      form: {
        newTitle: 'Nová akce',
        editTitle: 'Upravit akci',
        backToList: 'Zpět na seznam',
        view: 'Zobrazit stránku',
        title: 'Název',
        slug: 'Adresa (slug)',
        slugHint: 'Stránka akce: {{path}}',
        shortDescription: 'Krátký popis (do seznamu)',
        eventDate: 'Datum akce',
        status: 'Stav',
        displayFrom: 'Zobrazovat od',
        displayTo: 'Zobrazovat do',
        displayHint: 'Nevyplněné datum znamená bez omezení. Mimo toto období se akce nezobrazuje v seznamech ani v kalendáři.',
        pinned: 'Připnout (zvýraznit v kalendáři a na úvodní stránce)',
        image: 'Obrázek (miniatura)',
        imageUpload: 'Nahrát obrázek',
        imageReplace: 'Vyměnit obrázek',
        imageRemove: 'Odebrat',
        fullText: 'Obsah stránky',
        save: 'Uložit',
        saving: 'Ukládání…',
        saved: 'Uloženo.',
        slugTaken: 'Tato adresa už je použitá u jiné akce.',
        invalid: 'Zkontrolujte vyplněné údaje (adresa smí obsahovat jen malá písmena, číslice a pomlčky; „zobrazovat od“ nesmí být po „zobrazovat do“).',
        saveError: 'Uložení se nezdařilo.',
        loadError: 'Akci se nepodařilo načíst.',
        uploadError: 'Obrázek se nepodařilo nahrát (PNG, JPG, WebP nebo GIF do 5 MB).',
      },
    },
    en: {
      nav: { events: 'Events' },
      common: { loading: 'Loading…' },
      calendar: {
        title: 'Event calendar',
        previous: 'Previous month',
        next: 'Next month',
        today: 'Today',
        noEvents: 'No events this month.',
        legendEvent: 'Event',
        legendPinned: 'Pinned event',
        dayWithEvents_one: '{{day}} – {{count}} event',
        dayWithEvents_other: '{{day}} – {{count}} events',
      },
      archive: { title: 'Archive', empty: 'No events yet.' },
      list: {
        title: 'Upcoming events',
        monthTitle: 'Events – {{month}} {{year}}',
        loadMore: 'Load more',
        backToUpcoming: 'Upcoming events',
        manage: 'Manage events',
        pinned: 'Pinned',
        emptyUpcoming: 'No upcoming events.',
        emptyMonth: 'No events this month.',
        error: 'Could not load events.',
      },
      detail: { notFound: 'Event not found.', back: 'All events', edit: 'Edit' },
      status: { draft: 'Draft', published: 'Published', deleted: 'Deleted' },
      manage: {
        title: 'Manage events',
        new: 'New event',
        empty: 'No events yet.',
        showDeleted: 'Show deleted',
        forbidden: 'You are not allowed to manage events.',
      },
      form: {
        newTitle: 'New event',
        editTitle: 'Edit event',
        backToList: 'Back to list',
        view: 'View page',
        title: 'Title',
        slug: 'Address (slug)',
        slugHint: 'Event page: {{path}}',
        shortDescription: 'Short description (for listings)',
        eventDate: 'Event date',
        status: 'Status',
        displayFrom: 'Show from',
        displayTo: 'Show until',
        displayHint: 'An empty date means no limit. Outside this period the event is hidden from listings and the calendar.',
        pinned: 'Pin (highlight in the calendar and on the home page)',
        image: 'Image (thumbnail)',
        imageUpload: 'Upload image',
        imageReplace: 'Replace image',
        imageRemove: 'Remove',
        fullText: 'Page content',
        save: 'Save',
        saving: 'Saving…',
        saved: 'Saved.',
        slugTaken: 'This address is already used by another event.',
        invalid: 'Check the form (the address may only contain lowercase letters, digits and hyphens; "show from" must not be after "show until").',
        saveError: 'Saving failed.',
        loadError: 'Could not load the event.',
        uploadError: 'Could not upload the image (PNG, JPG, WebP or GIF up to 5 MB).',
      },
    },
  },
}

export default eventCalendarModule
