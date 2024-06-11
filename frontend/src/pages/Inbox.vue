<template>
    <header class="sticky top-0 z-10 flex items-center justify-between border-b bg-white px-3 py-2.5 sm:px-5">
        <Breadcrumbs :items="breadcrumbs" />
    </header>
    <div v-if="incomingMails.data" class="flex h-screen">
        <div class="overflow-auto border-r w-1/4 px-5 py-3 divide-y">
            <div v-for="mail in incomingMails.data" class="flex flex-col py-2 space-y-1">
                <div class="font-semibold">
                    {{ mail.display_name }}
                </div>
                <div class="text-xs">
                    {{ mail.subject }}
                </div>
                <div class="snippet text-xs text-gray-600">
                    {{ mail.snippet }}
                </div>
            </div>
            <div class="flex-1 overflow-auto w-3/4">

            </div>
        </div>
    </div>
</template>
<script setup>
import { Breadcrumbs, createResource } from "frappe-ui";
import { computed, inject } from "vue";

const user = inject("$user");

const breadcrumbs = computed(() => {
    return [{
        label: "Inbox",
        route: { name: "Inbox" }
    }]
})

const incomingMails = createResource({
   url: "mail.api.mail.get_incoming_mails",
   auto: true,
});

</script>
<style>
.snippet {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    text-overflow: ellipsis;
    width: 100%;
    overflow: hidden;
    margin: 0.25rem 0 1.25rem;
    line-height: 1.5;
}
</style>