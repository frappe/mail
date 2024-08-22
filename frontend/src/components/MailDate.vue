<template>
    <div class="text-xs text-gray-600">
        {{ formattedDate }}
    </div>
</template>
<script setup>
import { inject, computed } from 'vue';

const dayjs = inject('$dayjs')

const props = defineProps({
    datetime: {
        type: String,
        required: true
    },
    inList: {
        type: Boolean,
        default: false
    }
})

const formattedDate = computed(() => {
    if (dayjs(props.datetime).isToday()) {
        return dayjs(props.datetime).format('h:mm A')
    } else if (dayjs(props.datetime).isYesterday()) {
        return props.inList ? `Yesterday` : `Yesterday at ${dayjs(props.datetime).format('h:mm A')}`
    } else {
        return props.inList ? dayjs(props.datetime).format('DD MMM YYYY') : `${dayjs(props.datetime).format('MMM D, YYYY')} at ${dayjs(props.datetime).format('h:mm A')}`
    }
})
</script>