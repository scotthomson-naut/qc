# QC Checker private beta feedback setup

The beta pages and the `php` handler folder are copied into `documentation/site`
whenever the documentation builder runs.

## Server setup

1. Edit `documentation/template/php/beta-feedback-config.php` before building,
   or edit `documentation/site/php/beta-feedback-config.php` on the web server.
2. Set the recipient and sender email addresses. Set `data_directory` to a
   private, writable folder outside the public website directory.
3. Create a unique access code for each tester. Generate its hash with:

   ```console
   php -r "echo password_hash('TESTER ACCESS CODE', PASSWORD_DEFAULT), PHP_EOL;"
   ```

4. Add each lowercase tester ID, name, email, and generated hash to the
   `testers` array:

   ```php
   'tester01' => [
       'name' => 'Tester Name',
       'email' => 'tester@example.com',
       'password_hash' => '$2y$10$REPLACE_WITH_A_REAL_PASSWORD_HASH',
   ],
   ```

5. Keep the real config and generated JSON files out of source control. The
   handlers create `qc_check_beta_candidates.json` and
   `qc_check_beta_feedback.json` in `data_directory`.
6. Confirm that PHP `mail()` is configured by the host and that PHP upload limits
   are at least `upload_max_filesize = 8M` and `post_max_size = 21M`.
7. Serve the feedback page and handler over HTTPS.

The access code is checked only by PHP. It is never included in the page source,
the Blender URL, or the feedback email.

Candidate records are indexed by lowercase email. Feedback is also indexed by
email when the tester configuration includes one; otherwise it uses the tester
ID. Each feedback submission is appended to that tester's `reports` array.
IP addresses are recorded from the web server.

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
