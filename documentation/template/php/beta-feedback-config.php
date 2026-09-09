<?php
declare(strict_types=1);

/*
 * Keep this file private and out of public source control.
 * Generate each tester password hashes with:
 *     php -r "echo password_hash('TESTER ACCESS CODE', PASSWORD_DEFAULT), PHP_EOL;"
 */
return [
    'recipient' => 'scot.thomson@gmail.com',
    'from' => 'website@scriptronaut.com',
    'subject_prefix' => '[QC Checker Beta]',
    'max_file_bytes' => 8 * 1024 * 1024,
    'max_total_bytes' => 20 * 1024 * 1024,
    'rate_limit_count' => 12,
    'rate_limit_window_seconds' => 3600,
    // This resolves outside documentation/site after the documentation build.
    'data_directory' => dirname(__DIR__, 2) . DIRECTORY_SEPARATOR . 'qc-checker-private-data',
    'testers' => [
        'scot' => [
            'name' => 'Scot Thomson',
            'email' => 'scot.thomson@gmail.com',
            'password_hash' => '$2y$12$sQAyQvw5p1nKpQ1IfKLFp.5a8iWaREOGOs93IPLWJUtvYOwUCQyOK',
        ],
    ],
];
