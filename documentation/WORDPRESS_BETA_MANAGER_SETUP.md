# Scriptronaut Beta Manager — WordPress integration

WordPress: `http://scotdthomson.com/wp`  
Static Scriptronaut site: `http://scotdthomson.com/scriptronaut`

## 1. Install the plugin

In WordPress, open **Plugins → Add New → Upload Plugin**, choose `scriptronaut-beta-manager.zip`, install, and activate it.

Then open **Beta Manager → Settings** and confirm:

- notification recipient email
- From email/name
- static beta URL: `http://scotdthomson.com/scriptronaut/betas.html`
- static feedback URL: `http://scotdthomson.com/scriptronaut/beta-feedback.html`
- attachment and rate-limit values

## 2. Static form actions

The included templates have already been changed to use these WordPress handlers:

- Beta signup: `/wp/wp-admin/admin-post.php?action=scriptronaut_beta_signup`
- Beta feedback: `/wp/wp-admin/admin-post.php?action=scriptronaut_beta_feedback`
- Newsletter signup: `/wp/wp-admin/admin-post.php?action=scriptronaut_relay_subscribe`

Root-relative URLs are intentional. Because both sites use the same domain, they work regardless of HTTP/HTTPS after you enable HTTPS.

## 3. Newsletter / Relay

Newsletter subscriptions are owned by the separate **Scriptronaut Relay** WordPress plugin.

The beta signup form includes the optional `newsletter_optin` checkbox. With Relay active, Beta Manager hands that consent directly to Relay with source `beta_signup`.

The home-page standalone newsletter form posts directly to Relay using:

- action: `scriptronaut_relay_subscribe`
- `name` (required)
- `email` (required)
- `website` (hidden honeypot; should remain empty)

Standalone subscriptions are stored by Relay with source `newsletter_signup`.

## 4. Beta workflow

1. A person submits `betas.html`.
2. They appear under **Beta Manager → Candidates**.
3. Click **Approve**.
4. WordPress creates a tester ID and a one-time visible access code.
5. Copy those credentials and send them to the tester. The access code is stored only as a hash and cannot be recovered later.
6. If needed, click **New Access Code** to invalidate the old code and generate a new one.
7. Feedback submitted from `beta-feedback.html` appears under **Beta Manager → Feedback** and is also emailed to the configured recipient.

## 5. Old PHP handlers

The old `template/php/beta-signup-submit.php` and `template/php/beta-feedback-submit.php` are no longer used by these two forms. They can remain in your source tree while you test, but you do not need to deploy them once the WordPress flow is confirmed.

## 6. Uploads

Feedback attachments are stored using WordPress uploads and are linked from the Feedback admin page. The plugin accepts `.blend`, `.txt`, `.log`, and `.zip` files, subject to both plugin limits and your server/PHP upload limits.
