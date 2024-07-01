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

export function formatNumber(number) {
    return number.toLocaleString('en-IN', {
        maximumFractionDigits: 0,
    })
}

export function startResizing (event) {
    const startX = event.clientX;
    const sidebar = document.getElementsByClassName("mailSidebar")[0];
    const startWidth = sidebar.offsetWidth;

    const onMouseMove = (event) => {
        const diff = event.clientX - startX;
        let newWidth = startWidth + diff;
        if (newWidth < 200) {
            newWidth = 200;
        }
        sidebar.style.width = newWidth + "px";
    }

    const onMouseUp = () => {
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);
    }

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
}