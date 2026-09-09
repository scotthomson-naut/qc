<?php
declare(strict_types=1);

require_once __DIR__ . DIRECTORY_SEPARATOR . 'beta-common.php';

const ALLOWED_EXTENSIONS = ['blend', 'txt', 'log', 'png', 'jpg', 'jpeg', 'zip'];
const MAX_FIELD_LENGTHS = [
    'tester_id' => 80,
    'report_type' => 40,
    'tier' => 40,
    'category' => 80,
    'check_name' => 180,
    'check_id' => 180,
    'summary' => 180,
    'details' => 12000,
    'steps' => 8000,
    'expected_result' => 4000,
    'actual_result' => 4000,
    'qc_version' => 40,
    'blender_version' => 80,
    'operating_system' => 240,
    'blend_filename' => 255,
    'traceback' => 30000,
    'traceback_time' => 80,
    'source' => 40,
];

function finish_page(bool $success, string $title, string $message)
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
            <div class="actions"><a class="button primary" href="../beta-feedback.html">Return to Feedback</a></div>
        </section>
    </main>
</body>
</html>
HTML;
    exit;
}

function post_value(string $name): string
{
    $value = isset($_POST[$name]) && is_string($_POST[$name]) ? trim($_POST[$name]) : '';
    $limit = MAX_FIELD_LENGTHS[$name] ?? 1000;
    if (strlen($value) > $limit) {
        finish_page(false, 'Could not send feedback', "The {$name} field is too long.");
    }
    return $value;
}

