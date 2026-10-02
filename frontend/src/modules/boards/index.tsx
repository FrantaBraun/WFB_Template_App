/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Boards: /categories (every category), /categories/:slug (one category's
// posts, endlessly scrolling, with the form to add one) and
// /categories/new. CategoriesList is exported for applications that want it
// on other pages too (the home page does).
import type { ModuleDefinition } from '../types'
import CategoriesPage from './CategoriesPage'
import CategoryPage from './CategoryPage'
import NewCategoryPage from './NewCategoryPage'

export { default as CategoriesList } from './CategoriesList'

const boardsModule: ModuleDefinition = {
  key: 'boards',
  routes: [
    { path: '/categories', element: <CategoriesPage /> },
    // Declared before :slug for readability; react-router ranks the static
    // segment higher either way (and the backend never issues "new" as a slug).
    { path: '/categories/new', element: <NewCategoryPage /> },
    { path: '/categories/:slug', element: <CategoryPage /> },
  ],
  nav: [{ to: '/categories', labelKey: 'boards:nav.categories' }],
  locales: {
    cs: {
      nav: { categories: 'Kategorie' },
      common: { loading: 'Načítání…', loadMore: 'Načíst další', retry: 'Zkusit znovu' },
      list: {
        title: 'Kategorie',
        create: 'Nová kategorie',
        loginToCreate: 'Přihlaste se a založte kategorii',
        empty: 'Zatím tu není žádná kategorie.',
        error: 'Kategorie se nepodařilo načíst.',
        posts_one: '{{count}} příspěvek',
        posts_few: '{{count}} příspěvky',
        posts_many: '{{count}} příspěvku',
        posts_other: '{{count}} příspěvků',
      },
      category: {
        back: 'Všechny kategorie',
        notFound: 'Kategorie nebyla nalezena.',
        loadError: 'Kategorii se nepodařilo načíst.',
        loginToPost: 'Přihlaste se, abyste mohli přidat příspěvek a vyjádřit souznění.',
        empty: 'Zatím tu není žádný příspěvek. Buďte první.',
        error: 'Příspěvky se nepodařilo načíst.',
      },
      post: {
        value: 'Hodnota',
        resonances_one: '{{count}} souznění',
        resonances_few: '{{count}} souznění',
        resonances_many: '{{count}} souznění',
        resonances_other: '{{count}} souznění',
        resonate: 'Souzním',
        resonated: 'Souznění vyjádřeno',
        loginToResonate: 'Přihlaste se, abyste mohli vyjádřit souznění',
        resonateError: 'Souznění se nepodařilo uložit.',
      },
      form: {
        heading: 'Přidat příspěvek',
        title: 'Nadpis',
        body: 'Text',
        emoji: 'Emotikony',
        counter: '{{current}} / {{max}}',
        publish: 'Zveřejnit',
        publishing: 'Zveřejňování…',
        published: 'Příspěvek byl zveřejněn. Řadí se podle své hodnoty, takže se objeví mezi ostatními podle ní.',
        invalid: 'Zkontrolujte nadpis a text – nesmí být prázdné ani příliš dlouhé.',
        error: 'Příspěvek se nepodařilo zveřejnit.',
      },
      newCategory: {
        title: 'Nová kategorie',
        name: 'Název',
        nameHint: 'Adresa kategorie se vytvoří z názvu.',
        description: 'Krátký popis',
        create: 'Založit kategorii',
        creating: 'Zakládání…',
        loginRequired: 'Pro založení kategorie se přihlaste.',
        invalid: 'Zkontrolujte název a popis – nesmí být prázdné ani příliš dlouhé.',
        error: 'Kategorii se nepodařilo založit.',
      },
    },
    en: {
      nav: { categories: 'Categories' },
      common: { loading: 'Loading…', loadMore: 'Load more', retry: 'Try again' },
      list: {
        title: 'Categories',
        create: 'New category',
        loginToCreate: 'Sign in to create a category',
        empty: 'There are no categories yet.',
        error: 'Could not load the categories.',
        posts_one: '{{count}} post',
        posts_other: '{{count}} posts',
      },
      category: {
        back: 'All categories',
        notFound: 'Category not found.',
        loadError: 'Could not load the category.',
        loginToPost: 'Sign in to add a post and to resonate.',
        empty: 'No posts here yet. Be the first.',
        error: 'Could not load the posts.',
      },
      post: {
        value: 'Value',
        resonances_one: '{{count}} resonance',
        resonances_other: '{{count}} resonances',
        resonate: 'Resonate',
        resonated: 'You resonated',
        loginToResonate: 'Sign in to resonate',
        resonateError: 'Could not save your resonance.',
      },
      form: {
        heading: 'Add a post',
        title: 'Title',
        body: 'Text',
        emoji: 'Emoji',
        counter: '{{current}} / {{max}}',
        publish: 'Publish',
        publishing: 'Publishing…',
        published: 'Your post was published. Posts are ordered by value, so it appears among the others accordingly.',
        invalid: 'Check the title and the text – they cannot be empty or too long.',
        error: 'Could not publish the post.',
      },
      newCategory: {
        title: 'New category',
        name: 'Name',
        nameHint: "The category's address is generated from its name.",
        description: 'Short description',
        create: 'Create category',
        creating: 'Creating…',
        loginRequired: 'Sign in to create a category.',
        invalid: 'Check the name and the description – they cannot be empty or too long.',
        error: 'Could not create the category.',
      },
    },
  },
}

export default boardsModule
