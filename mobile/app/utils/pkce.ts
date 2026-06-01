// PKCE (Proof Key for Code Exchange, RFC 7636) helpers for the OAuth2 login flow.
// NativeScript has no Web Crypto, so we source secure randomness from the platform
// (arc4random on iOS, SecureRandom on Android) and hash with js-sha256.

import { isIOS } from '@nativescript/core'
import { sha256 } from 'js-sha256'

// libSystem CSPRNG, available in the iOS runtime but absent from @nativescript/types.
declare function arc4random_uniform(upperBound: number): number

// Unreserved base64url alphabet (RFC 4648 §5), no padding.
const B64URL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'

function randomBytes(length: number): number[] {
	const out: number[] = []
	if (isIOS) {
		// arc4random_uniform is a CSPRNG available in the iOS runtime.
		for (let i = 0; i < length; i++) out.push(arc4random_uniform(256))
	} else {
		const secureRandom = new java.security.SecureRandom()
		const buffer = Array.create('byte', length)
		secureRandom.nextBytes(buffer)
		for (let i = 0; i < length; i++) out.push(buffer[i] & 0xff)
	}
	return out
}

function base64UrlEncode(bytes: number[]): string {
	let out = ''
	for (let i = 0; i < bytes.length; i += 3) {
		const b0 = bytes[i]
		const b1 = i + 1 < bytes.length ? bytes[i + 1] : -1
		const b2 = i + 2 < bytes.length ? bytes[i + 2] : -1
		out += B64URL[b0 >> 2]
		out += B64URL[((b0 & 3) << 4) | ((b1 < 0 ? 0 : b1) >> 4)]
		if (b1 < 0) break
		out += B64URL[((b1 & 15) << 2) | ((b2 < 0 ? 0 : b2) >> 6)]
		if (b2 < 0) break
		out += B64URL[b2 & 63]
	}
	return out
}

export interface PkcePair {
	/** Secret kept on device; sent during the token exchange. */
	codeVerifier: string
	/** SHA-256(codeVerifier), sent in the authorize request. */
	codeChallenge: string
	/** Opaque value echoed back on redirect to guard against CSRF. */
	state: string
}

export function createPkcePair(): PkcePair {
	// 32 random bytes → 43-char base64url verifier (within the 43–128 spec range).
	const codeVerifier = base64UrlEncode(randomBytes(32))
	const codeChallenge = base64UrlEncode(sha256.array(codeVerifier))
	const state = base64UrlEncode(randomBytes(16))
	return { codeVerifier, codeChallenge, state }
}