function enforce_rate_limit(array $config): void
{
    $remoteAddress = (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown');
    $key = hash('sha256', 'qc-checker-beta|' . $remoteAddress);
    $path = rtrim(sys_get_temp_dir(), DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . 'qc-beta-' . $key . '.json';
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
        finish_page(false, 'Too many attempts', 'Please wait before submitting another report.');
    }

    $timestamps[] = $now;
    rewind($handle);
    ftruncate($handle, 0);
    fwrite($handle, json_encode($timestamps));
    fflush($handle);
    flock($handle, LOCK_UN);
    fclose($handle);
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    finish_page(false, 'Invalid request', 'Please submit feedback using the feedback form.');
}

$configPath = __DIR__ . DIRECTORY_SEPARATOR . 'beta-feedback-config.php';
if (!is_file($configPath)) {
    finish_page(false, 'Feedback is not configured', 'The feedback service has not been configured on this server.');
}

$config = require $configPath;
if (!is_array($config)) {
    finish_page(false, 'Feedback is not configured', 'The server configuration is invalid.');
}

enforce_rate_limit($config);

if (post_value('website') !== '') {
    finish_page(true, 'Feedback received', 'Thank you for helping test QC Checker.');
}

$testerId = strtolower(post_value('tester_id'));
$accessCode = isset($_POST['access_code']) && is_string($_POST['access_code']) ? $_POST['access_code'] : '';
$testers = isset($config['testers']) && is_array($config['testers']) ? $config['testers'] : [];
$testerEntry = $testers[$testerId] ?? '';
$passwordHash = is_array($testerEntry)
    ? (string)($testerEntry['password_hash'] ?? '')
    : (string)$testerEntry;
$testerName = is_array($testerEntry) ? trim((string)($testerEntry['name'] ?? '')) : '';
$testerEmail = is_array($testerEntry) ? strtolower(trim((string)($testerEntry['email'] ?? ''))) : '';

if (!is_string($passwordHash) || $passwordHash === '' || !password_verify($accessCode, $passwordHash)) {
    usleep(350000);
    finish_page(false, 'Access not recognized', 'Check your tester ID and access code, then try again.');
}

$reportType = post_value('report_type');
$tier = post_value('tier');
$summary = post_value('summary');
$details = post_value('details');

if ($reportType === '' || $tier === '' || $summary === '' || $details === '') {
    finish_page(false, 'Missing information', 'Report type, product, summary, and details are required.');
}

if ($tier !== 'Core') {
    finish_page(false, 'Invalid product', 'QC Checker Core is the only product currently available for beta feedback.');
}

$fields = [];
foreach (array_keys(MAX_FIELD_LENGTHS) as $fieldName) {
    if ($fieldName !== 'tester_id') {
        $fields[$fieldName] = post_value($fieldName);
    }
}

if ($reportType === 'check_issue' && ($fields['category'] === '' || $fields['check_name'] === '')) {
    finish_page(false, 'Missing check', 'Choose the category and check that had the issue.');
}

$files = $_FILES['attachments'] ?? null;
$attachments = [];
$totalBytes = 0;
$maxFileBytes = (int)($config['max_file_bytes'] ?? 8 * 1024 * 1024);
$maxTotalBytes = (int)($config['max_total_bytes'] ?? 20 * 1024 * 1024);

if (is_array($files) && isset($files['name']) && is_array($files['name'])) {
    if (post_value('upload_confirmation') !== 'yes') {
        $hasUpload = array_filter($files['name'], static fn($name): bool => is_string($name) && $name !== '');
        if ($hasUpload) {
            finish_page(false, 'Upload confirmation required', 'Confirm that you are permitted to send the selected files.');
        }
    }

    foreach ($files['name'] as $index => $originalName) {
        $error = (int)($files['error'][$index] ?? UPLOAD_ERR_NO_FILE);
        if ($error === UPLOAD_ERR_NO_FILE) {
            continue;
        }
        if ($error !== UPLOAD_ERR_OK) {
            finish_page(false, 'Upload failed', 'One of the selected files could not be uploaded.');
        }

        $safeName = basename((string)$originalName);
        $extension = strtolower(pathinfo($safeName, PATHINFO_EXTENSION));
        $size = (int)($files['size'][$index] ?? 0);
        $temporaryPath = (string)($files['tmp_name'][$index] ?? '');

        if (!in_array($extension, ALLOWED_EXTENSIONS, true)) {
            finish_page(false, 'Unsupported file', "The file {$safeName} is not an allowed file type.");
        }
        if ($size <= 0 || $size > $maxFileBytes || !is_uploaded_file($temporaryPath)) {
            finish_page(false, 'Upload too large', "The file {$safeName} exceeds the upload limit or is invalid.");
        }

        $totalBytes += $size;
        if ($totalBytes > $maxTotalBytes) {
            finish_page(false, 'Uploads too large', 'The combined upload exceeds the total size limit.');
        }

        $attachments[] = [
            'name' => preg_replace('/[^A-Za-z0-9._-]/', '_', $safeName) ?: 'attachment',
            'path' => $temporaryPath,
            'type' => 'application/octet-stream',
        ];
    }
}

$labels = [
    'report_type' => 'Report type', 'tier' => 'Product', 'category' => 'Category',
    'check_name' => 'Check', 'check_id' => 'Check ID', 'summary' => 'Summary',
    'details' => 'Details', 'steps' => 'Steps to reproduce',
    'expected_result' => 'Expected result', 'actual_result' => 'Actual result',
    'qc_version' => 'QC Checker version', 'blender_version' => 'Blender version',
    'operating_system' => 'Operating system', 'blend_filename' => 'Blend filename',
    'traceback' => 'Traceback / console output', 'traceback_time' => 'Traceback recorded at',
    'source' => 'Opened from',
];

$submittedAt = gmdate('c');
$ipAddress = beta_client_ip();
$bodyLines = [
    'QC Checker private beta feedback',
    'Tester ID: ' . $testerId,
    'Submitted UTC: ' . $submittedAt,
    '',
];

foreach ($labels as $fieldName => $label) {
    $value = $fields[$fieldName] ?? '';
    if ($value !== '') {
        $bodyLines[] = $label . ':';
        $bodyLines[] = $value;
        $bodyLines[] = '';
    }
}

$bodyLines[] = 'IP address:';
$bodyLines[] = $ipAddress;

$report = [
    'submitted_utc' => $submittedAt, 'tester_id' => $testerId,
    'type' => $reportType, 'product' => $tier,
    'category' => $fields['category'], 'check' => $fields['check_name'],
    'check_id' => $fields['check_id'], 'summary' => $summary, 'details' => $details,
    'steps_to_reproduce' => $fields['steps'], 'expected_result' => $fields['expected_result'],
    'actual_result' => $fields['actual_result'], 'qc_checker_version' => $fields['qc_version'],
    'blender_version' => $fields['blender_version'], 'operating_system' => $fields['operating_system'],
    'blend_filename' => $fields['blend_filename'], 'traceback' => $fields['traceback'],
    'traceback_time' => $fields['traceback_time'], 'opened_from' => $fields['source'],
    'attachments' => array_values(array_map(
        static fn(array $attachment): string => (string)$attachment['name'], $attachments
    )),
    'ip_address' => $ipAddress,
];
$recordKey = $testerEmail !== '' ? $testerEmail : $testerId;
try {
    $feedbackPath = beta_data_path($config, 'qc_check_beta_feedback.json');
    beta_update_json($feedbackPath, static function (array $data) use (
        $recordKey, $testerId, $testerName, $testerEmail, $report
    ): array {
        $tester = isset($data[$recordKey]) && is_array($data[$recordKey]) ? $data[$recordKey] : [];
        $tester['tester_id'] = $testerId;
        $tester['name'] = $testerName;
        $tester['email'] = $testerEmail;
        $tester['reports'] = isset($tester['reports']) && is_array($tester['reports'])
            ? $tester['reports'] : [];
        $tester['reports'][] = $report;
        $data[$recordKey] = $tester;
        ksort($data, SORT_NATURAL | SORT_FLAG_CASE);
        return $data;
    });
} catch (Throwable $error) {
    error_log('QC beta feedback storage error: ' . $error->getMessage());
    finish_page(false, 'Could not save feedback', 'The server could not save your report. Please try again later.');
}

$recipient = (string)($config['recipient'] ?? '');
$from = (string)($config['from'] ?? '');
$prefix = (string)($config['subject_prefix'] ?? '[QC Checker Beta]');
if (!filter_var($recipient, FILTER_VALIDATE_EMAIL) || !filter_var($from, FILTER_VALIDATE_EMAIL)) {
    finish_page(false, 'Feedback is not configured', 'The server email configuration is invalid.');
}

$subjectText = preg_replace('/[\r\n]+/', ' ', $prefix . ' ' . $reportType . ': ' . $summary);
$value = static fn(string $field): string => ($fields[$field] ?? '') !== '' ? $fields[$field] : '—';
$orange = '#ffc18f'; $warm = '#f4ece6'; $blue = '#c9e5f7';
$htmlMessage = beta_email_document(
    '<tr>' . beta_email_cell('Tester ID', $testerId, $orange)
    . beta_email_cell('Submitted', gmdate('l, jS F Y @ g:ia') . ' UTC', $orange) . '</tr>'
    . '<tr><td colspan="2" style="padding:8px 10px;background:' . $warm
    . ';font:700 20px Arial,sans-serif;color:#171717;">Product Report</td></tr>'
    . '<tr>' . beta_email_cell('Product', ucfirst($tier), $warm)
    . beta_email_cell('QC Checker version', $value('qc_version'), $warm) . '</tr>'
    . '<tr>' . beta_email_cell('Report type', $reportType, $warm, 2) . '</tr>'
    . '<tr>' . beta_email_cell('Category', $value('category'), $warm, 2) . '</tr>'
    . '<tr>' . beta_email_cell('Check', $value('check_name'), $warm)
    . beta_email_cell('Check ID', $value('check_id'), $warm) . '</tr>'
    . '<tr>' . beta_email_cell('Summary', $summary, $warm, 2) . '</tr>'
    . '<tr>' . beta_email_cell('Details', $details, $warm, 2) . '</tr>'
    . '<tr>' . beta_email_cell('Steps to reproduce', $value('steps'), $warm, 2) . '</tr>'
    . '<tr>' . beta_email_cell('Expected result', $value('expected_result'), $warm)
    . beta_email_cell('Actual result', $value('actual_result'), $warm) . '</tr>'
    . '<tr>' . beta_email_cell('Blend filename', $value('blend_filename'), $warm, 2) . '</tr>'
    . '<tr>' . beta_email_cell('Traceback / console output', $value('traceback'), $warm, 2) . '</tr>'
    . '<tr><td colspan="2" style="padding:8px 10px;background:' . $blue
    . ';font:700 20px Arial,sans-serif;color:#171717;">Software</td></tr>'
    . '<tr>' . beta_email_cell('Blender version', $value('blender_version'), $blue)
    . beta_email_cell('Operating system', $value('operating_system'), $blue) . '</tr>'
    . '<tr>' . beta_email_cell('Opened from', $value('source'), $blue, 2) . '</tr>'
);
$replyTo = filter_var($testerEmail, FILTER_VALIDATE_EMAIL) ? $testerEmail : $from;
try {
    $sent = beta_send_alternative_email(
        $recipient, $from, $replyTo, $subjectText,
        implode("\r\n", $bodyLines), $htmlMessage, $attachments
    );
} catch (Throwable $error) {
    error_log('QC beta feedback email error: ' . $error->getMessage());
    $sent = false;
}
if (!$sent) {
    finish_page(false, 'Could not send feedback', 'The mail server did not accept the report. Please contact Scriptronaut directly.');
}

finish_page(true, 'Feedback sent', 'Thank you. Your report has been sent to the QC Checker beta team.');
