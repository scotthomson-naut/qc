"use strict";

const QC_CHECKS = window.QC_BETA_CHECKS || {};

const form = document.getElementById("beta-feedback-form");
const reportType = document.getElementById("report-type");
const checkFields = document.getElementById("check-fields");
const issueFields = document.getElementById("issue-fields");
const categorySelect = document.getElementById("check-category");
const checkSelect = document.getElementById("check-name");

function titleCase(value) {
    return value.replace(/_/g, " ").replace(/\b\w/g, character => character.toUpperCase());
}

function setSelectValue(select, value) {
    if (!value) return;
    const normalized = value.toLowerCase();
    const option = Array.from(select.options).find(item =>
        item.value.toLowerCase() === normalized || item.textContent.toLowerCase() === normalized
    );
    if (option) select.value = option.value;
}

function populateCategories() {
    Object.keys(QC_CHECKS).forEach(category => {
        const option = document.createElement("option");
        option.value = category;
        option.textContent = titleCase(category);
        categorySelect.appendChild(option);
    });
}

function populateChecks(preferredCheck = "") {
    checkSelect.innerHTML = '<option value="">Choose a check</option>';
    const checks = QC_CHECKS[categorySelect.value] || [];
    checks.forEach(check => {
        const option = document.createElement("option");
        option.value = check;
        option.textContent = check;
        checkSelect.appendChild(option);
    });
    setSelectValue(checkSelect, preferredCheck);
}

function updateConditionalFields() {
    const type = reportType.value;
    const isCheckIssue = type === "check_issue";
    const isIssue = isCheckIssue || type === "crash" || type === "installation";

    checkFields.hidden = !isCheckIssue;
    issueFields.hidden = !isIssue;
    categorySelect.required = isCheckIssue;
    checkSelect.required = isCheckIssue;
}

function prefillFromBlender() {
    // addon_id may be supplied by an invitation URL, while Blender
    // diagnostics remain in the URL fragment.
    const pageQuery = new URLSearchParams(window.location.search);
    const addonInput = document.getElementById("beta-addon-id");
    const pageAddonId = pageQuery.get("addon_id");
    if (pageAddonId && /^[a-z0-9_-]+$/i.test(pageAddonId) && addonInput) {
        addonInput.value = pageAddonId.toLowerCase();
    }

    // Blender supplies diagnostics in the URL fragment so they are not sent
    // in the initial HTTP request or normal web-server access logs.
    const query = new URLSearchParams(window.location.hash.slice(1));
    const fragmentAddonId = query.get("addon_id");
    if (fragmentAddonId && /^[a-z0-9_-]+$/i.test(fragmentAddonId) && addonInput) {
        addonInput.value = fragmentAddonId.toLowerCase();
    }

    const mappings = {
        qc_version: "qc-version",
        blender_version: "blender-version",
        operating_system: "operating-system",
        blend_file: "blend-filename",
        traceback: "traceback",
        check_id: "check-id",
        traceback_time: "traceback-time",
        source: "feedback-source"
    };

    Object.entries(mappings).forEach(([parameter, elementId]) => {
        const value = query.get(parameter);
        const element = document.getElementById(elementId);
        if (value && element) element.value = value;
    });

    setSelectValue(document.getElementById("product-tier"), query.get("tier") || "");

    const category = (query.get("category") || "").toLowerCase();
    if (category && QC_CHECKS[category]) {
        reportType.value = "check_issue";
        categorySelect.value = category;
        populateChecks(query.get("check_name") || query.get("check_id") || "");
    }

    if (query.get("traceback")) {
        reportType.value = "crash";
    }

    updateConditionalFields();
}

populateCategories();
categorySelect.addEventListener("change", () => populateChecks());
reportType.addEventListener("change", updateConditionalFields);
prefillFromBlender();

const attachmentInput = form.querySelector('input[name="attachments[]"]');
const uploadConfirmationRow = document.getElementById("upload-confirmation-row");
const uploadConfirmation = form.elements.upload_confirmation;
const clearAttachmentsButton = document.getElementById("clear-attachments");

function updateUploadConfirmation() {
    const hasFiles = Boolean(attachmentInput && attachmentInput.files && attachmentInput.files.length);

    if (uploadConfirmationRow) {
        uploadConfirmationRow.hidden = !hasFiles;
    }

    if (clearAttachmentsButton) {
        clearAttachmentsButton.hidden = !hasFiles;
    }

    if (uploadConfirmation) {
        uploadConfirmation.required = hasFiles;

        if (!hasFiles) {
            uploadConfirmation.checked = false;
        }
    }
}

if (attachmentInput) {
    attachmentInput.addEventListener("change", updateUploadConfirmation);
}

if (clearAttachmentsButton && attachmentInput) {
    clearAttachmentsButton.addEventListener("click", () => {
        attachmentInput.value = "";
        updateUploadConfirmation();
        attachmentInput.focus();
    });
}

updateUploadConfirmation();

form.addEventListener("submit", event => {
    const files = Array.from(form.querySelector('input[type="file"]').files || []);
    const totalBytes = files.reduce((total, file) => total + file.size, 0);
    const oversized = files.find(file => file.size > 8 * 1024 * 1024);
    const confirmation = form.elements.upload_confirmation;

    if (files.length && !confirmation.checked) {
        event.preventDefault();
        alert("Please confirm that you have permission to share the selected files.");
        confirmation.focus();
        return;
    }

    if (oversized || totalBytes > 20 * 1024 * 1024) {
        event.preventDefault();
        alert("Each file must be 8 MB or smaller and the combined upload must be 20 MB or smaller.");
        return;
    }

    // Validation passed. Give immediate feedback while the browser uploads the
    // form and WordPress stores the report / sends notification email.
    const submitButton = form.querySelector('.beta-submit');
    const waitState = document.getElementById('beta-submit-wait');
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = 'Sending…';
    }
    if (waitState) {
        waitState.hidden = false;
    }
});
