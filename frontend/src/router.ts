import { createRouter, createWebHistory } from 'vue-router'

import { sessionStore } from '@/stores/session'
import { userStore } from '@/stores/user'

import type { UserAccount } from './types'

// Lightweight placeholder used by shortcut routes — the beforeEach guard
// intercepts them and redirects before any component ever mounts.
const ShortcutRedirect = { render: () => null }

const routes = [
	{
		path: '/signup',
		name: 'SignUp',
		component: () => import('@/pages/SignupView.vue'),
		meta: { isLogin: true },
	},
	{
		path: '/signup/:requestKey',
		name: 'InviteSetup',
		component: () => import('@/pages/InviteSetupView.vue'),
		props: true,
		meta: { isLogin: true },
	},
	{
		path: '/login',
		name: 'Login',
		component: () => import('@/pages/LoginView.vue'),
		meta: { isLogin: true },
	},
	{
		path: '/reset-password',
		name: 'ForgotPassword',
		component: () => import('@/pages/ForgotPasswordView.vue'),
		meta: { isLogin: true },
	},
	{
		path: '/reset-password/:requestKey',
		name: 'ResetPassword',
		component: () => import('@/pages/ResetPasswordView.vue'),
		props: true,
		meta: { isLogin: true },
	},
	{
		path: '/account/:accountId/mailbox/:mailbox',
		name: 'Mailbox',
		component: () => import('@/pages/MailboxView.vue'),
		props: true,
	},
	{
		path: '/account/:accountId/mailbox/:mailbox/:threadID',
		name: 'Mail',
		component: () => import('@/pages/MailboxView.vue'),
		props: true,
	},
	{
		path: '/account/:accountId/address-books/',
		name: 'AddressBooks',
		component: () => import('@/pages/AddressBooksView.vue'),
		props: true,
	},
	{
		path: '/account/:accountId/address-books/:addressBookName',
		name: 'AddressBook',
		component: () => import('@/pages/AddressBookView.vue'),
		props: true,
	},
	{
		path: '/account/:accountId/contacts/',
		name: 'Contacts',
		component: () => import('@/pages/ContactsView.vue'),
		props: true,
	},
	{
		path: '/account/:accountId/contacts/:contactName',
		name: 'Contact',
		component: () => import('@/pages/ContactView.vue'),
		props: true,
	},
	{
		path: '/mail-exchanges',
		name: 'MailExchanges',
		component: () => import('@/pages/MailExchangesView.vue'),
		meta: { noLayout: true },
	},
	{
		path: '/mail-exchanges/:id',
		name: 'MailExchange',
		component: () => import('@/pages/MailExchangeView.vue'),
		meta: { noLayout: true },
		props: true,
	},
	{
		path: '/mime-message/:id',
		name: 'MimeMessage',
		component: () => import('@/pages/MimeMessageView.vue'),
		props: true,
		meta: { noLayout: true },
	},
	{
		path: '/dashboard',
		redirect: { name: 'Domains' },
		meta: { isDashboard: true },
	},
	{
		path: '/dashboard/domains',
		name: 'Domains',
		component: () => import('@/pages/dashboard/DomainsView.vue'),
		meta: { isDashboard: true },
	},
	{
		path: '/dashboard/domains/:domainName',
		name: 'Domain',
		component: () => import('@/pages/dashboard/DomainView.vue'),
		props: true,
		meta: { isDashboard: true },
	},
	{
		path: '/dashboard/members',
		name: 'Members',
		component: () => import('@/pages/dashboard/MembersView.vue'),
		meta: { isDashboard: true },
	},
	{
		path: '/dashboard/members/:memberName',
		name: 'Member',
		component: () => import('@/pages/dashboard/MemberView.vue'),
		props: true,
		meta: { isDashboard: true },
	},
	{
		path: '/dashboard/invites',
		name: 'Invites',
		component: () => import('@/pages/dashboard/MembersView.vue'),
		meta: { isDashboard: true },
	},
	{
		path: '/dashboard/mailing-lists',
		name: 'MailingLists',
		component: () => import('@/pages/dashboard/MailingListsView.vue'),
		meta: { isDashboard: true },
	},
	{
		path: '/dashboard/mailing-lists/:listName',
		name: 'MailingList',
		component: () => import('@/pages/dashboard/MailingListView.vue'),
		props: true,
		meta: { isDashboard: true },
	},
	// Shortcut routes: short paths that resolve to their full account-scoped
	// equivalents once the active accountId is known (resolved in beforeEach).
	{
		path: '/',
		name: 'RootShortcut',
		component: ShortcutRedirect,
		meta: { shortcut: true },
	},
	{
		path: '/account/:accountId?',
		name: 'AccountShortcut',
		component: ShortcutRedirect,
		meta: { shortcut: true },
	},
	{
		path: '/mailbox/:mailbox?/:threadID?',
		name: 'MailboxShortcut',
		component: ShortcutRedirect,
		meta: { shortcut: true },
	},
	{
		path: '/address-books/:addressBookName?',
		name: 'AddressBooksShortcut',
		component: ShortcutRedirect,
		meta: { shortcut: true },
	},
	{
		path: '/contacts/:contactName?',
		name: 'ContactsShortcut',
		component: ShortcutRedirect,
		meta: { shortcut: true },
	},
]

