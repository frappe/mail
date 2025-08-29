<template>
	<h1>{{ __('API Access') }}</h1>
	<CopyControl v-if="user.data?.api_key" :label="__('API Key')" :value="user.data?.api_key" />
	<p v-else class="text-base">
		{{ __(`You don't have an API key yet. Generate one to access the API.`) }}
	</p>
	<Button
		class="min-h-7"
		:label="user.data?.api_key ? __('Regenerate Secret') : __('Generate Keys')"
		@click="generateKeys.submit()"
	/>

	<Dialog v-model="showSecret" :options="{ title: __('API Access') }">
		<template #body-content>
			<p class="text-base">
				{{ __(`Please copy the API secret now. You won’t be able to see it again!`) }}
			</p>
			<CopyControl :label="__('API Key')" :value="user.data?.api_key" />
			<CopyControl :label="__('API Secret')" :value="apiSecret" />
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { inject, ref } from 'vue'
import { Button, Dialog, createResource } from 'frappe-ui'

import CopyControl from '@/components/Controls/CopyControl.vue'

const user = inject('$user')

const showSecret = ref(false)
const apiSecret = ref('')

const generateKeys = createResource({
	url: 'mail.utils.user.generate_user_keys',
	makeParams: () => ({ user: user.data?.name }),
	onSuccess: (data) => {
		if (!user.data?.api_key) user.reload()
		apiSecret.value = data.api_secret
		showSecret.value = true
	},
})
</script>
