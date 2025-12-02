<template>
	<Dialog v-model="show" :options="{ title: __('Edit Photo'), size: 'sm' }">
		<template #body-content>
			<FileUploader
				class="mb-2 w-full"
				:file-types="['image/*']"
				@success="(file) => setProfilePhoto.submit({ image: file.file_url })"
			>
				<template #default="{ error, uploading, openFileSelector }">
					<div class="flex flex-col items-center space-y-4">
						<div
							class="bg-surface-gray-2 flex h-64 w-64 items-center justify-center rounded-full"
						>
							<img
								v-if="user.data?.user_image"
								:src="user.data?.user_image"
								class="h-full w-full rounded-full object-cover"
							/>
							<User v-else class="text-ink-gray-4 h-40 w-40 stroke-1" />
						</div>
						<ErrorMessage :message="error" />
						<Button
							:label="__('Upload New Photo')"
							variant="solid"
							class="w-full"
							:disabled="uploading || setProfilePhoto.loading"
							@click="openFileSelector"
						/>
						<Button
							v-if="user.data?.user_image"
							:label="__('Remove Current Photo')"
							class="w-full"
							:disabled="uploading || setProfilePhoto.loading"
							@click="() => setProfilePhoto.submit({ image: null })"
						/>
					</div>
				</template>
			</FileUploader>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { User } from 'lucide-vue-next'
import { Button, Dialog, ErrorMessage, FileUploader, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'

const show = defineModel<boolean>()

const user = inject('$user')

const setProfilePhoto = createResource({
	url: 'frappe.client.set_value',
	makeParams: ({ image }: { image: string | null }) => ({
		doctype: 'User',
		name: user.data?.name,
		fieldname: 'user_image',
		value: image,
	}),
	onSuccess: () => {
		raiseToast(__('Profile photo updated.'))
		user.reload()
	},
})
</script>
