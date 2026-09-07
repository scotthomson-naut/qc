# QC Checker private beta feedback setup

The feedback page is copied into `documentation/site` whenever the documentation
builder runs.

## Server setup

1. Copy `beta-feedback-config.example.php` to `beta-feedback-config.php` on the
   web server.
2. Set the recipient and sender email addresses.
3. Create a unique access code for each tester. Generate its hash with:

   ```console
   php -r "echo password_hash('TESTER ACCESS CODE', PASSWORD_DEFAULT), PHP_EOL;"
   ```

4. Add each tester ID and generated hash to the `testers` array. Tester IDs are
   entered in lowercase by the handler.
5. Keep the real config file out of source control.
6. Confirm that PHP `mail()` is configured by the host and that PHP upload limits
   are at least `upload_max_filesize = 8M` and `post_max_size = 21M`.
7. Serve the feedback page and handler over HTTPS.

The access code is checked only by PHP. It is never included in the page source,
the Blender URL, or the feedback email.

## Blender links

Update these temporary constants before building the beta:

```python
BETA_FEEDBACK_URL = "https://scriptronaut.com/beta-feedback.html"
BETA_DOCUMENTATION_URL = "https://scriptronaut.com/docs/qc_checker/core/index.html"
```

They are located in `shared/scriptronaut_qc/constants.py`.

The feedback button prefills the product tier, QC Checker version, Blender
version, operating system, blend filename, selected category/check, and the most
recent captured Python traceback. Browsers do not permit websites to attach a
local file automatically, so the tester must explicitly choose a `.blend` or
crash-log file.

A native Blender crash may terminate the process before Python can record a
traceback. In that situation, the tester should reopen Blender, use the feedback
page, and manually attach the Blender crash log.
