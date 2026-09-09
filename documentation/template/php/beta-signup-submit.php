<?php
declare(strict_types=1);

require_once __DIR__ . DIRECTORY_SEPARATOR . 'beta-common.php';

const SIGNUP_FIELD_LIMITS = [
    'name' => 120,
    'email' => 254,
    'blender_use' => 80,
    'blender_version' => 20,
    'website' => 200,
];

function finish_signup(bool $success, string $title, string $message): void
{
    http_response_code($success ? 200 : 400);
    $safeTitle = htmlspecialchars($title, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    $safeMessage = htmlspecialchars($message, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    $statusClass = $success ? 'beta-status-success' : 'beta-status-error';

    echo <<<HTML
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{$safeTitle} — Scriptronaut</title>
    <link rel="stylesheet" href="../css/docs.css">
</head>
<body>
    <div class="stars"></div><div class="stars stars-medium"></div><div class="stars stars-faint"></div>
    <main class="content beta-response-page">
        <section class="beta-form-card {$statusClass}">
            <h1>{$safeTitle}</h1>
            <p>{$safeMessage}</p>
            <div class="actions"><a class="button primary" href="../betas.html">Return to Beta Page</a></div>
        </section>
    </main>
</body>
</html>
HTML;
    exit;
}

function signup_value(string $name): string
{
    $value = isset($_POST[$name]) && is_string($_POST[$name]) ? trim($_POST[$name]) : '';
    if (strlen($value) > (SIGNUP_FIELD_LIMITS[$name] ?? 1000)) {
        finish_signup(false, 'Could not submit signup', 'One of the submitted fields is too long.');
    }
    return $value;
}

function enforce_signup_rate_limit(array $config): void
{
    $remoteAddress = (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown');
    $key = hash('sha256', 'qc-checker-beta-signup|' . $remoteAddress);
    $path = rtrim(sys_get_temp_dir(), DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . 'qc-beta-signup-' . $key . '.json';
    $window = max(60, (int)($config['rate_limit_window_seconds'] ?? 3600));
    $limit = max(1, (int)($config['rate_limit_count'] ?? 12));
    $now = time();
    $handle = fopen($path, 'c+');

    if ($handle === false || !flock($handle, LOCK_EX)) {
        if (is_resource($handle)) {
            fclose($handle);
        }
        return;
    }

    $stored = stream_get_contents($handle);
    $timestamps = json_decode($stored ?: '[]', true);
    if (!is_array($timestamps)) {
        $timestamps = [];
    }
    $timestamps = array_values(array_filter(
        $timestamps,
        static fn($timestamp): bool => is_int($timestamp) && $timestamp > $now - $window
    ));

    if (count($timestamps) >= $limit) {
        flock($handle, LOCK_UN);
        fclose($handle);
        finish_signup(false, 'Too many attempts', 'Please wait before submitting again.');
    }

    $timestamps[] = $now;
    rewind($handle);
    ftruncate($handle, 0);
    fwrite($handle, json_encode($timestamps));
    fflush($handle);
    flock($handle, LOCK_UN);
    fclose($handle);
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    finish_signup(false, 'Invalid request', 'Please use the signup form on the beta page.');
}

$configPath = __DIR__ . DIRECTORY_SEPARATOR . 'beta-feedback-config.php';
if (!is_file($configPath)) {
    finish_signup(false, 'Signup is not configured', 'The signup service has not been configured on this server.');
}

$config = require $configPath;
if (!is_array($config)) {
    finish_signup(false, 'Signup is not configured', 'The server configuration is invalid.');
}

enforce_signup_rate_limit($config);

if (signup_value('website') !== '') {
    finish_signup(true, 'Signup received', 'Thank you for your interest in testing QC Checker.');
}

$name = signup_value('name');
$email = signup_value('email');
$blenderUse = signup_value('blender_use');
$blenderVersion = signup_value('blender_version');

if ($name === '' || $email === '' || $blenderUse === '' || $blenderVersion === '') {
    finish_signup(false, 'Missing information', 'Complete all required fields and try again.');
}
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
    finish_signup(false, 'Invalid email', 'Enter a valid email address and try again.');
}

$allowedUses = ['VFX/Animation', 'ArchViz', 'Games', 'Freelance 3D', 'Technical Artist', 'Other'];
if (!in_array($blenderUse, $allowedUses, true)) {
    finish_signup(false, 'Invalid selection', 'Choose a valid Blender usage option.');
}
if (!preg_match('/^[0-9]+(?:\.[0-9]+){1,2}$/', $blenderVersion)) {
    finish_signup(false, 'Invalid Blender version', 'Use numbers and periods, such as 4.3 or 5.1.2.');
}

$recipient = (string)($config['recipient'] ?? '');
$from = (string)($config['from'] ?? '');
$prefix = (string)($config['subject_prefix'] ?? '[QC Checker Beta]');
if (!filter_var($recipient, FILTER_VALIDATE_EMAIL) || !filter_var($from, FILTER_VALIDATE_EMAIL)) {
    finish_signup(false, 'Signup is not configured', 'The server email configuration is invalid.');
}

$safeName = preg_replace('/[\r\n]+/', ' ', $name);
$safeEmail = preg_replace('/[\r\n]+/', '', $email);
$subject = preg_replace('/[\r\n]+/', ' ', $prefix . ' Signup: ' . $safeName);
$submittedAt = gmdate('c');
$ipAddress = beta_client_ip();
$candidate = [
    'name' => $name,
    'email' => strtolower($email),
    'blender_use' => $blenderUse,
    'blender_version' => $blenderVersion,
    'ip_address' => $ipAddress,
    'submitted_utc' => $submittedAt,
];
try {
    $candidatePath = beta_data_path($config, 'qc_check_beta_candidates.json');
    beta_update_json($candidatePath, static function (array $data) use ($candidate): array {
        $data[$candidate['email']] = $candidate;
        ksort($data, SORT_NATURAL | SORT_FLAG_CASE);
        return $data;
    });
} catch (Throwable $error) {
    error_log('QC beta signup storage error: ' . $error->getMessage());
    finish_signup(false, 'Could not save signup', 'The server could not save your signup. Please try again later.');
}
$message = implode("\r\n", [
    'QC Checker beta signup',
    'Submitted UTC: ' . $submittedAt,
    '',
    'Name: ' . $name,
    'Email: ' . $email,
    'Main Blender use: ' . $blenderUse,
    'Blender version: ' . $blenderVersion,
    'IP address: ' . $ipAddress,
]);
$orange = '#ffc18f';
$blue = '#c9e5f7';
$htmlMessage = beta_email_document(
    '<tr>' . beta_email_cell('Name', $name, $orange)
    . beta_email_cell('Main Blender use', $blenderUse, $blue) . '</tr>'
    . '<tr>' . beta_email_cell('Email', $email, $orange)
    . beta_email_cell('Blender version', $blenderVersion, $blue) . '</tr>'
);
try {
    $sent = beta_send_alternative_email(
        $recipient, $from, $safeEmail, $subject, $message, $htmlMessage
    );
} catch (Throwable $error) {
    error_log('QC beta signup email error: ' . $error->getMessage());
    $sent = false;
}
if (!$sent) {
    finish_signup(false, 'Could not send signup', 'The server could not send your signup. Please try again later.');
}

finish_signup(true, 'Signup received', 'Thank you. We will contact you at the email address you provided.');
