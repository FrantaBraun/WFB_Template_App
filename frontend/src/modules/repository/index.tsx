/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Repository: everyone who is signed in builds their own databases. A
// repository holds tables (object types) with attributes the user defines,
// and records in them; everything is private to its owner.
//
//   /repository/new                                 a new repository
//   /repository/:repo/*                             RepositoryArea: loads the repository, tints the page
//                                                   with its colour scheme, shows its tables as a side
//                                                   menu and routes (see RepositoryArea.tsx) to:
//       (index)                                     the repository: its tables, edit, delete
//       tables                                      manage the tables
//       table/new, table/:table/edit                the definition of a table
//       table/:table                                the content of a table
//       table/:table/item/new|:item|:item/edit      a record
//
// There is no `nav` entry: the home page of the application shows the user's
// repositories (RepositoryList, exported for it). `:repo` and `:table` are
// slugs; `new`, `edit` and `tables` are reserved so they cannot collide.
import type { ModuleDefinition } from '../types'
import { cs, en } from './locales'
import RepositoryArea from './RepositoryArea'
import RepositoryFormPage from './RepositoryFormPage'

const repositoryModule: ModuleDefinition = {
  key: 'repository',
  routes: [
    { path: '/repository/new', element: <RepositoryFormPage /> },
    { path: '/repository/:repo/*', element: <RepositoryArea /> },
  ],
  locales: { cs, en },
}

export { default as RepositoryList } from './RepositoryList'

export default repositoryModule
