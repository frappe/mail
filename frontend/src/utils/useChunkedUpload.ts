import { ref } from 'vue'

// Chunked file upload, ported from frappe-ui PR #788 (not yet merged) and matching the framework's
// chunked `upload_file` handler (frappe PR #37888). Large files are sent in sequential chunks so the
// upload isn't capped by the web server's request-body limit — needed for big mail-import archives.

export interface UploadedFile {
	name: string
	file_name: string
	file_url: string
	is_private: 0 | 1
	[key: string]: unknown
}

export interface ChunkedUploadOptions {
	private?: boolean
	folder?: string
	doctype?: string
	docname?: string
	fieldname?: string
	method?: string
	type?: string
	file_url?: string
	upload_endpoint?: string
	chunk_size?: number
}

// Default chunk size; stays under the framework's 25 MB default so each request clears the usual web
// server body limit. Callers can override via options.chunk_size.
const DEFAULT_CHUNK_SIZE = 24 * 1024 * 1024

export function useChunkedUpload() {
	const uploading = ref(false)
	const progress = ref(0)

	const upload = (file: File, options: ChunkedUploadOptions = {}): Promise<UploadedFile> => {
		const chunkSize = options.chunk_size || DEFAULT_CHUNK_SIZE
		const totalChunks = Math.max(1, Math.ceil(file.size / chunkSize))
		const endpoint = options.upload_endpoint || '/api/method/mail.api.mail.upload_file'

		const buildFormData = (chunk: Blob, chunkIndex: number, chunkByteOffset: number) => {
			const form = new FormData()
			form.append('file', chunk, file.name)
			form.append('is_private', options.private ? '1' : '0')
			form.append('folder', options.folder || 'Home')
			form.append('total_file_size', String(file.size))
			form.append('chunk_index', String(chunkIndex))
			form.append('total_chunk_count', String(totalChunks))
			form.append('chunk_byte_offset', String(chunkByteOffset))
			if (options.file_url) form.append('file_url', options.file_url)
			if (options.doctype) form.append('doctype', options.doctype)
			if (options.docname) form.append('docname', options.docname)
			if (options.fieldname) form.append('fieldname', options.fieldname)
			if (options.method) form.append('method', options.method)
			if (options.type) form.append('type', options.type)
			return form
		}

		const sendChunk = (chunkIndex: number, chunkByteOffset: number): Promise<UploadedFile> =>
			new Promise((resolve, reject) => {
				const xhr = new XMLHttpRequest()

				xhr.upload.addEventListener('progress', (e) => {
					if (!e.lengthComputable) return
					progress.value = Math.round(((chunkByteOffset + e.loaded) / file.size) * 100)
				})

				xhr.addEventListener('error', () => reject(new Error(__('Upload failed.'))))

				xhr.onreadystatechange = () => {
					if (xhr.readyState !== XMLHttpRequest.DONE) return
					if (xhr.status === 200) {
						// Only the final chunk's response carries the created File document.
						if (chunkIndex === totalChunks - 1) {
							let r
							try {
								r = JSON.parse(xhr.responseText)
							} catch {
								r = xhr.responseText
							}
							resolve((r?.message || r) as UploadedFile)
						} else {
							sendChunk(chunkIndex + 1, chunkByteOffset + chunkSize)
								.then(resolve)
								.catch(reject)
						}
					} else {
						let message = __('Upload failed.')
						if (xhr.status === 413) message = __('File is too large to upload.')
						else {
							try {
								const err = JSON.parse(xhr.responseText)
								message = JSON.parse(err._server_messages || '[]')[0]
									? JSON.parse(JSON.parse(err._server_messages)[0]).message
									: err.message || message
							} catch {
								// keep default message
							}
						}
						reject(new Error(message))
					}
				}

				xhr.open('POST', endpoint, true)
				xhr.setRequestHeader('Accept', 'application/json')
				if (window.csrf_token && window.csrf_token !== '{{ csrf_token }}')
					xhr.setRequestHeader('X-Frappe-CSRF-Token', window.csrf_token)
				xhr.send(
					buildFormData(
						file.slice(chunkByteOffset, chunkByteOffset + chunkSize),
						chunkIndex,
						chunkByteOffset,
					),
				)
			})

		uploading.value = true
		progress.value = 0
		return sendChunk(0, 0).finally(() => (uploading.value = false))
	}

	return { uploading, progress, upload }
}
