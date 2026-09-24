"""Magnetic-component helpers for PFC design."""
from .high_flux import (
    HIGH_FLUX_254,
    HIGH_FLUX_254_MATERIALS,
    HighFluxCoreGeometry,
    HighFluxMaterial,
    high_flux_254_material,
)
from .pfc_inductor_designer import (
    PFCInductorDesignRequest,
    PFCInductorDesignResult,
    design_pfc_inductor,
)
from .ferrite_inductor import (
    FerriteInductorRequest,
    FerriteInductorResult,
    design_ferrite_pfc_inductor,
)
from .user_core_library import UserCoreLibrary, default_user_core_library_path

__all__ = [
    "HIGH_FLUX_254",
    "HIGH_FLUX_254_MATERIALS",
    "HighFluxCoreGeometry",
    "HighFluxMaterial",
    "high_flux_254_material",
    "PFCInductorDesignRequest",
    "PFCInductorDesignResult",
    "design_pfc_inductor",
    "FerriteInductorRequest",
    "FerriteInductorResult",
    "design_ferrite_pfc_inductor",
    "UserCoreLibrary",
    "default_user_core_library_path",
]
