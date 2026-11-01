"""Keep Tk's point-sized fonts and pixel-sized layout at the same display scale."""

import ctypes
import sys


def enable_dpi_awareness():
    """Request Windows system DPI awareness before creating the first Tk window.

    Respect awareness already selected by the executable or host. System awareness
    lets Windows handle moves between monitors without requiring Tk 8.6 widgets
    to resize dynamically.
    """
    if sys.platform != 'win32':
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        # Windows versions before 8.1 expose only the older system-aware API.
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


class DisplayScale:
    """Convert layout distances from 96-DPI design pixels to Tk display pixels."""

    def __init__(self, widget):
        """Read the font scale from a Tk widget, leaving point-sized fonts intact."""
        self.factor = float(widget.tk.call('tk', 'scaling')) * 72 / 96

    def pixels(self, value):
        """Return a scaled integer distance, or tuple of distances, for value.

        Positive distances retain at least one pixel so borders stay visible.
        Tuple input supports Tk's asymmetric padding options.
        """
        if isinstance(value, tuple):
            return tuple(self.pixels(item) for item in value)
        return max(1, round(value * self.factor)) if value > 0 else round(value * self.factor)
