import md5 from 'blueimp-md5'

// Gravatar URL for an email, hashed per the Gravatar spec (trimmed + lowercased
// md5). `d=404` makes Gravatar return 404 when the email has no real avatar, so
// callers can fall back to initials instead of a default image. We hit Gravatar
// directly from the client so the backend needs no guest-accessible endpoint.
export function gravatarUrl(email: string, size = 256): string {
	const hash = md5(email.trim().toLowerCase())
	return `https://secure.gravatar.com/avatar/${hash}?d=404&s=${size}`
}

// Pulls the raw email out of a get_avatar API URL (…/get_avatar?email=foo@bar.com).
export function emailFromAvatarUrl(url: string): string {
	const match = url.match(/[?&]email=([^&]+)/i)
	return match ? decodeURIComponent(match[1]) : ''
}
