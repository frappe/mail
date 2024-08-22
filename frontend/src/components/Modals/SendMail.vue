<template>
    <Dialog v-model="show" :options="{
        title: __('Send Mail'),
        size: '4xl',
        actions: [{
            label: __('Send'),
            variant: 'solid',
            onClick: (close) => {
                send(close)
            }
        }]
    }">
        <template #body-content>
            <div class="flex flex-col space-y-4 text-sm">
                <FormControl v-model="mail.to" :label="__('To')"/>
                <FormControl v-model="mail.cc" :label="__('CC')" />
                <FormControl v-model="mail.bcc" :label="__('BCC')" />
                <FormControl v-model="mail.subject" :label="__('Subject')" />
                <div>
                    <div class="mb-1.5 text-xs text-gray-600">
                        {{ __('Message') }}
                    </div>
                    <TextEditor :content="mail.html" @change="(val) => (mail.html = val)" :editable="true"
                        :fixedMenu="true"
                        editorClass="text-sm prose-sm max-w-none border-b border-x bg-gray-100 rounded-b-md py-2 px-2 min-h-[7rem]" />
                </div>
            </div>
        </template>
    </Dialog>
</template>
<script setup>
import { Dialog, FormControl, TextEditor, createResource } from "frappe-ui";
import { reactive, watch, inject } from "vue";

const user = inject("$user");
const show = defineModel()

const props = defineProps({
    replyDetails: {
        type: Object,
        required: false
    }
})

const mail = reactive({
    to: "",
    cc: "",
    bcc: "",
    subject: "",
    html: ""
})

watch(show, () => {
    if (show.value && props.replyDetails) {
        mail.to = props.replyDetails.to
        mail.cc = props.replyDetails.cc
        mail.bcc = props.replyDetails.bcc
        mail.subject = props.replyDetails.subject
        mail.html = props.replyDetails.html
        mail.reply_to_mail_type = props.replyDetails.reply_to_mail_type
        mail.reply_to_mail_name = props.replyDetails.reply_to_mail_name
    }
})

const sendMail = createResource({
    url: "mail.api.outbound.send",
    method: "POST",
    makeParams(values) {
        return {
            from_: `${user.data?.full_name} <${user.data?.name}>`,
            ...mail
        }
    },
})

const send = (close) => {
    sendMail.submit({}, {
        onSuccess() {
            close()
        }
    })
}

</script>