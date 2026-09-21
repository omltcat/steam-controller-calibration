"""Named colors shared by the Steam Controller calibration interface."""


class Theme:
    """Keep the complete visual palette in one place for easy retheming."""

    CANVAS_BACKGROUND = '#fafafa'
    ACCENT = '#1677c8'
    HYPERLINK = '#0563c1'
    MUTED_TEXT = '#666666'

    STICK_BORDER = '#a8a8a8'
    STICK_GUIDE = '#dedede'
    STICK_MARKER_WIDTH = 3

    PLOT_BORDER = '#c8c8c8'
    PLOT_FRAME = '#d0d0d0'
    PLOT_ZERO_LINE = '#a8a8a8'
    PLOT_GRID = '#ececec'

    STATUS_TONES = {
        'normal': ('#e8eef5', '#243447'),
        'hold': ('#fff0bd', '#713f12'),
        'move': ('#dcfce7', '#166534'),
        'stop': ('#fee2e2', '#991b1b'),
        'success': ('#dcfce7', '#166534'),
        'error': ('#fee2e2', '#991b1b'),
    }

    WINDOW_WIDTH = 850
    WINDOW_HEIGHT = 765

