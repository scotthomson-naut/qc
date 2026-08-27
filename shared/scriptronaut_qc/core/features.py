"""Runtime registry for optional Scriptronaut QC product features."""

_FEATURES = {}


def register_feature(
        feature_id,
        *,
        enabled_callback=None,
        draw_callback=None,
    ):
    feature_id = str(feature_id).strip()

    if not feature_id:
        raise ValueError("feature_id cannot be empty.")

    _FEATURES[feature_id] = {
        "enabled_callback": enabled_callback,
        "draw_callback": draw_callback,
    }


def unregister_feature(
        feature_id,
    ):
    _FEATURES.pop(
        str(feature_id),
        None,
    )


def has_feature(
        feature_id,
    ):
    return str(feature_id) in _FEATURES


def is_feature_enabled(
        feature_id,
        context=None,
    ):
    feature = _FEATURES.get(
        str(feature_id)
    )

    if feature is None:
        return False

    callback = feature.get(
        "enabled_callback"
    )

    if callback is None:
        return True

    try:
        return bool(
            callback(
                context
            )
        )
    except Exception as error:
        print(
            "Scriptronaut QC feature '{}' enabled callback failed: {}".format(
                feature_id,
                error,
            )
        )
        return False


def draw_feature(
        feature_id,
        layout,
        context,
    ):
    feature = _FEATURES.get(
        str(feature_id)
    )

    if feature is None:
        return False

    callback = feature.get(
        "draw_callback"
    )

    if callback is None:
        return False

    try:
        callback(
            layout,
            context,
        )
        return True

    except Exception as error:
        print(
            "Scriptronaut QC feature '{}' draw callback failed: {}".format(
                feature_id,
                error,
            )
        )
        return False
