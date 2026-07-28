<!-- 根组件，布局 + <router-view> -->
<script setup lang="ts">
import NavBar from "@/components/NavBar.vue"
import { useAuthStore } from "@/stores/auth"
import { onMounted } from "vue"

const auth = useAuthStore()

onMounted(async () => {
  if (auth.isLoggedIn) {
    try {
      await auth.fetchUser()
    } catch {
      auth.logout()
    }
  }
})

</script>

<template>
  <div id="app">
    <NavBar />
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style>

body {
  margin: 0;
  font-family: "Helvetica Neue", Arial, sans-serif;
  background: #f5f7fa;
}
.main-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}
</style>
