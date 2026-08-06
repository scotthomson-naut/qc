"""
Time formatting utilities.
"""


def format_elapsed_time(seconds):
    """
    Returns a human readable elapsed time.

    Examples:
        0.021   -> 0.021 sec
        8.432   -> 8.432 sec
        65.2    -> 1 min 5 sec
        152.8   -> 2 min 33 sec
        3725.1  -> 1 hr 2 min 5 sec
    """
    seconds = float(seconds)

    # Under one minute, keep the precision.
    if seconds < 60.0:
        return "{:.3f} sec".format(seconds)

    total_seconds = int(round(seconds))

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return "{} hr {} min {} sec".format(
            hours,
            minutes,
            seconds,
        )

    return "{} min {} sec".format(
        minutes,
        seconds,
    )
