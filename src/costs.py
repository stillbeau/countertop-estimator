from typing import Dict


def calculate_cost(
    rec: Dict,
    sq_ft: float,
    markup_factor: float,
    fabrication_cost_per_sqft: float,
    install_cost_per_sqft: float,
    ib_material_markup: float,
) -> Dict[str, float]:
    """Return a breakdown of costs for the given record."""
    uc = rec.get("unit_cost", 0) or 0
    mat = uc * markup_factor * sq_ft
    fab = fabrication_cost_per_sqft * sq_ft
    ins = install_cost_per_sqft * sq_ft
    ib = ((uc * ib_material_markup) + fabrication_cost_per_sqft) * sq_ft
    return {
        "base_material_and_fab_component": mat + fab,
        "base_install_cost_component": ins,
        "ib_cost_component": ib,
        "total_customer_facing_base_cost": mat + fab + ins,
    }
