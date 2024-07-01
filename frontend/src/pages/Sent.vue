<template>
    <div>
        <header class="sticky top-0 z-10 flex items-center justify-between border-b bg-white px-3 py-2.5 sm:px-5">
            <Breadcrumbs :items="breadcrumbs">
                <template #suffix>
                    <div v-if="outgoingMailCount.data" class="self-end text-xs text-gray-600 ml-2">
                        {{ formatNumber(outgoingMailCount.data) }} {{ __("messages") }}
                    </div>
                </template>
            </Breadcrumbs>
            <HeaderActions />
        </header>
        <div v-if="outgoingMails.data" class="flex">
            <div @scroll="loadMoreEmails" ref="mailSidebar"
                class="mailSidebar border-r w-1/3 px-5 py-3 h-[calc(100vh-3.2rem)] sticky top-16 overflow-y-scroll overscroll-contain">
                <div v-for="(mail, idx) in outgoingMails.data" @click="openMail(mail)"
                    class="flex flex-col py-2 space-y-1 cursor-pointer"
                    :class="{ 'border-b': idx < outgoingMails.data.length - 1 }">
                    <SidebarDetail :mail="mail" />
                </div>
            </div>
            <div class="flex w-2 cursor-col-resize justify-center" @mousedown="startResizing">
                <div ref="resizer"
                    class="h-full w-[2px] rounded-full transition-all duration-300 ease-in-out group-hover:bg-gray-400" />
            </div>
            <div v-if="currentMail" class="flex-1 overflow-auto w-2/3">
                <MailDetails :mailID="currentMail.name" type="Outgoing Mail"/>
            </div>
        </div>
    </div>
</template>
<script setup>
import { Breadcrumbs, createResource, createListResource } from 'frappe-ui';
import { computed, inject, ref } from 'vue';
import HeaderActions from "@/components/HeaderActions.vue";
import { formatNumber, startResizing } from "@/utils";
import MailDetails from "@/components/MailDetails.vue";
import { useDebounceFn } from '@vueuse/core'
import SidebarDetail from "@/components/SidebarDetail.vue";

const user = inject("$user");
const mailStart = ref(0)
const mailList = ref([])
const currentMail = ref(null)

const outgoingMails = createListResource({
    url: "mail.api.mail.get_outgoing_mails",
    doctype: "Outgoing Mail",
    auto: true,
    start: mailStart.value,
    pageLength: 50,
    cache: ["outgoing", user.data?.name],
    onSuccess(data) {
        mailList.value = mailList.value.concat(data)
        mailStart.value = mailStart.value + data.length
        if (!currentMail.value) {
            currentMail.value = data[0]
        }
    }
});

const outgoingMailCount = createResource({
    url: "frappe.client.get_count",
    makeParams(values) {
        return {
            doctype: "Outgoing Mail",
            filters: {
                sender: user.data?.name,
                status: "Sent"
            }
        }
    },
    cache: ["outgoingMailCount", user.data?.name],
    auto: true,
})

const loadMoreEmails = useDebounceFn(() => {
    if (outgoingMails.hasNextPage)
        outgoingMails.next()
}, 500)

const openMail = (mail) => {
    currentMail.value = mail
}

const breadcrumbs = computed(() => {
    return [
        {
            label: "Sent",
            route: { name: "Sent" }
        }
    ];
});
</script>