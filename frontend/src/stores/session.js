import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'
import { userStore } from './user'
import router from '@/router'
import { ref, computed } from 'vue'

export const sessionStore = defineStore('mail-session', () => {
    let { userResource } = userStore()

    function sessionUser() {
        let cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
        let _sessionUser = cookies.get('user_id')
        if (_sessionUser === 'Guest') {
            _sessionUser = null
        }
        return _sessionUser
    }

    let user = ref(sessionUser())
    const isLoggedIn = computed(() => !!user.value)

    const login = createResource({
        url: 'login',
        onError() {
            throw new Error('Invalid email or password')
        },
        onSuccess() {
            userResource.reload()
            user.value = sessionUser()
            login.reset()
            router.replace({ path: '/' })
        },
    })

    const logout = createResource({
        url: 'logout',
        onSuccess() {
            userResource.reset()
            user.value = null
            window.location.reload()
        },
    })

    const branding = createResource({
        url: 'mail.api.mail.get_branding',
        cache: 'brand',
        auto: true,
        onSuccess(data) {
            document.querySelector("link[rel='icon']").href = data.favicon
        },
    })

    return {
        user,
        isLoggedIn,
        login,
        logout,
        branding,
    }
})
