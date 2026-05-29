import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { ApplicationSettings } from '@nativescript/core'

import type { SiteInfo } from '@mail/types'

const SITES_KEY = 'mail-sites'
const ACTIVE_SITE_KEY = 'mail-active-site'

function loadSites(): SiteInfo[] {
	try {
		const raw = ApplicationSettings.getString(SITES_KEY, '[]')
		return JSON.parse(raw) as SiteInfo[]
	} catch {
		return []
	}
}

export const siteStore = defineStore('mail-site', () => {
	const sites = ref<SiteInfo[]>(loadSites())
	const activeSiteUrl = ref<string>(ApplicationSettings.getString(ACTIVE_SITE_KEY, ''))

	const activeSite = computed(
		() => sites.value.find((s) => s.url === activeSiteUrl.value) ?? null,
	)

	function addSite(info: SiteInfo) {
		if (!sites.value.some((s) => s.url === info.url)) {
			sites.value.push(info)
			persist()
		}
		setActiveSite(info.url)
	}

	function removeSite(url: string) {
		sites.value = sites.value.filter((s) => s.url !== url)
		persist()
		if (activeSiteUrl.value === url) {
			setActiveSite(sites.value[0]?.url ?? '')
		}
	}

	function setActiveSite(url: string) {
		activeSiteUrl.value = url
		ApplicationSettings.setString(ACTIVE_SITE_KEY, url)
	}

	function persist() {
		ApplicationSettings.setString(SITES_KEY, JSON.stringify(sites.value))
	}

	return { sites, activeSiteUrl, activeSite, addSite, removeSite, setActiveSite }
})
