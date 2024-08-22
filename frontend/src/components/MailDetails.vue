<template>
    <div v-if="mail.data" class="p-3 pl-5">
        <div class="flex space-x-3 border-b pb-2">
            <Avatar class="avatar border border-gray-300" :label="mail.data.display_name || mail.data.sender"
                :image="mail.data.user_image" size="lg" />
            <div class="text-xs space-y-1 flex-1">
                <div class="flex items-center justify-between">
                    <div class="text-base font-semibold">
                        {{ mail.data.display_name || mail.data.sender }}
                    </div>
                    <MailDate :datetime="mail.data.creation" />
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
        <div v-if="mail.data.body_html" v-html="mailBody"
            class="text-sm leading-5 ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-gray-300 prose-th:border-gray-300 prose-td:relative prose-th:relative prose-th:bg-gray-100 prose-sm max-w-none">
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
import { watch, ref, reactive, inject, computed } from 'vue';
import { Reply, ReplyAll, Forward } from 'lucide-vue-next';
import SendMail from "@/components/Modals/SendMail.vue";
import MailDate from '@/components/MailDate.vue';

const showSendModal = ref(false)
const dayjs = inject("$dayjs")

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

const replyDetails = reactive({
    to: "",
    cc: "",
    bcc: "",
    subject: "",
    reply_to_mail_type: props.type,
    reply_to_mail_name: "",
})

const mail = createResource({
    url: "mail.api.mail.get_mail",
    makeParams(values) {
        return {
            name: values?.mailID || props.mailID,
            type: props.type
        }
    },
    auto: props.mailID ? true : false,
});

const mailBody = computed(() => {
    return mail.data.body_html.replace(/<br\s*\/?>/, '')
})

const openModal = (type) => {    
    if (props.type == "Incoming Mail") {
        replyDetails.to = mail.data.sender
    } else {
        replyDetails.to = mail.data.to.map(to => to.email).join(", ")
    }

    replyDetails.subject = `Re: ${mail.data.subject}`
    replyDetails.cc = ""
    replyDetails.bcc = ""
    replyDetails.reply_to_mail_name = mail.data.name
    
    if (type === 'replyAll') {
        replyDetails.cc = mail.data.cc.map(cc => cc.email).join(", ")
        replyDetails.bcc = mail.data.bcc.map(bcc => bcc.email).join(", ")
    }
    if (type === 'forward') {
        replyDetails.to = ""
        replyDetails.subject = `Fwd: ${mail.data.subject}`
    }
    replyDetails.html = getReplyHtml(mail.data.body_html, type)
    showSendModal.value = true
}

const getReplyHtml = (html, type) => {
    const replyHeader = `
        On ${dayjs(mail.data.creation).format("DD MMM YYYY")} at ${dayjs(mail.data.creation).format("h:mm A")}, ${replyDetails.to} wrote:
    `;
    return `<br><blockquote>${replyHeader} <br> ${html}</blockquote>`;
}

watch(
    () => props.mailID,
    (newName) => {
        mail.reload({ mailID: newName })
    }
)
</script>
<style>
.prose :where(blockquote p:first-of-type):not(:where([class~="not-prose"],[class~="not-prose"] *))::before {
    content: ""
}
</style>