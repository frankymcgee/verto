// custom_app/custom_app/public/js/custom_desk_script.js

document.addEventListener("DOMContentLoaded", function() {
    const script = document.createElement("script");
    script.type = "module";
    script.innerHTML = `
    import Chatbot from "https://cdn.jsdelivr.net/npm/flowise-embed/dist/web.js"
    Chatbot.init({
        chatflowid: "70f89ec5-002c-42df-b5b7-368ff61b6694",
        apiHost: "https://ai.webwire.com.au",
    })
    `;
    document.head.appendChild(script);
});
