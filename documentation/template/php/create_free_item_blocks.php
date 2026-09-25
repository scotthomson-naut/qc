<?php
/** Scriptronaut Free Item Block Generator */

function scriptronaut_parse_free_item_file($txt_file)
{
    $data = array('description' => '', 'group' => '');
    $contents = @file_get_contents($txt_file);
    if ($contents === false) return $data;

    $contents = str_replace(array("\r\n", "\r"), "\n", $contents);
    $current_key = '';

    foreach (explode("\n", $contents) as $line) {
        $trimmed = trim($line);
        if (preg_match('/^description\s*:\s*(.*)$/i', $line, $m)) {
            $current_key = 'description';
            $data['description'] = trim($m[1]);
            continue;
        }
        if (preg_match('/^group\s*:\s*(.*)$/i', $line, $m)) {
            $current_key = 'group';
            $data['group'] = trim($m[1]);
            continue;
        }
        if ($trimmed === '') continue;
        if ($current_key === 'description') {
            if ($data['description'] !== '') $data['description'] .= "\n";
            $data['description'] .= $trimmed;
        } elseif ($current_key === 'group' && $data['group'] === '') {
            $data['group'] = $trimmed;
        }
    }
    return $data;
}

function scriptronaut_free_item_display_name($filename)
{
    $name = str_replace(array('_', '-'), ' ', $filename);
    $name = preg_replace('/\s+/', ' ', $name);
    return ucwords(trim($name));
}

function scriptronaut_create_free_item_blocks()
{
    $template_dir = dirname(__DIR__);
    $items_dir = $template_dir . '/free_items';
    if (!is_dir($items_dir)) return '<!-- free_items folder not found. -->';

    $txt_files = glob($items_dir . '/*.txt');
    if (!$txt_files) return '<!-- No free items found. -->';
    natcasesort($txt_files);
    $blocks = array();

    foreach ($txt_files as $txt_file) {
        $filename = pathinfo($txt_file, PATHINFO_FILENAME);
        if (!preg_match('/^[A-Za-z0-9_-]+$/', $filename)) continue;

        $zip_file = $items_dir . '/' . $filename . '.zip';
        $png_file = $items_dir . '/' . $filename . '.png';
        $gif_file = $items_dir . '/' . $filename . '.gif';
        $image_extension = is_file($png_file) ? 'png' : (is_file($gif_file) ? 'gif' : '');

        // The .txt is discovered first, but only complete item sets are rendered.
        if (!is_file($zip_file) || $image_extension === '') continue;

        $item = scriptronaut_parse_free_item_file($txt_file);
        if ($item['description'] === '' || $item['group'] === '') continue;

        $group = strtolower(trim($item['group']));
        $group = preg_replace('/[^a-z0-9_-]/', '', $group);
        if ($group === '') continue;

        $display_name = scriptronaut_free_item_display_name($filename);
        $safe_name = htmlspecialchars($display_name, ENT_QUOTES, 'UTF-8');
        $safe_description = nl2br(htmlspecialchars($item['description'], ENT_QUOTES, 'UTF-8'));
        $safe_group = htmlspecialchars($group, ENT_QUOTES, 'UTF-8');
        $safe_filename = rawurlencode($filename);

        $image_url = 'free_items/' . $safe_filename . '.' . $image_extension;
        $zip_url = 'free_items/' . $safe_filename . '.zip';
        $group_url = 'svg/group_' . rawurlencode($group) . '.svg';

        $blocks[] =
            '                    <!-- Item: ' . $safe_name . ' -->' . "\n" .
            '                    <article class="detail-card product-benefit">' . "\n" .
            '                        <h2>' . "\n" .
            '                            ' . $safe_name . "\n" .
            '                            <img class="i-orange" src="' . $group_url . '" alt="Scriptronaut ' . $safe_group . '" />' . "\n" .
            '                        </h2>' . "\n" .
            '                        <div class="story-image-col">' . "\n" .
            '                            <img src="' . $image_url . '" alt="' . $safe_name . '">' . "\n" .
            '                        </div>' . "\n" .
            '                        <p>' . "\n" .
            '                            ' . $safe_description . "\n" .
            '                        </p>' . "\n" .
            '                        <div class="actions">' . "\n" .
            '                            <a class="button primary" href="' . $zip_url . '" download>' . "\n" .
            '                                Download' . "\n" .
            '                            </a>' . "\n" .
            '                        </div>' . "\n" .
            '                    </article>';
    }

    if (!$blocks) return '<!-- No complete free items found. Each item needs matching .txt, .zip and .png/.gif files. -->';
    return implode("\n\n", $blocks);
}
