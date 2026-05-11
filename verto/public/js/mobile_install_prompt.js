(() => {
    let deferredInstallPrompt = null;

    window.addEventListener("beforeinstallprompt", (event) => {
        event.preventDefault();
        deferredInstallPrompt = event;
    });

    function isLoginPage() {
        const path = window.location.pathname;

        return path === "/" ||
            path === "/login" ||
            path.endsWith("/login") ||
            document.querySelector(".for-login") ||
            document.querySelector(".page-card");
    }

    function isMobileBrowser() {
        return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    }

    function isRunningStandalone() {
        return window.matchMedia("(display-mode: standalone)").matches ||
            window.navigator.standalone === true;
    }

    function isIOS() {
        return /iPhone|iPad|iPod/i.test(navigator.userAgent);
    }

    function isAndroid() {
        return /Android/i.test(navigator.userAgent);
    }

    function showMessage(html) {
        if (window.frappe && frappe.msgprint) {
            frappe.msgprint(html);
            return;
        }

        alert(html.replace(/<br\s*\/?>/gi, "\n").replace(/<[^>]+>/g, ""));
    }

    function showInstallInstructions() {
        if (isIOS()) {
            showMessage(`
                <b>Install this app on iPhone/iPad</b><br><br>
                1. Open this site in <b>Safari</b>.<br>
                2. Tap the <b>...</b> button.<br>
                3. Tap the <b>Share</b> button.<br>
                4. Scroll down and tap <b>Add to Home Screen</b>.<br>
                5. Tap <b>Add</b>.
            `);
            return;
        }

        if (isAndroid()) {
            showMessage(`
                <b>Install this app on Android</b><br><br>
                1. Tap the browser menu <b>⋮</b>.<br>
                2. Tap <b>Install app</b> or <b>Add to Home screen</b>.<br>
                3. Confirm the install.
            `);
            return;
        }

        showMessage(`
            Use your browser menu and select <b>Install app</b> or 
            <b>Add to Home Screen</b>.
        `);
    }

    async function handleInstallClick() {
        if (deferredInstallPrompt) {
            deferredInstallPrompt.prompt();
            await deferredInstallPrompt.userChoice;
            deferredInstallPrompt = null;
            return;
        }

        showInstallInstructions();
    }

    function addInstallPrompt() {
        if (!isLoginPage()) return;
        if (!isMobileBrowser()) return;
        if (isRunningStandalone()) return;
        if (document.querySelector("#mobile-install-prompt")) return;

        const loginContainer =
            document.querySelector(".page-card") ||
            document.querySelector(".for-login") ||
            document.querySelector(".login-content") ||
            document.body;

        const prompt = document.createElement("div");
        prompt.id = "mobile-install-prompt";
        prompt.className = "mobile-install-prompt";

        prompt.innerHTML = `
            <div class="mobile-install-card">
                <div class="mobile-install-icon">📱</div>
                <div class="mobile-install-content">
                    <div class="mobile-install-title">Install this app</div>
                    <div class="mobile-install-text">
                        Add this site to your home screen for quicker access.
                    </div>
                </div>
                <button type="button" class="btn btn-primary btn-sm" id="mobile-install-button">
                    Install
                </button>
            </div>
        `;

        loginContainer.prepend(prompt);

        const button = prompt.querySelector("#mobile-install-button");

        if (button) {
            button.addEventListener("click", handleInstallClick);
        }
    }

    function runWhenReady() {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", addInstallPrompt);
        } else {
            addInstallPrompt();
        }

        setTimeout(addInstallPrompt, 500);
        setTimeout(addInstallPrompt, 1500);
    }

    runWhenReady();
})();