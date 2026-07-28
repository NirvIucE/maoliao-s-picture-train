/*
三步：创建应用 → 装 Pinia → 装 Router → 挂载到 #app 
（ index.html 里的 <div id="app"> ）
*/
import { createApp } from "vue"
import { createPinia } from "pinia"
import App from "./App.vue"
import router from "./router"

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount("#app")