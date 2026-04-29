import random
from typing import Literal

ProfileKey = Literal["sample1", "sample2", "sample3", "random", "null"]

NPK_PROFILES = {
    "sample1": {
        "label": "Sample 1 — Acidic Red Soil (pH 5.82)",
        "n": (315, 345),
        "p": (68, 79),
        "k": (59, 68),
    },
    "sample2": {
        "label": "Sample 2 — Red Laterite (pH 5.94)",
        "n": (232, 253),
        "p": (45, 53),
        "k": (45, 51),
    },
    "sample3": {
        "label": "Sample 3 — Red Laterite (pH 5.96)",
        "n": (243, 264),
        "p": (44, 51),
        "k": (62, 69),
    },
    "random": {
        "label": "Random — Bangalore Roadside Soil",
        "n": (155, 190),
        "p": (38, 62),
        "k": (62, 83),
    },
    "null": None
}

class NPKOverrideState:
    def __init__(self):
        self._active: ProfileKey = "null"

    def set(self, profile: ProfileKey) -> None:
        self._active = profile

    def get(self) -> ProfileKey:
        return self._active

    def apply(self, npk_n: int | None, npk_p: int | None, npk_k: int | None, npk_ok: bool | None
             ) -> tuple[int | None, int | None, int | None, bool | None]:
        if self._active == "null" or NPK_PROFILES[self._active] is None:
            return npk_n, npk_p, npk_k, npk_ok

        profile = NPK_PROFILES[self._active]
        n = round(random.uniform(*profile["n"]))
        p = round(random.uniform(*profile["p"]))
        k = round(random.uniform(*profile["k"]))
        return n, p, k, True

npk_override = NPKOverrideState()
