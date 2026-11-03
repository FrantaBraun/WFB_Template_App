/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import LegalShell, { Sections, useSections } from '../components/LegalShell'

/**
 * Terms of use (/terms): the service, accounts, content and permissions, the
 * rules of use, the limits of what the alerts and comparisons promise,
 * liability and termination. The provider named in them comes from
 * public/legal.json; the texts are the `legal` locales' `terms.*`.
 */
export default function Terms() {
  return <LegalShell page="terms">{(_, vars) => <TermsBody vars={vars} />}</LegalShell>
}

function TermsBody({ vars }: { vars: Record<string, string> }) {
  return <Sections sections={useSections('terms.sections', vars)} />
}
