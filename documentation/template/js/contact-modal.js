(() => {
    const modal = document.getElementById("contact-modal");
    const openButton = document.getElementById("contact-open");
    if (!modal || !openButton) return;
    const closeButtons = modal.querySelectorAll("[data-contact-close]");
    const firstField = modal.querySelector('input[name="name"]');
    const status = document.getElementById("contact-status");
    const form = modal.querySelector("form.contact-form");
    let previousFocus = null;
    let clearSuccessOnClose = false;

    function openModal() {
        previousFocus = document.activeElement;
        modal.classList.add("is-open");
        modal.setAttribute("aria-hidden", "false");
        document.body.classList.add("contact-modal-open");
        window.setTimeout(() => firstField && firstField.focus(), 20);
    }
    function closeModal() {
        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("contact-modal-open");

        // A successful submission confirmation is shown only once. After the
        // visitor closes it, return the modal to a clean form for next time.
        if (clearSuccessOnClose) {
            if (status) {
                status.hidden = true;
                status.className = "contact-status";
                status.textContent = "";
            }
            if (form) form.reset();
            clearSuccessOnClose = false;
        }

        if (previousFocus) previousFocus.focus();
    }

    openButton.addEventListener("click", openModal);
    closeButtons.forEach((button) => button.addEventListener("click", closeModal));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && modal.classList.contains("is-open")) closeModal();
    });

    const params = new URLSearchParams(window.location.search);
    const result = params.get("contact");
    if (result && status) {
        status.hidden = false;
        status.className = result === "sent" ? "contact-status is-success" : "contact-status is-error";
        status.textContent = result === "sent"
            ? "Thanks — your message has been sent."
            : "We could not send your message. Please try again or email contact@scriptronaut.com.";
        clearSuccessOnClose = result === "sent";
        openModal();
        params.delete("contact");
        const query = params.toString();
        history.replaceState({}, "", location.pathname + (query ? "?" + query : "") + location.hash);
    }
})();