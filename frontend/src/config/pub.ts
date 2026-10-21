/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

/**
 * The (made-up) facts about the pub that the pages show - one place, so a real
 * pub changes them here. Nothing below exists: the name, the address, the number,
 * the e-mail (an example.com address, which can never be delivered) and the company
 * are invented for this demo, and the site says so (footer, About page). The words
 * around them are in the locale files.
 */
export const PUB = {
  name: 'Hostinec U Zlatého chmele',
  street: 'Chmelařská 12',
  city: '438 01 Žatec',
  phone: '+420 123 456 789',
  phoneHref: 'tel:+420123456789',
  email: 'hostinec@example.com',
  operator: 'Chmelová hospoda s.r.o.',
  ico: '12345678',
  founded: 1894,
} as const
