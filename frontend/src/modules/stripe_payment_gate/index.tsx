/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// No nav entry: payments are always started from application code (via
// PayButton or startCheckout() from ./checkout), never from a standalone
// page - the only route is the return page Stripe redirects back to.
import type { ModuleDefinition } from '../types'
import PaymentResultPage from './PaymentResultPage'

const stripePaymentGateModule: ModuleDefinition = {
  key: 'stripe_payment_gate',
  routes: [{ path: '/platba/vysledek', element: <PaymentResultPage /> }],
  locales: {
    cs: {
      button: {
        pay: 'Zaplatit',
        redirecting: 'Přesměrování na platební bránu…',
        error: 'Platbu se nepodařilo zahájit. Zkuste to prosím znovu.',
        signInRequired: 'Pro zaplacení se nejprve přihlaste.',
      },
      result: {
        title: 'Výsledek platby',
        loading: 'Ověřujeme platbu…',
        paidTitle: 'Platba proběhla úspěšně',
        paidMessage: 'Děkujeme, platbu jsme přijali.',
        pendingTitle: 'Čekáme na potvrzení platby…',
        pendingMessage: 'Platební brána platbu ještě potvrzuje, chvíli strpení.',
        stillPendingTitle: 'Platba zatím nebyla potvrzena',
        stillPendingMessage: 'Potvrzení může trvat déle (např. u bankovního převodu). Stav můžete ověřit znovu později.',
        canceledTitle: 'Platba byla zrušena',
        canceledMessage: 'Nic jsme vám nestrhli. Platbu můžete kdykoli zopakovat.',
        failedTitle: 'Platba se nezdařila',
        failedMessage: 'Platební brána platbu odmítla. Zkuste to prosím znovu, případně jiným způsobem platby.',
        expiredTitle: 'Platba vypršela',
        expiredMessage: 'Platební relace vypršela dřív, než byla dokončena. Zahajte prosím platbu znovu.',
        notFoundTitle: 'Platba nenalezena',
        notFoundMessage: 'Tuto platbu jsme nenašli. Pokud jste ji zahájili po přihlášení, přihlaste se stejným účtem.',
        errorTitle: 'Stav platby se nepodařilo načíst',
        errorMessage: 'Zkuste to prosím za chvíli znovu.',
        description: 'Položka',
        amount: 'Částka',
        retry: 'Ověřit znovu',
        continue: 'Pokračovat',
        backHome: 'Zpět na hlavní stránku',
      },
    },
    en: {
      button: {
        pay: 'Pay',
        redirecting: 'Redirecting to the payment gateway…',
        error: 'Could not start the payment. Please try again.',
        signInRequired: 'Please sign in to pay.',
      },
      result: {
        title: 'Payment result',
        loading: 'Checking your payment…',
        paidTitle: 'Payment successful',
        paidMessage: "Thank you, we've received your payment.",
        pendingTitle: 'Waiting for payment confirmation…',
        pendingMessage: 'The payment gateway is still confirming your payment, please wait a moment.',
        stillPendingTitle: 'Payment not confirmed yet',
        stillPendingMessage: 'Confirmation can take longer (e.g. for bank transfers). You can check the status again later.',
        canceledTitle: 'Payment canceled',
        canceledMessage: "You haven't been charged. You can retry the payment at any time.",
        failedTitle: 'Payment failed',
        failedMessage: 'The payment gateway declined the payment. Please try again or use a different payment method.',
        expiredTitle: 'Payment expired',
        expiredMessage: 'The payment session expired before it was completed. Please start the payment again.',
        notFoundTitle: 'Payment not found',
        notFoundMessage: "We couldn't find this payment. If you started it while signed in, sign in with the same account.",
        errorTitle: 'Could not load payment status',
        errorMessage: 'Please try again in a moment.',
        description: 'Item',
        amount: 'Amount',
        retry: 'Check again',
        continue: 'Continue',
        backHome: 'Back to homepage',
      },
    },
  },
}

export default stripePaymentGateModule
