/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { cs } from './cs'
import { en } from './en'
import { legalCs } from './legalCs'
import { legalEn } from './legalEn'

/** The page texts with the legal pages' sections folded into `legal.<page>.sections`. */
function withSections<T extends typeof cs>(texts: T, sections: typeof legalCs) {
  return {
    ...texts,
    legal: {
      ...texts.legal,
      privacy: { ...texts.legal.privacy, sections: sections.privacy },
      terms: { ...texts.legal.terms, sections: sections.terms },
      cookies: { ...texts.legal.cookies, sections: sections.cookies },
    },
  }
}

export const csBundle = withSections(cs, legalCs)
export const enBundle = withSections(en, legalEn)
