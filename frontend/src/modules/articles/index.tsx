/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Articles: /articles (newest first, type filter, search), /articles/:slug
// (the article page) and the administrators' /articles/manage area (list,
// editor, article types). ArticleCard and the typeStyle() helper are
// exported for applications that show articles on other pages (e.g. a home
// page). Modules built on articles extend the pages through two slots:
//   article.detail - on the article page, context `{ article }` (ArticleDetail)
//   article.editor - in the editor of a saved article, context `{ article }` (ArticleAdmin)
import type { ModuleDefinition } from '../types'
import ArticleDetailPage from './ArticleDetailPage'
import ArticleFormPage from './ArticleFormPage'
import ArticlesPage from './ArticlesPage'
import ManageArticlesPage from './ManageArticlesPage'
import ManageTypesPage from './ManageTypesPage'

export { default as ArticleCard } from './ArticleCard'
export { articlePath, typeStyle } from './api'
export type { ArticleDetail, ArticleTeaser, ArticleType } from './api'

const articlesModule: ModuleDefinition = {
  key: 'articles',
  routes: [
    { path: '/articles', element: <ArticlesPage /> },
    { path: '/articles/manage', element: <ManageArticlesPage /> },
    { path: '/articles/manage/new', element: <ArticleFormPage /> },
    { path: '/articles/manage/types', element: <ManageTypesPage /> },
    { path: '/articles/manage/:id', element: <ArticleFormPage /> },
    { path: '/articles/:slug', element: <ArticleDetailPage /> },
  ],
  nav: [{ to: '/articles', labelKey: 'articles:nav.articles' }],
  locales: {
    cs: {
      nav: { articles: 'Články' },
      common: {
        loading: 'Načítání…',
        forbidden: 'Tato část je jen pro administrátora.',
      },
      status: { draft: 'Rozpracováno', published: 'Publikováno', archived: 'Archivováno' },
      card: { pinned: 'Připnuto' },
      list: {
        title: 'Články',
        description: 'Články, reportáže a oznámení.',
        manage: 'Spravovat články',
        searchPlaceholder: 'Hledat v článcích…',
        typeFilter: 'Typ článku',
        allTypes: 'Všechny typy',
        includeArchived: 'Zobrazit i archivované',
        loadMore: 'Načíst další',
        error: 'Články se nepodařilo načíst.',
        empty: 'Zatím tu nejsou žádné články.',
        noResults: 'Nic jsme nenašli.',
      },
      detail: { notFound: 'Článek nebyl nalezen.', back: 'Všechny články', edit: 'Upravit' },
      manage: {
        title: 'Správa článků',
        new: 'Nový článek',
        types: 'Typy článků',
        statusFilter: 'Stav',
        allStatuses: 'Všechny stavy',
        empty: 'Žádné články.',
      },
      form: {
        newTitle: 'Nový článek',
        editTitle: 'Upravit článek',
        backToList: 'Zpět na seznam',
        view: 'Zobrazit',
        title: 'Název',
        slug: 'Adresa (slug)',
        slugHint: 'Článek bude na {{path}}',
        perex: 'Perex (krátký popis)',
        type: 'Typ',
        noType: 'Bez typu',
        manageTypes: 'Spravovat typy',
        status: 'Stav',
        displayFrom: 'Zobrazovat od',
        displayTo: 'Zobrazovat do',
        displayHint:
          'Platnost zobrazení se týká výpisů a zdi: mimo ni se článek nenabízí, ale odkaz na něj dál funguje. Prázdné pole = bez omezení.',
        pinned: 'Připnout',
        image: 'Obrázek',
        imageUpload: 'Nahrát obrázek',
        imageReplace: 'Nahradit obrázek',
        imageRemove: 'Odebrat',
        content: 'Obsah',
        save: 'Uložit',
        saving: 'Ukládání…',
        saved: 'Uloženo.',
        saveError: 'Článek se nepodařilo uložit.',
        slugTaken: 'Tato adresa už je použitá.',
        invalid: 'Zkontrolujte vyplněné údaje (adresa, data, typ).',
        loadError: 'Článek se nepodařilo načíst.',
        uploadError: 'Obrázek se nepodařilo nahrát (PNG, JPEG, WebP nebo GIF do 5 MB).',
      },
      types: {
        title: 'Typy článků',
        intro: 'Každý typ má rámeček a podbarvení zvlášť pro světlý a tmavý režim; v nich se článek daného typu zobrazuje.',
        empty: 'Zatím žádný typ.',
        name: 'Název',
        border_light: 'Rámeček (světlý)',
        background_light: 'Podbarvení (světlé)',
        border_dark: 'Rámeček (tmavý)',
        background_dark: 'Podbarvení (tmavé)',
        previewLight: 'Světlý',
        previewDark: 'Tmavý',
        articleCount_one: '{{count}} článek',
        articleCount_few: '{{count}} články',
        articleCount_many: '{{count}} článku',
        articleCount_other: '{{count}} článků',
        saved: 'Uloženo.',
        saveError: 'Typ se nepodařilo uložit.',
        nameTaken: 'Typ s tímto názvem už existuje.',
        replaceWith: 'Nahradit typem…',
        delete: 'Smazat',
        confirmDelete: 'Opravdu smazat tento typ?',
        confirmDeleteUsed: 'Smazat typ a přesunout jeho články ({{count}}) na vybraný typ?',
        deleteError: 'Typ se nepodařilo smazat.',
        newTitle: 'Nový typ',
        create: 'Přidat typ',
      },
    },
    en: {
      nav: { articles: 'Articles' },
      common: {
        loading: 'Loading…',
        forbidden: 'This area is for the administrator only.',
      },
      status: { draft: 'Draft', published: 'Published', archived: 'Archived' },
      card: { pinned: 'Pinned' },
      list: {
        title: 'Articles',
        description: 'Articles, reports and announcements.',
        manage: 'Manage articles',
        searchPlaceholder: 'Search articles…',
        typeFilter: 'Article type',
        allTypes: 'All types',
        includeArchived: 'Show archived too',
        loadMore: 'Load more',
        error: 'Could not load the articles.',
        empty: 'There are no articles yet.',
        noResults: 'Nothing found.',
      },
      detail: { notFound: 'Article not found.', back: 'All articles', edit: 'Edit' },
      manage: {
        title: 'Manage articles',
        new: 'New article',
        types: 'Article types',
        statusFilter: 'Status',
        allStatuses: 'All statuses',
        empty: 'No articles.',
      },
      form: {
        newTitle: 'New article',
        editTitle: 'Edit article',
        backToList: 'Back to the list',
        view: 'View',
        title: 'Title',
        slug: 'Address (slug)',
        slugHint: 'The article will be at {{path}}',
        perex: 'Perex (short description)',
        type: 'Type',
        noType: 'No type',
        manageTypes: 'Manage types',
        status: 'Status',
        displayFrom: 'Show from',
        displayTo: 'Show until',
        displayHint:
          'The display window applies to listings and the wall: outside it the article is not offered, but a link to it keeps working. Empty = no limit.',
        pinned: 'Pin',
        image: 'Image',
        imageUpload: 'Upload an image',
        imageReplace: 'Replace image',
        imageRemove: 'Remove',
        content: 'Content',
        save: 'Save',
        saving: 'Saving…',
        saved: 'Saved.',
        saveError: 'Could not save the article.',
        slugTaken: 'That address is already in use.',
        invalid: 'Check the entered values (address, dates, type).',
        loadError: 'Could not load the article.',
        uploadError: 'Could not upload the image (PNG, JPEG, WebP or GIF, up to 5 MB).',
      },
      types: {
        title: 'Article types',
        intro: 'Each type has a frame and a background for the light and the dark theme separately; articles of that type are drawn in them.',
        empty: 'No types yet.',
        name: 'Name',
        border_light: 'Frame (light)',
        background_light: 'Background (light)',
        border_dark: 'Frame (dark)',
        background_dark: 'Background (dark)',
        previewLight: 'Light',
        previewDark: 'Dark',
        articleCount_one: '{{count}} article',
        articleCount_other: '{{count}} articles',
        saved: 'Saved.',
        saveError: 'Could not save the type.',
        nameTaken: 'A type with this name already exists.',
        replaceWith: 'Replace with…',
        delete: 'Delete',
        confirmDelete: 'Really delete this type?',
        confirmDeleteUsed: 'Delete the type and move its articles ({{count}}) to the selected type?',
        deleteError: 'Could not delete the type.',
        newTitle: 'New type',
        create: 'Add type',
      },
    },
  },
}

export default articlesModule