const router = createRouter({ history: createWebHistory('/mail'), routes })

// ---------------------------------------------------------------------------
// Guard helpers
// ---------------------------------------------------------------------------

const handleSetupWizardEscape = () => {
	if (document.referrer.includes('/app/setup-wizard')) window.location.replace('/app')
}

const getPersonalAccountId = (user: { accounts?: UserAccount[] }) =>
	user.accounts?.find((a) => a.is_personal)?.id

const resolveAccount = (
	routeAccountId: string | undefined,
	user: { accounts?: UserAccount[] },
	storeAccountId: string,
	setAccount: (id: string) => void,
) => {
	if (routeAccountId) {
		const isValid = user.accounts?.some((a) => a.id === routeAccountId)
		if (isValid) {
			if (routeAccountId !== storeAccountId) setAccount(routeAccountId)
			return
		}
	}

	if (!storeAccountId) {
		const personalId = getPersonalAccountId(user)
		if (personalId) setAccount(personalId)
	}
}

const buildDefaultRoute = (
	accountId: string,
	mailboxes: { data?: { id: string }[] },
): { name: string; params: Record<string, string> } => {
	const firstMailbox = mailboxes.data?.[0]?.id
	if (firstMailbox) return { name: 'Mailbox', params: { accountId, mailbox: firstMailbox } }

	return { name: 'AddressBooks', params: { accountId } }
}

const resolveShortcut = (
	name: string | symbol | null | undefined,
	params: Record<string, string | string[]>,
	accountId: string,
	defaultRoute: { name: string; params: Record<string, string> },
) => {
	switch (name) {
		case 'MailboxShortcut':
			if (params.threadID) return { name: 'Mail', params: { accountId, ...params } }
			if (params.mailbox) return { name: 'Mailbox', params: { accountId, ...params } }
			return defaultRoute
		case 'AddressBooksShortcut':
			if (params.addressBookName)
				return { name: 'AddressBook', params: { accountId, ...params } }
			return { name: 'AddressBooks', params: { accountId } }
		case 'ContactsShortcut':
			if (params.contactName) return { name: 'Contact', params: { accountId, ...params } }
			return { name: 'Contacts', params: { accountId } }
		default:
			return defaultRoute
	}
}

// ---------------------------------------------------------------------------
// Navigation guard
// ---------------------------------------------------------------------------

router.beforeEach(async (to, _, next) => {
	handleSetupWizardEscape()

	// 1. Authentication check
	const { isLoggedIn } = sessionStore()
	if (!isLoggedIn) return to.meta.isLogin ? next() : next({ name: 'Login' })

	// 2. Wait for user data
	const { userResource, mailboxes, setAccount } = userStore()
	await userResource.promise
	const user = userResource.data

	// Re-read accountId after resolveAccount may have updated it via setAccount
	const accountId = userStore().accountId

	// 3. Resolve active account (use current store value, not the pre-await snapshot)
	resolveAccount(to.params.accountId as string | undefined, user, accountId, setAccount)

	// 4. Fetch and wait for mailbox list
	if (!mailboxes.promise) mailboxes.fetch()
	await mailboxes.promise
	const defaultRoute = buildDefaultRoute(accountId, mailboxes)

	// 5. Validate mailbox param for mailbox routes
	if (to.name === 'Mailbox' || to.name === 'Mail') {
		const mailboxExists =
			mailboxes.data?.some((m: { id: string }) => m.id === to.params.mailbox) ||
			['starred', 'search'].includes(to.params.mailbox)
		if (!mailboxExists) return next(defaultRoute)
	}

	// 6. Expand shortcut routes to their full account-scoped equivalents
	if (to.meta.shortcut) return next(resolveShortcut(to.name, to.params, accountId, defaultRoute))

	// 7. Admin / dashboard access control
	if (user.is_mail_admin) {
		if (!user.is_jmap_configured && !to.meta.isDashboard) return next({ name: 'Domains' })
	} else if (to.meta.isDashboard) return next(defaultRoute)

	// 8. Login pages redirect already-authenticated users to their mailbox
	return to.meta.isLogin ? next(defaultRoute) : next()
})

export default router
