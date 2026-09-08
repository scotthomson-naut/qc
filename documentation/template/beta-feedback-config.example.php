<?php
declare(strict_types=1);

/*
 * Copy this file to beta-feedback-config.php on the web server.
 * Keep the real config out of source control and do not make it downloadable.
 * Generate each hash with:
 *     php -r "echo password_hash('TESTER ACCESS CODE', PASSWORD_DEFAULT), PHP_EOL;"
 *    'recipient' => 'beta@scriptronaut.com',
 *            // 'tester-id' => '$2y$10$REPLACE_WITH_A_REAL_PASSWORD_HASH',
*/
return [
    'recipient' => 'scot.thomson@gmail.com',
    'from' => 'website@scriptronaut.com',
    'subject_prefix' => '[QC Checker Beta]',
    'max_file_bytes' => 8 * 1024 * 1024,
    'max_total_bytes' => 20 * 1024 * 1024,
    'rate_limit_count' => 12,
    'rate_limit_window_seconds' => 3600,
    'testers' => [
        'Scot' => '$2y$12$sQAyQvw5p1nKpQ1IfKLFp.5a8iWaREOGOs93IPLWJUtvYOwUCQyOK',
    ],
];
