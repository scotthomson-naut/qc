<?php
declare(strict_types=1);

function beta_html(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function beta_client_ip(): string
{
    return trim((string)($_SERVER['REMOTE_ADDR'] ?? 'unknown'));
}

function beta_data_path(array $config, string $filename): string
{
    $directory = trim((string)($config['data_directory'] ?? ''));
    if ($directory === '') {
        throw new RuntimeException('The private data directory is not configured.');
    }
    if (!is_dir($directory) && !mkdir($directory, 0700, true) && !is_dir($directory)) {
        throw new RuntimeException('The private data directory could not be created.');
    }
    if (!is_writable($directory)) {
        throw new RuntimeException('The private data directory is not writable.');
    }
    return rtrim($directory, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . $filename;
}

function beta_update_json(string $path, callable $update): void
{
    $handle = fopen($path, 'c+');
    if ($handle === false || !flock($handle, LOCK_EX)) {
        if (is_resource($handle)) {
            fclose($handle);
        }
        throw new RuntimeException('The data file could not be locked.');
    }

    try {
        $contents = stream_get_contents($handle);
        $data = json_decode($contents ?: '{}', true);
        if (!is_array($data)) {
            throw new RuntimeException('The data file does not contain valid JSON.');
        }

        $updated = $update($data);
        if (!is_array($updated)) {
            throw new RuntimeException('The data update was invalid.');
        }

        $json = json_encode(
            $updated,
            JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR
        ) . PHP_EOL;
        rewind($handle);
        if (!ftruncate($handle, 0) || fwrite($handle, $json) === false) {
            throw new RuntimeException('The data file could not be written.');
        }
        fflush($handle);
        @chmod($path, 0600);
    } finally {
        flock($handle, LOCK_UN);
        fclose($handle);
    }
}

function beta_email_cell(string $label, string $value, string $background, int $colspan = 1): string
{
    $safeLabel = beta_html($label);
    $safeValue = nl2br(beta_html($value));
    $width = $colspan > 1 ? '100%' : '50%';
    return '<td colspan="' . $colspan . '" style="width:' . $width . ';padding:9px;border:0;'
        . 'vertical-align:top;background:' . $background . ';font-family:Arial,sans-serif;font-size:14px;color:#171717;">'
        . '<strong>' . $safeLabel . ':</strong><br><span style="color:#1c3478;">' . $safeValue . '</span></td>';
}

function beta_email_document(string $content): string
{
    return '<!doctype html><html><body style="margin:0;padding:20px;background:#ffffff;">'
        . '<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;max-width:680px;'
        . 'margin:0 auto;border-collapse:separate;border-spacing:0;border-radius:16px;overflow:hidden;">'
        . $content . '</table></body></html>';
}

function beta_send_alternative_email(
    string $recipient,
    string $from,
    string $replyTo,
    string $subject,
    string $plainText,
    string $html,
    array $attachments = []
): bool {
    $alternativeBoundary = 'qc-beta-alt-' . bin2hex(random_bytes(18));
    $headers = [
        'From: ' . $from,
        'Reply-To: ' . $replyTo,
        'MIME-Version: 1.0',
    ];

    $alternativeMessage = '--' . $alternativeBoundary . "\r\n";
    $alternativeMessage .= "Content-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n";
    $alternativeMessage .= quoted_printable_encode($plainText) . "\r\n";
    $alternativeMessage .= '--' . $alternativeBoundary . "\r\n";
    $alternativeMessage .= "Content-Type: text/html; charset=UTF-8\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n";
    $alternativeMessage .= quoted_printable_encode($html) . "\r\n";
    $alternativeMessage .= '--' . $alternativeBoundary . "--\r\n";

    if ($attachments === []) {
        $headers[] = 'Content-Type: multipart/alternative; boundary="' . $alternativeBoundary . '"';
        return mail($recipient, $subject, $alternativeMessage, implode("\r\n", $headers));
    }

    $mixedBoundary = 'qc-beta-mixed-' . bin2hex(random_bytes(18));
    $headers[] = 'Content-Type: multipart/mixed; boundary="' . $mixedBoundary . '"';
    $message = '--' . $mixedBoundary . "\r\n";
    $message .= 'Content-Type: multipart/alternative; boundary="' . $alternativeBoundary . "\"\r\n\r\n";
    $message .= $alternativeMessage;

    foreach ($attachments as $attachment) {
        $contents = file_get_contents((string)$attachment['path']);
        if ($contents === false) {
            throw new RuntimeException('An attachment could not be read.');
        }
        $name = (string)$attachment['name'];
        $type = (string)($attachment['type'] ?? 'application/octet-stream');
        $message .= '--' . $mixedBoundary . "\r\n";
        $message .= 'Content-Type: ' . $type . '; name="' . $name . "\"\r\n";
        $message .= "Content-Transfer-Encoding: base64\r\n";
        $message .= 'Content-Disposition: attachment; filename="' . $name . "\"\r\n\r\n";
        $message .= chunk_split(base64_encode($contents)) . "\r\n";
    }
    $message .= '--' . $mixedBoundary . "--\r\n";

    return mail($recipient, $subject, $message, implode("\r\n", $headers));
}
