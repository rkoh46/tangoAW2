"""The Dual Strike look settings a run is made with (TANGOAW2_DS_GRAPHICS, TANGOAW2_TILT):
tests that check pixels against AW2's own art read them, as test_ds_hud.py does, and check the
Dual Strike equivalent instead when the look is on. Game-state checks never depend on them."""

import os


def graphics():
    """The Dual Strike map graphics are on for this run (HUD, menus, CO page, cursor, art)."""
    return os.environ.get("TANGOAW2_DS_GRAPHICS") == "1"


def tilt():
    """The tilted map is on too."""
    return graphics() and os.environ.get("TANGOAW2_TILT") == "1"
