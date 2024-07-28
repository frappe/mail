<template>
    <div>
        <Tooltip :text="__('Compose a new message')">
            <Button variant="ghost" @click="openSendModal()">
                <SquarePen class="h-4 w-4 text-gray-700" />
            </Button>
        </Tooltip>
    </div>
    <SendMail v-model="showSendModal"/>
</template>
<script setup>
import { Button, Tooltip } from "frappe-ui";
import { SquarePen } from "lucide-vue-next";
import SendMail from "@/components/Modals/SendMail.vue";
import { ref } from "vue";

const showSendModal = ref(false)

const openSendModal = () => {
    showSendModal.value = true
}
</script>