import { createRouter, createWebHistory } from 'vue-router'

import { sessionStore } from '@/stores/session'
import { userStore } from '@/stores/user'

const routes = [
	{
		path: '/signup',
		name: 'SignUp',
		component: () => import('@/pages/SignupView.vue'),
		meta: { isLogin: true },
	},
	{
		path: '/signup/personal',
		name: 'PersonalSignUp',
		component: () => import('@/pages/SignupView.vue'),
		meta: { isLogin: true },
	},
	{
		path: '/signup/business',
		name: 'BusinessSignUp',
		component: () => import('@/pages/BusinessSignupView.vue'),
		meta: { isLogin: true },
	},
	{
		path: '/signup/business/:requestKey',
		name: 'BusinessSetup',
		component: () => import('@/pages/BusinessSignupView.vue'),
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
		path: '/setup',
		name: 'Setup',
		component: () => import('@/pages/SetupView.vue'),
		meta: { isSetup: true },
	},
	{
		path: '/mailbox/:mailbox',
		name: 'Mailbox',
		component: () => import('@/pages/MailboxView.vue'),
		props: true,
	},
	{
		path: '/mailbox/:mailbox/:threadID',
		name: 'Mail',
		component: () => import('@/pages/MailboxView.vue'),
		props: true,
	},
	{
		path: '/address-books/',
		name: 'AddressBooks',
		component: () => import('@/pages/AddressBooksView.vue'),
	},
	{
		path: '/address-books/:addressBookName',
		name: 'AddressBook',
		component: () => import('@/pages/AddressBookView.vue'),
		props: true,
	},
	{
		path: '/contacts/',
		name: 'Contacts',
		component: () => import('@/pages/ContactsView.vue'),
	},
	{
		path: '/contacts/:contactName',
		name: 'Contact',
		component: () => import('@/pages/ContactView.vue'),
		props: true,
	},
	{
		path: '/mail-data-exchanges',
		name: 'MailDataExchanges',
		component: () => import('@/pages/MailDataExchangesView.vue'),
		meta: { noLayout: true },
	},
	{
		path: '/mail-data-exchanges/:id',
		name: 'MailDataExchange',
		component: () => import('@/pages/MailDataExchangeView.vue'),
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
]

const router = createRouter({ history: createWebHistory('/mail'), routes })

router.beforeEach(async (to, _, next) => {
	if (document.referrer.includes('/app/setup-wizard')) window.location.replace('/app')

	const { isLoggedIn } = sessionStore()
	if (!isLoggedIn) return to.meta.isLogin ? next() : next({ name: 'Login' })

	const { userResource, mailboxes } = userStore()
	await userResource.promise
	await mailboxes.promise
	const user = userResource.data
	const mailboxRoute = { name: 'Mailbox', params: { mailbox: mailboxes.data?.[0]?.id } }

	if (user.is_mail_admin) {
		if (!user.tenant) return to.meta.isSetup ? next() : next({ name: 'Setup' })
		if (!user.is_mail_user && !to.meta.isDashboard) return next({ name: 'Domains' })
	} else if (to.meta.isDashboard) return next(mailboxRoute)

	if (['/', '/mailbox', '/mailbox/'].includes(to.path)) return next(mailboxRoute)

	return to.meta.isLogin || to.meta.isSetup ? next(mailboxRoute) : next()
})

export default router
