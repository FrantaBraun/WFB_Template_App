/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Event calendar, built on the articles module: an event is a date (or a run
// of days, with optional times) belonging to one article, so an event has no
// page of its own - it leads to its article. /events (upcoming list + month
// listings, calendar and year/month archive in the sidebar) and the editors'
// /events/manage area. EventCalendar and EventCard are exported for
// applications that want them on other pages too (e.g. a home page), with
// the Dashboard / DatedArticle types of GET /dashboard.
//
// Slots this module defines (see ModuleSlot / ModuleDefinition.slots):
//   event.actions - after each date of an article on the article page, context `{ event }` (EventTeaser)
//   event.manage  - in each row of the administrators' event list, context `{ event }` (EventAdmin)
//   event.editor  - below the form of a *saved* event in the editor, context `{ event }` (EventAdmin)
// and contributes to the articles module's slots:
//   article.detail - the article's dates (each with the event.actions slot)
//   article.editor - a panel to add / edit / delete the article's dates
import '../articles/articles.css'
import type { ModuleDefinition } from '../types'
import { ArticleDates, ArticleDatesPanel } from './ArticleEvents'
import EventFormPage from './EventFormPage'
import EventsPage from './EventsPage'
import ManageEventsPage from './ManageEventsPage'

export { default as EventCalendar } from './EventCalendar'
export { EventCard } from './EventsPage'
export { eventPath, formatEventWhen } from './api'
export type { Dashboard, DatedArticle, EventAdmin, EventTeaser } from './api'

const eventCalendarModule: ModuleDefinition = {
  key: 'event_calendar',
  requires: ['articles'],
  routes: [
    { path: '/events', element: <EventsPage /> },
    { path: '/events/manage', element: <ManageEventsPage /> },
    { path: '/events/manage/new', element: <EventFormPage /> },
    { path: '/events/manage/:id', element: <EventFormPage /> },
  ],
  nav: [{ to: '/events', labelKey: 'event_calendar:nav.events' }],
  slots: {
    'article.detail': ArticleDates,
    'article.editor': ArticleDatesPanel,
  },
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
        legendPinned: 'Připnutý článek',
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
        archived: 'archivováno',
        emptyUpcoming: 'Žádné nadcházející akce.',
        emptyMonth: 'V tomto měsíci nejsou žádné akce.',
        error: 'Akce se nepodařilo načíst.',
      },
      articleStatus: { draft: 'rozpracováno', published: 'publikováno', archived: 'archivováno' },
      articleDates: {
        title: 'Termíny',
        over: 'proběhlo',
        add: 'Přidat termín',
        none: 'Tento článek zatím nemá žádný termín.',
        edit: 'Upravit',
        delete: 'Smazat',
      },
      manage: {
        title: 'Správa akcí',
        new: 'Nový termín',
        empty: 'Zatím žádné termíny.',
        forbidden: 'Na správu akcí nemáte oprávnění.',
      },
      form: {
        newTitle: 'Nový termín',
        editTitle: 'Upravit termín',
        backToList: 'Zpět na seznam',
        viewArticle: 'Zobrazit článek',
        article: 'Článek',
        articleChange: 'Změnit článek',
        articleKeep: 'Ponechat vybraný článek',
        articleSearch: 'Hledat článek podle názvu…',
        articleNoResults: 'Žádný článek nenalezen.',
        noArticle: 'Vyberte článek, ke kterému termín patří.',
        title: 'Název termínu',
        titleHint: 'Předvyplněno názvem článku; hodí se upřesnit, např. „Jarní bazar – sobota“.',
        shortDescription: 'Krátký popis (zobrazí se v kalendáři po najetí myší)',
        startDate: 'Datum',
        endDate: 'Do (u vícedenní akce)',
        startTime: 'Čas od',
        endTime: 'Čas do',
        termHint: 'Datum „do“ a časy jsou nepovinné. Čas „do“ lze zadat jen s časem „od“.',
        save: 'Uložit',
        saving: 'Ukládání…',
        saved: 'Uloženo.',
        delete: 'Smazat termín',
        confirmDelete: 'Opravdu smazat tento termín? Článek zůstane.',
        deleteBlocked: 'Termín nejde smazat, navazují na něj další údaje (například registrace).',
        deleteError: 'Termín se nepodařilo smazat.',
        invalid: 'Zkontrolujte vyplněné údaje (datum „do“ nesmí být před datem, čas „do“ před časem „od“; popis má nejvýše 128 znaků).',
        saveError: 'Uložení se nezdařilo.',
        loadError: 'Termín se nepodařilo načíst.',
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
        legendPinned: 'Pinned article',
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
        archived: 'archived',
        emptyUpcoming: 'No upcoming events.',
        emptyMonth: 'No events this month.',
        error: 'Could not load events.',
      },
      articleStatus: { draft: 'draft', published: 'published', archived: 'archived' },
      articleDates: {
        title: 'Dates',
        over: 'past',
        add: 'Add a date',
        none: 'This article has no dates yet.',
        edit: 'Edit',
        delete: 'Delete',
      },
      manage: {
        title: 'Manage events',
        new: 'New date',
        empty: 'No dates yet.',
        forbidden: 'You are not allowed to manage events.',
      },
      form: {
        newTitle: 'New date',
        editTitle: 'Edit date',
        backToList: 'Back to list',
        viewArticle: 'View article',
        article: 'Article',
        articleChange: 'Change article',
        articleKeep: 'Keep the selected article',
        articleSearch: 'Search articles by title…',
        articleNoResults: 'No article found.',
        noArticle: 'Choose the article this date belongs to.',
        title: 'Name of the date',
        titleHint: 'Filled in with the article title; worth making more specific, e.g. "Spring book sale – Saturday".',
        shortDescription: 'Short description (shown in the calendar when you point at the event)',
        startDate: 'Date',
        endDate: 'Until (for a multi-day event)',
        startTime: 'Time from',
        endTime: 'Time until',
        termHint: 'The "until" date and the times are optional. A "time until" needs a "time from".',
        save: 'Save',
        saving: 'Saving…',
        saved: 'Saved.',
        delete: 'Delete date',
        confirmDelete: 'Really delete this date? The article stays.',
        deleteBlocked: 'This date cannot be deleted, other data depends on it (for example a registration).',
        deleteError: 'Could not delete the date.',
        invalid: 'Check the form (the "until" date must not be before the date, the "time until" not before "time from"; the description is at most 128 characters).',
        saveError: 'Saving failed.',
        loadError: 'Could not load the date.',
      },
    },
  },
}

export default eventCalendarModule
