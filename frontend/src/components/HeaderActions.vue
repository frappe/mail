<template>
    <div>
        <Tooltip :text="__('Compose a new message')">
            <Button variant="ghost">
                <SquarePen class="h-4 w-4 text-gray-700" />
            </Button>
        </Tooltip>
    </div>
</template>
<script setup>
import { Button, Tooltip } from "frappe-ui";
import { SquarePen } from "lucide-vue-next";
</script>