export function convertToTitleCase(str) {
    if (!str) {
        return ''
    }

    return str
        .toLowerCase()
        .split(' ')
        .map(function (word) {
            return word.charAt(0).toUpperCase().concat(word.substr(1))
        })
        .join(' ')
}

export function getSidebarLinks() {
    return [
        {
            label: 'Inbox',
            icon: 'Inbox',
            to: 'Inbox',
            activeFor: ['Inbox'],
        },
        {
            label: 'Sent',
            icon: 'Send',
            to: 'Sent',
            activeFor: ['Sent'],
        },
    ]
}