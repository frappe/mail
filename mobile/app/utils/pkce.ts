// PKCE (Proof Key for Code Exchange, RFC 7636) helpers for the OAuth2 login flow.
// NativeScript has no Web Crypto, so we source secure randomness from the platform
// (arc4random on iOS, SecureRandom on Android) and hash with an inlined pure-JS
// SHA-256 (js-sha256 pulls in Node.js 'crypto'/'buffer' which webpack 5 won't bundle).

import { isIOS } from '@nativescript/core'

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

// ---------------------------------------------------------------------------
// Pure-JS SHA-256 (FIPS 180-4). Operates on a UTF-8 string, returns bytes[].
// Source: compact adaptation of the public-domain SHA-256 spec — no Node APIs.
// ---------------------------------------------------------------------------
function sha256Bytes(msg: string): number[] {
	// Pre-process: UTF-8 encode
	const bytes: number[] = []
	for (let i = 0; i < msg.length; i++) {
		const c = msg.charCodeAt(i)
		if (c < 0x80) bytes.push(c)
		else if (c < 0x800) bytes.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f))
		else bytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f))
	}

	const K = [
		0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
		0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
		0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
		0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
		0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
		0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
		0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
		0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
		0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
		0xc67178f2,
	]

	const len = bytes.length
	bytes.push(0x80)
	while (bytes.length % 64 !== 56) bytes.push(0)
	const bitLen = len * 8
	for (let i = 7; i >= 0; i--) bytes.push((bitLen / Math.pow(2, i * 8)) & 0xff)

	let h0 = 0x6a09e667,
		h1 = 0xbb67ae85,
		h2 = 0x3c6ef372,
		h3 = 0xa54ff53a,
		h4 = 0x510e527f,
		h5 = 0x9b05688c,
		h6 = 0x1f83d9ab,
		h7 = 0x5be0cd19

	const rotr = (x: number, n: number) => ((x >>> n) | (x << (32 - n))) >>> 0

	for (let i = 0; i < bytes.length; i += 64) {
		const w: number[] = []
		for (let j = 0; j < 16; j++)
			w[j] =
				((bytes[i + j * 4] << 24) |
					(bytes[i + j * 4 + 1] << 16) |
					(bytes[i + j * 4 + 2] << 8) |
					bytes[i + j * 4 + 3]) >>>
				0
		for (let j = 16; j < 64; j++) {
			const s0 = (rotr(w[j - 15], 7) ^ rotr(w[j - 15], 18) ^ (w[j - 15] >>> 3)) >>> 0
			const s1 = (rotr(w[j - 2], 17) ^ rotr(w[j - 2], 19) ^ (w[j - 2] >>> 10)) >>> 0
			w[j] = (w[j - 16] + s0 + w[j - 7] + s1) >>> 0
		}
		let [a, b, c, d, e, f, g, h] = [h0, h1, h2, h3, h4, h5, h6, h7]
		for (let j = 0; j < 64; j++) {
			const S1 = (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) >>> 0
			const ch = ((e & f) ^ (~e & g)) >>> 0
			const temp1 = (h + S1 + ch + K[j] + w[j]) >>> 0
			const S0 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) >>> 0
			const maj = ((a & b) ^ (a & c) ^ (b & c)) >>> 0
			const temp2 = (S0 + maj) >>> 0
			;[h, g, f, e, d, c, b, a] = [
				g,
				f,
				e,
				(d + temp1) >>> 0,
				c,
				b,
				a,
				(temp1 + temp2) >>> 0,
			]
		}
		h0 = (h0 + a) >>> 0
		h1 = (h1 + b) >>> 0
		h2 = (h2 + c) >>> 0
		h3 = (h3 + d) >>> 0
		h4 = (h4 + e) >>> 0
		h5 = (h5 + f) >>> 0
		h6 = (h6 + g) >>> 0
		h7 = (h7 + h) >>> 0
	}

	const out: number[] = []
	for (const word of [h0, h1, h2, h3, h4, h5, h6, h7])
		for (let i = 3; i >= 0; i--) out.push((word >>> (i * 8)) & 0xff)
	return out
}

export function createPkcePair(): PkcePair {
	// 32 random bytes → 43-char base64url verifier (within the 43–128 spec range).
	const codeVerifier = base64UrlEncode(randomBytes(32))
	const codeChallenge = base64UrlEncode(sha256Bytes(codeVerifier))
	const state = base64UrlEncode(randomBytes(16))
	return { codeVerifier, codeChallenge, state }
}
