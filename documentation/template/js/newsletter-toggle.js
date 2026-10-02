(() => {
    const toggle = document.getElementById("newsletter-toggle");
    const panel = document.getElementById("newsletter-form-panel");
    if (!toggle || !panel) return;

    function setOpen(open) {
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        panel.hidden = !open;
        panel.classList.toggle("is-open", open);
    }

    toggle.addEventListener("click", () => {
        setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });

    // Keep the form visible after Relay redirects back with a newsletter/subscription result.
    const params = new URLSearchParams(window.location.search);
    const hasRelayResult = [...params.keys()].some((key) =>
        /relay|newsletter|subscribe|subscription/i.test(key)
    );
    const hashTargetsNewsletter = /newsletter|subscribe/i.test(window.location.hash);

    if (hasRelayResult || hashTargetsNewsletter) {
        setOpen(true);
    }
})();