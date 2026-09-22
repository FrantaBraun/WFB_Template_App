/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { ModuleDefinition } from '../types'
import NotificationBell from './NotificationBell'

const notificationsModule: ModuleDefinition = {
  key: 'notifications',
  routes: [],
  headerWidget: <NotificationBell />,
  locales: {
    cs: {
      bell: {
        title: 'Oznámení',
        empty: 'Zatím žádná oznámení.',
      },
    },
    en: {
      bell: {
        title: 'Notifications',
        empty: 'No notifications yet.',
      },
    },
  },
}

export default notificationsModule
