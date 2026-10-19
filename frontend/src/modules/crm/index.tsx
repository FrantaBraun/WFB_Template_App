/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// CRM (administrators only): /crm lists partners, /crm/partners/:partnerId
// shows one partner with their tasks, /crm/tasks/:taskId shows a task with
// its invoice PDFs. There is no `nav` entry (that would show to every
// visitor): the header shows a link icon to administrators only, as a
// headerWidget. Every page is wrapped in CrmGate, and the backend checks
// User.is_admin on every request regardless.
import type { ModuleDefinition } from '../types'
import CrmNavLink from './CrmNavLink'
import PartnerFormPage from './PartnerFormPage'
import PartnerPage from './PartnerPage'
import PartnersPage from './PartnersPage'
import TaskFormPage from './TaskFormPage'
import TaskPage from './TaskPage'

const crmModule: ModuleDefinition = {
  key: 'crm',
  routes: [
    { path: '/crm', element: <PartnersPage /> },
    { path: '/crm/partners/new', element: <PartnerFormPage /> },
    { path: '/crm/partners/:partnerId', element: <PartnerPage /> },
    { path: '/crm/partners/:partnerId/edit', element: <PartnerFormPage /> },
    { path: '/crm/partners/:partnerId/tasks/new', element: <TaskFormPage /> },
    { path: '/crm/tasks/:taskId', element: <TaskPage /> },
    { path: '/crm/tasks/:taskId/edit', element: <TaskFormPage /> },
  ],
  headerWidget: <CrmNavLink />,
  locales: {
    cs: {
      nav: { crm: 'Partneři a zakázky' },
      common: {
        loading: 'Načítání…',
        forbidden: 'Tato část je jen pro administrátora.',
        back: 'Zpět',
        edit: 'Upravit',
        delete: 'Smazat',
        save: 'Uložit',
        saving: 'Ukládání…',
      },
      status: {
        new: 'Nová',
        in_progress: 'Rozpracovaná',
        done: 'Hotová',
        invoiced: 'Vyfakturovaná',
        paid: 'Zaplacená',
        cancelled: 'Zrušená',
      },
      partners: {
        title: 'Partneři',
        new: 'Nový partner',
        search: 'Hledat (jméno, firma, e-mail, IČO)',
        showArchived: 'Zobrazit archivované',
        archived: 'Archivován',
        empty: 'Zatím žádní partneři.',
        emptyFiltered: 'Nic nenalezeno.',
        loadError: 'Partnery se nepodařilo načíst.',
        taskCount_one: '{{count}} zakázka',
        taskCount_few: '{{count}} zakázky',
        taskCount_many: '{{count}} zakázky',
        taskCount_other: '{{count}} zakázek',
      },
      partner: {
        backToList: 'Všichni partneři',
        notFound: 'Partner nebyl nalezen.',
        loadError: 'Partnera se nepodařilo načíst.',
        archive: 'Archivovat',
        restore: 'Obnovit',
        confirmDelete: 'Opravdu smazat tohoto partnera?',
        deleteBlocked: 'Partner má zakázky, nelze ho smazat. Archivujte ho.',
        actionError: 'Akci se nepodařilo provést.',
        fields: {
          name: 'Jméno',
          company: 'Firma',
          companyId: 'IČO',
          vatId: 'DIČ',
          email: 'E-mail',
          phone: 'Telefon',
          address: 'Adresa',
          notes: 'Poznámky',
        },
        form: {
          newTitle: 'Nový partner',
          editTitle: 'Upravit partnera',
          invalid: 'Některý údaj není platný, zkontrolujte například e-mail.',
          saveError: 'Partnera se nepodařilo uložit.',
        },
      },
      tasks: {
        title: 'Zakázky',
        new: 'Nová zakázka',
        empty: 'Zatím žádné zakázky.',
        dueOn: 'termín {{date}}',
        invoiceCount_one: '{{count}} faktura',
        invoiceCount_few: '{{count}} faktury',
        invoiceCount_many: '{{count}} faktury',
        invoiceCount_other: '{{count}} faktur',
      },
      task: {
        notFound: 'Zakázka nebyla nalezena.',
        loadError: 'Zakázku se nepodařilo načíst.',
        confirmDelete: 'Opravdu smazat tuto zakázku?',
        deleteBlocked: 'Zakázka má faktury, nelze ji smazat. Nejdřív smažte faktury, nebo zakázku zrušte.',
        actionError: 'Akci se nepodařilo provést.',
        fields: {
          title: 'Název',
          description: 'Popis',
          status: 'Stav',
          price: 'Cena',
          currency: 'Měna',
          startDate: 'Začátek',
          dueDate: 'Termín',
        },
        form: {
          newTitle: 'Nová zakázka',
          editTitle: 'Upravit zakázku',
          invalid: 'Některý údaj není platný, zkontrolujte například cenu a data.',
          saveError: 'Zakázku se nepodařilo uložit.',
        },
      },
      invoices: {
        title: 'Faktury',
        empty: 'K této zakázce zatím nejsou žádné faktury.',
        numberShort: 'č. {{number}}',
        uploadedOn: 'nahráno {{date}}',
        download: 'Stáhnout',
        confirmDelete: 'Opravdu smazat fakturu {{name}}?',
        uploadTitle: 'Nahrát fakturu',
        file: 'Soubor PDF',
        number: 'Číslo faktury (nepovinné)',
        hint: 'Pouze PDF, nejvýše 10 MB.',
        upload: 'Nahrát',
        uploading: 'Nahrávání…',
        errors: {
          type: 'Nahrát lze jen soubor PDF.',
          size: 'Soubor je příliš velký (nejvýše 10 MB).',
          invalid: 'Soubor je prázdný nebo neplatný.',
          upload: 'Fakturu se nepodařilo nahrát.',
          download: 'Fakturu se nepodařilo stáhnout.',
          delete: 'Fakturu se nepodařilo smazat.',
        },
      },
    },
    en: {
      nav: { crm: 'Partners & tasks' },
      common: {
        loading: 'Loading…',
        forbidden: 'This area is for the administrator only.',
        back: 'Back',
        edit: 'Edit',
        delete: 'Delete',
        save: 'Save',
        saving: 'Saving…',
      },
      status: {
        new: 'New',
        in_progress: 'In progress',
        done: 'Done',
        invoiced: 'Invoiced',
        paid: 'Paid',
        cancelled: 'Cancelled',
      },
      partners: {
        title: 'Partners',
        new: 'New partner',
        search: 'Search (name, company, e-mail, ID)',
        showArchived: 'Show archived',
        archived: 'Archived',
        empty: 'No partners yet.',
        emptyFiltered: 'Nothing found.',
        loadError: 'Could not load the partners.',
        taskCount_one: '{{count}} task',
        taskCount_other: '{{count}} tasks',
      },
      partner: {
        backToList: 'All partners',
        notFound: 'Partner not found.',
        loadError: 'Could not load the partner.',
        archive: 'Archive',
        restore: 'Restore',
        confirmDelete: 'Really delete this partner?',
        deleteBlocked: 'This partner has tasks and cannot be deleted. Archive it instead.',
        actionError: 'The action failed.',
        fields: {
          name: 'Name',
          company: 'Company',
          companyId: 'Company ID',
          vatId: 'VAT ID',
          email: 'E-mail',
          phone: 'Phone',
          address: 'Address',
          notes: 'Notes',
        },
        form: {
          newTitle: 'New partner',
          editTitle: 'Edit partner',
          invalid: 'Some value is not valid - check the e-mail address, for example.',
          saveError: 'Could not save the partner.',
        },
      },
      tasks: {
        title: 'Tasks',
        new: 'New task',
        empty: 'No tasks yet.',
        dueOn: 'due {{date}}',
        invoiceCount_one: '{{count}} invoice',
        invoiceCount_other: '{{count}} invoices',
      },
      task: {
        notFound: 'Task not found.',
        loadError: 'Could not load the task.',
        confirmDelete: 'Really delete this task?',
        deleteBlocked: 'This task has invoices and cannot be deleted. Delete the invoices first, or cancel the task.',
        actionError: 'The action failed.',
        fields: {
          title: 'Title',
          description: 'Description',
          status: 'Status',
          price: 'Price',
          currency: 'Currency',
          startDate: 'Start',
          dueDate: 'Due date',
        },
        form: {
          newTitle: 'New task',
          editTitle: 'Edit task',
          invalid: 'Some value is not valid - check the price and the dates, for example.',
          saveError: 'Could not save the task.',
        },
      },
      invoices: {
        title: 'Invoices',
        empty: 'No invoices for this task yet.',
        numberShort: 'No. {{number}}',
        uploadedOn: 'uploaded {{date}}',
        download: 'Download',
        confirmDelete: 'Really delete the invoice {{name}}?',
        uploadTitle: 'Upload an invoice',
        file: 'PDF file',
        number: 'Invoice number (optional)',
        hint: 'PDF only, up to 10 MB.',
        upload: 'Upload',
        uploading: 'Uploading…',
        errors: {
          type: 'Only PDF files can be uploaded.',
          size: 'The file is too large (10 MB at most).',
          invalid: 'The file is empty or invalid.',
          upload: 'Could not upload the invoice.',
          download: 'Could not download the invoice.',
          delete: 'Could not delete the invoice.',
        },
      },
    },
  },
}

export default crmModule
