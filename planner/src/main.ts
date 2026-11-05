import "./index.css";

import { createApp } from "vue";
import router from "./router";
import App from "./App.vue";

import { Button, setConfig, resourcesPlugin } from "frappe-ui";
import { plannerRequest } from "./utils/requestCoordinator";

const app = createApp(App);

setConfig("resourceFetcher", plannerRequest);

app.use(router);
app.use(resourcesPlugin);

app.component("Button", Button);
app.mount("#app");
