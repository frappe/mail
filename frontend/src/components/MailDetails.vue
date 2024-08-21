<template>
    <div v-if="mail.data" class="p-3">
        <div class="flex space-x-3 border-b pb-2">
            <Avatar class="avatar border border-gray-300" :label="mail.data.display_name || mail.data.sender"
                :image="mail.data.user_image" size="lg" />
            <div class="text-xs space-y-1">
                <div class="text-base font-semibold">
                    {{ mail.data.display_name || mail.data.sender }}
                </div>
                <div class="leading-4">
                    {{ mail.data.subject }}
                </div>
                <div class="space-x-2">
                    <span v-if="mail.data.to.length">
                        {{ __("To") }}: 
                        <span v-for="recipient in mail.data.to" class="text-gray-700">
                            {{ recipient.display_name || recipient.email }}
                        </span>
                    </span>
                    <span v-if="mail.data.cc.length">
                        {{ __("Cc") }}: 
                        <span v-for="recipient in mail.data.cc" class="text-gray-700">
                            {{ recipient.display_name || recipient.email }}
                        </span>
                    </span>
                    <span v-if="mail.data.bcc.length">
                        {{ __("Bcc") }}: 
                        <span v-for="recipient in mail.data.bcc" class="text-gray-700">
                            {{ recipient.display_name || recipient.email }}
                        </span>
                    </span>
                </div>
            </div>
        </div>
        <div class="border rounded-md w-fit mx-auto relative bottom-4 bg-white">
            <Button variant="ghost" @click="openModal('reply')">
                <template #icon>
                    <Reply class="w-4 h-4 text-gray-600" />
                </template>
            </Button>
            <Button variant="ghost" @click="openModal('replyAll')">
                <template #icon>
                    <ReplyAll class="w-4 h-4 text-gray-600" />
                </template>
            </Button>
            <Button variant="ghost" @click="openModal('forward')">
                <template #icon>
                    <Forward class="w-4 h-4 text-gray-600" />
                </template>
            </Button>
        </div>
        <div v-if="mail.data.body_html" v-html="mail.data.body_html"
            class="text-sm ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-gray-300 prose-th:border-gray-300 prose-td:relative prose-th:relative prose-th:bg-gray-100 prose-sm max-w-none">
        </div>
    </div>
    <div v-else class="flex-1 flex flex-col space-y-2 items-center justify-center w-full h-full my-auto">
        <div class="text-gray-500 text-lg">
            {{ __("No emails to show") }}
        </div>
    </div>
    <SendMail v-model="showSendModal" :replyDetails="replyDetails"/>
</template>
<script setup>
import { createResource, Avatar, Button } from 'frappe-ui';
import { watch, ref, reactive } from 'vue';
import { Reply, ReplyAll, Forward } from 'lucide-vue-next';
import SendMail from "@/components/Modals/SendMail.vue";

const showSendModal = ref(false)
const replyDetails = reactive({
    to: "",
    cc: "",
    bcc: "",
    subject: "",
})

const props = defineProps({
    mailID: {
        type: [String, null],
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
    auto: props.mailID ? true : false,
});

const openModal = (type) => {
    showSendModal.value = true
    replyDetails.to = mail.data.sender
    replyDetails.subject = `Re: ${mail.data.subject}`
    if (type === 'replyAll') {
        replyDetails.cc = mail.data.cc.map(cc => cc.email).join(", ")
        replyDetails.bcc = mail.data.bcc.map(bcc => bcc.email).join(", ")
    }
    if (type === 'forward') {
        replyDetails.subject = `Fwd: ${mail.data.subject}`
    }
}

watch(
    () => props.mailID,
    (newName) => {
        mail.reload({ mailID: newName })
    }
)
</script>