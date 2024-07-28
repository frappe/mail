<template>
    <div v-if="mail.data" class="p-5">
        <div class="flex space-x-4 border-b pb-5">
            <Avatar class="avatar border border-gray-300" :label="mail.data.display_name || mail.data.sender"
                :image="mail.data.user_image" size="lg" />
            <div class="text-sm space-y-2">
                <div class="text-base font-semibold">
                    {{ mail.data.display_name || mail.data.sender }}
                </div>
                <div class="leading-4">
                    {{ mail.data.subject }}
                </div>
                <div>
                    {{ __("To") }}: {{ mail.data.receiver }}
                </div>
            </div>
        </div>
        <div v-if="mail.data.body_html" v-html="mail.data.body_html"
            class="pt-5 ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-gray-300 prose-th:border-gray-300 prose-td:relative prose-th:relative prose-th:bg-gray-100 prose-sm max-w-none">
        </div>
    </div>
</template>
<script setup>
import { createResource, Avatar } from 'frappe-ui';
import { watch } from 'vue';

const props = defineProps({
    mailID: {
        type: String,
        required: true
    },
    type: {
        type: String,
        required: true
    }
});

const mail = createResource({
    url: "mail.api.mail.get_mail_details",
    makeParams(values) {
        return {
            name: values?.mailID || props.mailID,
            type: props.type
        }
    },
    auto: true,
});

watch(
    () => props.mailID,
    (newName) => {
        console.log(props.mailID)
        mail.reload({ mailID: newName })
    }
)
</script>