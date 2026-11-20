"""Load magnitudes shared by the FEM load cases. Every value is ASSUMED until measured.

Forces in N. One place to refine them: part definitions read these, they don't repeat them.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BeltLoads:
    """Tension of one belt run."""

    preload_n: float = 40.0  #: ASSUMED: set when tensioning, acts continuously
    dynamic_n: float = 20.0  #: ASSUMED: added at peak acceleration

    @property
    def peak_n(self) -> float:
        """Tension of one run at peak acceleration."""
        return self.preload_n + self.dynamic_n


X_BELT_LOADS = BeltLoads()
Y_BELT_LOADS = BeltLoads()
