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
            <div class="flex flex-col space-y-4">
                <FormControl v-model="mail.to" :label="__('To')" />
                <FormControl v-model="mail.cc" :label="__('CC')" />
                <FormControl v-model="mail.bcc" :label="__('BCC')" />
                <FormControl v-model="mail.subject" :label="__('Subject')" />
                <div>
                    <div class="mb-1.5 text-sm text-gray-700">
                        {{ __('Message') }}
                    </div>
                    <TextEditor :content="mail.html" @change="(val) => (mail.html = val)" :editable="true"
                        :fixedMenu="true"
                        editorClass="prose-sm max-w-none border-b border-x bg-gray-100 rounded-b-md py-1 px-2 min-h-[7rem]" />
                </div>
            </div>
        </template>
    </Dialog>
</template>
<script setup>
import { Dialog, FormControl, TextEditor, createResource } from "frappe-ui";
import { reactive } from "vue";

const show = defineModel()
const mail = reactive({
    to: "pateljannat2308@gmail.com",
    cc: "",
    bcc: "",
    subject: "From Hardcode",
    html: "<p>Hardcoded</p>"
})

const sender = createResource({
    url: "frappe.client.get_list",
    makeParams(values) {
        return {
            doctype: "Mailbox",
            fields: ["email"],
            filters: {
                'enabled': true,
                'outgoing': true
            }
        }
    },
})

const sendMail = createResource({
    url: "mail.api.outbound.send",
    method: "POST",
    makeParams(values) {
        console.log(mail)
        return {
            from: "sagar.s@frappemail.com",
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