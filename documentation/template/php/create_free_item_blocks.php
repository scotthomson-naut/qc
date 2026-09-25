<?php
/** Scriptronaut Free Item Block + CSS-only Filter Generator */

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

function scriptronaut_free_group_display_name($group)
{
    $name = str_replace(array('_', '-'), ' ', $group);
    $name = preg_replace('/\s+/', ' ', $name);
    return ucwords(trim($name));
}

function scriptronaut_create_free_item_blocks()
{
    $template_dir = dirname(__DIR__);
    $items_dir = $template_dir . '/free_items';

    if (!is_dir($items_dir)) {
        return '<!-- free_items folder not found. -->';
    }

    $txt_files = glob($items_dir . '/*.txt');
    if (!$txt_files) {
        return '<!-- No free items found. -->';
    }

    natcasesort($txt_files);

    $items = array();
    $groups = array();

    // First collect only complete/valid items.
    foreach ($txt_files as $txt_file) {
        $filename = pathinfo($txt_file, PATHINFO_FILENAME);
        if (!preg_match('/^[A-Za-z0-9_-]+$/', $filename)) continue;

        $zip_file = $items_dir . '/' . $filename . '.zip';
        $png_file = $items_dir . '/' . $filename . '.png';
        $gif_file = $items_dir . '/' . $filename . '.gif';
        $image_extension = is_file($png_file) ? 'png' : (is_file($gif_file) ? 'gif' : '');

        if (!is_file($zip_file) || $image_extension === '') continue;

        $item_data = scriptronaut_parse_free_item_file($txt_file);
        if ($item_data['description'] === '' || $item_data['group'] === '') continue;

        $group = strtolower(trim($item_data['group']));
        $group = preg_replace('/[^a-z0-9_-]/', '', $group);
        if ($group === '') continue;

        $items[] = array(
            'filename' => $filename,
            'image_extension' => $image_extension,
            'description' => $item_data['description'],
            'group' => $group,
        );

        $groups[$group] = true;
    }

    if (!$items) {
        return '<!-- No complete free items found. Each item needs matching .txt, .zip and .png/.gif files. -->';
    }

    $group_names = array_keys($groups);
    natcasesort($group_names);
    $group_names = array_values($group_names);
    $show_filters = count($group_names) > 1;

    // Indentation begins at 16 spaces because this output is inserted inside
    // <section class="product-section free-items-section"> in free.html.
    $html = array();
    $html[] = '                <div class="free-items-browser">';

    if ($show_filters) {
        // Keep all essential filter CSS inline so the feature does not depend on cached docs.css.
        $html[] = '                    <style>';
        $html[] = '                        .free-filter-radio { display: none !important; }';
        $html[] = '                        .free-filter-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 14px; margin: 0 0 26px; }';
        $html[] = '                        .free-filter-button { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; padding: 0; border: 0; border-radius: 0; background: transparent; cursor: pointer; user-select: none; }';
        $html[] = '                        .free-filter-button img { display: block; width: 32px; height: 32px; object-fit: contain; transition: filter .15s ease, opacity .15s ease; }';
        $html[] = '                        .free-filter-button:hover img { filter: brightness(0) saturate(100%) invert(60%) sepia(72%) saturate(1794%) hue-rotate(340deg) brightness(100%) contrast(98%); }';
        $html[] = '                        .free-filter-button.is-placeholder { display: none; }';
        $html[] = '                    </style>';
        $html[] = '';
        $html[] = '                    <input class="free-filter-radio" type="radio" name="free-item-filter" id="free-filter-all" checked>';

        foreach ($group_names as $group) {
            $safe_id = htmlspecialchars($group, ENT_QUOTES, 'UTF-8');
            $html[] = '                    <input class="free-filter-radio" type="radio" name="free-item-filter" id="free-filter-' . $safe_id . '">';
        }

        $html[] = '';
        $html[] = '                    <div class="free-filter-bar" aria-label="Filter free items">';
        $html[] = '                        <label class="free-filter-button" for="free-filter-all" title="Show all" aria-label="Show all">';
        $html[] = '                            <img src="svg/group_all.svg" alt="">';
        $html[] = '                        </label>';

        foreach ($group_names as $group) {
            $safe_group = htmlspecialchars($group, ENT_QUOTES, 'UTF-8');
            $label = htmlspecialchars(scriptronaut_free_group_display_name($group), ENT_QUOTES, 'UTF-8');
            $group_url = 'svg/group_' . rawurlencode($group) . '.svg';

            $html[] = '                        <label class="free-filter-button" for="free-filter-' . $safe_group . '" title="' . $label . '" aria-label="' . $label . '">';
            $html[] = '                            <img src="' . $group_url . '" alt="">';
            $html[] = '                        </label>';
        }

        $html[] = '                    </div>';
        $html[] = '';
        $html[] = '                    <style>';
        foreach ($group_names as $group) {
            $safe_group = htmlspecialchars($group, ENT_QUOTES, 'UTF-8');
            $html[] = '                        #free-filter-' . $safe_group . ':checked ~ .free-items-grid .free-item:not(.group-' . $safe_group . ') { display: none; }';
            $html[] = '                        #free-filter-' . $safe_group . ':checked ~ .free-filter-bar label[for="free-filter-' . $safe_group . '"] img { filter: brightness(0) saturate(100%) invert(60%) sepia(72%) saturate(1794%) hue-rotate(340deg) brightness(100%) contrast(98%); }';
        }
        $html[] = '                        #free-filter-all:checked ~ .free-filter-bar label[for="free-filter-all"] img { filter: brightness(0) saturate(100%) invert(60%) sepia(72%) saturate(1794%) hue-rotate(340deg) brightness(100%) contrast(98%); }';
        $html[] = '                    </style>';
        $html[] = '';
    }

    $html[] = '                    <div class="grid free-items-grid">';

    foreach ($items as $item) {
        $filename = $item['filename'];
        $group = $item['group'];
        $image_extension = $item['image_extension'];

        $display_name = scriptronaut_free_item_display_name($filename);
        $safe_name = htmlspecialchars($display_name, ENT_QUOTES, 'UTF-8');
        $safe_description = nl2br(htmlspecialchars($item['description'], ENT_QUOTES, 'UTF-8'));
        $safe_group = htmlspecialchars($group, ENT_QUOTES, 'UTF-8');
        $safe_filename = rawurlencode($filename);

        $image_url = 'free_items/' . $safe_filename . '.' . $image_extension;
        $zip_url = 'free_items/' . $safe_filename . '.zip';
        $group_url = 'svg/group_' . rawurlencode($group) . '.svg';

        $html[] = '';
        $html[] = '                        <!-- Item: ' . $safe_name . ' -->';
        $html[] = '                        <article class="detail-card product-benefit free-item group-' . $safe_group . '">';
        $html[] = '                            <h2>';
        $html[] = '                                ' . $safe_name;
        $html[] = '                                <img class="i-orange" src="' . $group_url . '" alt="Scriptronaut ' . $safe_group . '" />';
        $html[] = '                            </h2>';
        $html[] = '                            <div class="story-image-col">';
        $html[] = '                                <img src="' . $image_url . '" alt="' . $safe_name . '">';
        $html[] = '                            </div>';
        $html[] = '                            <p>' . $safe_description . '</p>';
        $html[] = '                            <div class="actions">';
        $html[] = '                                <a class="button primary" href="' . $zip_url . '" download>Download</a>';
        $html[] = '                            </div>';
        $html[] = '                        </article>';
    }

    $html[] = '';
    $html[] = '                    </div>';
    $html[] = '                </div>';

    return implode("\n", $html);
}
