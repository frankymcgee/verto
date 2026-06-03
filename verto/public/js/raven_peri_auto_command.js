(function () {
    console.log("[PERI Auto Command] Script file loaded:", window.location.pathname);

    const MAX_ATTEMPTS = 120;
    const ATTEMPT_DELAY_MS = 500;

    let hasStarted = false;
    let hasSent = false;

    function log(...args) {
        console.log("[PERI Auto Command]", ...args);
    }

    function isRavenPage() {
        return window.location.pathname.includes("/raven");
    }

    function getStoredCommand() {
        return sessionStorage.getItem("peri_auto_command");
    }

    function clearStoredCommand() {
        sessionStorage.removeItem("peri_auto_command");
        sessionStorage.removeItem("peri_auto_source");
        sessionStorage.removeItem("peri_auto_project_scope_name");
    }

    function isVisible(el) {
        if (!el) {
            return false;
        }

        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();

        return (
            style.display !== "none" &&
            style.visibility !== "hidden" &&
            rect.width > 0 &&
            rect.height > 0
        );
    }

    function findComposer() {
        const selectors = [
            ".tiptap-editor[contenteditable='true']",
            ".ProseMirror.tiptap-editor[contenteditable='true']",
            ".tiptap.ProseMirror.tiptap-editor[contenteditable='true']",
            "[contenteditable='true'].tiptap-editor"
        ];

        for (const selector of selectors) {
            const matches = Array.from(document.querySelectorAll(selector))
                .filter(isVisible);

            if (matches.length) {
                return matches[matches.length - 1];
            }
        }

        return null;
    }

    function findSendButton() {
        return (
            document.querySelector('button[aria-label="send message"]') ||
            document.querySelector('button[title="Send message"]') ||
            document.querySelector('[role="button"][aria-label="send message"]') ||
            document.querySelector('[role="button"][title="Send message"]')
        );
    }

    function insertText(editor, text) {
        if (!editor) {
            return false;
        }

        if (editor.getAttribute("contenteditable") !== "true") {
            log("Composer found but it is not editable:", editor);
            return false;
        }

        editor.focus();

        try {
            document.execCommand("selectAll", false, null);
            document.execCommand("delete", false, null);
            const inserted = document.execCommand("insertText", false, text);

            editor.dispatchEvent(
                new InputEvent("input", {
                    bubbles: true,
                    cancelable: true,
                    inputType: "insertText",
                    data: text
                })
            );

            editor.dispatchEvent(new Event("change", { bubbles: true }));
            editor.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true }));

            log("execCommand insert result:", inserted);
            return true;
        } catch (error) {
            log("execCommand failed:", error);
        }

        try {
            editor.innerHTML = `<p>${escapeHtml(text)}</p>`;

            editor.dispatchEvent(
                new InputEvent("input", {
                    bubbles: true,
                    cancelable: true,
                    inputType: "insertText",
                    data: text
                })
            );

            editor.dispatchEvent(new Event("change", { bubbles: true }));

            return true;
        } catch (error) {
            log("DOM fallback failed:", error);
            return false;
        }
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function getComposerText(editor) {
        return (editor && (editor.innerText || editor.textContent || "")).trim();
    }

    function sendMessage(editor) {
        const sendButton = findSendButton();

        if (sendButton) {
            log("Send button found. Clicking:", sendButton);
            sendButton.click();
            return true;
        }

        log("Send button not found. Trying Enter key.");

        editor.dispatchEvent(
            new KeyboardEvent("keydown", {
                key: "Enter",
                code: "Enter",
                which: 13,
                keyCode: 13,
                bubbles: true,
                cancelable: true
            })
        );

        return true;
    }

    function runAutoCommand(forceRun = false) {
        if (hasSent) {
            return;
        }

        if (!isRavenPage()) {
            log("Not on Raven page. Current path:", window.location.pathname);
            return;
        }

        const command = getStoredCommand();

        if (!command) {
            log("No peri_auto_command found in sessionStorage.");
            return;
        }

        if (hasStarted && !forceRun) {
            return;
        }

        hasStarted = true;

        log("Auto command found:", command);

        let attempts = 0;

        const interval = setInterval(function () {
            if (hasSent) {
                clearInterval(interval);
                return;
            }

            attempts += 1;

            const editor = findComposer();

            if (!editor) {
                log(`Attempt ${attempts}: Raven composer not found yet.`);

                if (attempts >= MAX_ATTEMPTS) {
                    clearInterval(interval);
                    hasStarted = false;
                    console.warn("[PERI Auto Command] Composer not found after max attempts.");
                }

                return;
            }

            log("Composer found:", editor);

            const inserted = insertText(editor, command);

            if (!inserted) {
                log(`Attempt ${attempts}: Failed to insert command.`);

                if (attempts >= MAX_ATTEMPTS) {
                    clearInterval(interval);
                    hasStarted = false;
                }

                return;
            }

            setTimeout(function () {
                const textNow = getComposerText(editor);
                log("Composer text after insert:", textNow);

                if (!textNow.includes(command)) {
                    log("Command was not detected in composer after insert.");
                    return;
                }

                sendMessage(editor);

                hasSent = true;
                clearStoredCommand();
                clearInterval(interval);

                log("Command sent and sessionStorage cleared.");
            }, 700);
        }, ATTEMPT_DELAY_MS);
    }

    function startObserver() {
        if (!document.body) {
            setTimeout(startObserver, 500);
            return;
        }

        const observer = new MutationObserver(function () {
            const command = getStoredCommand();

            if (!command || hasSent) {
                return;
            }

            const editor = findComposer();

            if (editor) {
                log("MutationObserver detected Raven composer.");
                runAutoCommand(true);
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        log("MutationObserver started.");
    }

    // Expose manual debug helper
    window.runPeriAutoCommand = function () {
        hasStarted = false;
        hasSent = false;
        runAutoCommand(true);
    };

    startObserver();

    runAutoCommand(true);

    setTimeout(function () {
        runAutoCommand(true);
    }, 1000);

    setTimeout(function () {
        runAutoCommand(true);
    }, 3000);

    setTimeout(function () {
        runAutoCommand(true);
    }, 6000);
})();