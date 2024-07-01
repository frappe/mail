<template>
    <div class="">
        <header class="sticky top-0 z-10 flex items-center justify-between border-b bg-white px-3 py-2.5 sm:px-5">
            <Breadcrumbs :items="breadcrumbs">
                <template #suffix>
                    <div v-if="incomingMailCount.data" class="self-end text-xs text-gray-600 ml-2">
                        {{ formatNumber(incomingMailCount.data) }} {{ __("messages") }}
                    </div>
                </template>
            </Breadcrumbs>
            <HeaderActions />
        </header>
        <div v-if="incomingMails.data" class="flex">
            <div @scroll="loadMoreEmails" ref="mailSidebar"
                class="mailSidebar border-r w-1/3 px-5 py-3 h-[calc(100vh-3.2rem)] sticky top-16 overflow-y-scroll overscroll-contain">
                <div v-for="(mail, idx) in incomingMails.data" @click="openMail(mail)"
                    class="flex flex-col py-2 space-y-1 cursor-pointer"
                    :class="{ 'border-b': idx < incomingMails.data.length - 1 }">
                    <SidebarDetail :mail="mail" />
                </div>
            </div>
            <div class="flex w-2 cursor-col-resize justify-center" @mousedown="startResizing">
                <div ref="resizer"
                    class="h-full w-[2px] rounded-full transition-all duration-300 ease-in-out group-hover:bg-gray-400" />
            </div>
            <div v-if="currentMail" class="flex-1 overflow-auto w-2/3">
                <MailDetails :mailID="currentMail.name" type="Incoming Mail"/>
            </div>
        </div>
    </div>
</template>
<script setup>
import { Breadcrumbs, createListResource, createResource } from "frappe-ui";
import { computed, inject, ref, onMounted } from "vue";
import { formatNumber, startResizing } from "@/utils";
import HeaderActions from "@/components/HeaderActions.vue";
import MailDetails from "@/components/MailDetails.vue";
import { set, useDebounceFn } from '@vueuse/core'
import SidebarDetail from "@/components/SidebarDetail.vue";

const user = inject("$user");
const mailStart = ref(0)
const mailList = ref([])
const currentMail = ref(null)

onMounted(() => {
    setCurrentMail()
})

const incomingMails = createListResource({
   url: "mail.api.mail.get_incoming_mails",
   doctype: "Incoming Mail",
   auto: true,
   start: mailStart.value,
   pageLength: 50,
   cache: ["incoming", user.data?.name],
   onSuccess(data) {
        mailList.value = mailList.value.concat(data)
        mailStart.value = mailStart.value + data.length
       setCurrentMail()
   }
});

const incomingMailCount = createResource({
    url: "frappe.client.get_count",
    makeParams(values) {
        return {
            doctype: "Incoming Mail",
            filters: {
                receiver: user.data?.name,
            }
        }
    },
    cache: ["incomingMailCount", user.data?.name],
    auto: true,
})

const loadMoreEmails = useDebounceFn(() => {
    if (incomingMails.hasNextPage)
        incomingMails.next()
}, 500)

const openMail = (mail) => {
    currentMail.value = mail
}

const setCurrentMail = () => {
    if (!currentMail.value && mailList.value.length) {
        currentMail.value = mailList.value[0]
    }
}

const breadcrumbs = computed(() => {
    return [{
        label: `Inbox`,
        route: { name: "Inbox" }
    }]
})



</script>