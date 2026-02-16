"""Shared chart styling utilities."""

import matplotlib.pyplot as plt


def apply_dark_style(fig, ax, title=None):
    """Apply consistent dark-mode styling to a matplotlib figure."""
    ax.set_facecolor("#1e1e1e")
    fig.patch.set_facecolor("#1e1e1e")
    ax.tick_params(colors="white")
    ax.yaxis.label.set_color("white")
    ax.xaxis.label.set_color("white")
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", color="white")
    elif ax.get_title():
        ax.title.set_color("white")
    ax.spines["bottom"].set_color("white")
    ax.spines["left"].set_color("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def apply_dark_legend(ax, **kwargs):
    """Style legend for dark mode."""
    defaults = {"loc": "best", "framealpha": 0.9, "fontsize": 9}
    defaults.update(kwargs)
    legend = ax.legend(**defaults)
    legend.get_frame().set_facecolor("#2e2e2e")
    for text in legend.get_texts():
        text.set_color("white")
    return legend
