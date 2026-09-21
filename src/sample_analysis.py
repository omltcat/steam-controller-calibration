"""Statistics shared by the command-line and GUI calibration workflows."""
import statistics

from .protocol import AXES


def summarize(values):
    """Summarize one list of processed controller samples for each stick axis."""
    if any(not values[axis] for axis in AXES):
        raise RuntimeError('No supported stick reports arrived from the controller')
    return {axis: dict(minimum=min(items), maximum=max(items),
                       median=statistics.median(items),
                       peak_to_peak=max(items) - min(items), samples=len(items))
            for axis, items in values.items()}
