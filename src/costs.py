MARKUP_FACTOR = 1.51
INSTALL_COST_PER_SQFT = 21
FABRICATION_COST_PER_SQFT = 17
IB_MATERIAL_MARKUP = 1.05


def calculate_cost(rec: dict, sq: float) -> dict:
    uc = rec.get("unit_cost", 0) or 0
    mat = uc * MARKUP_FACTOR * sq
    fab = FABRICATION_COST_PER_SQFT * sq
    ins = INSTALL_COST_PER_SQFT * sq
    ib = ((uc * IB_MATERIAL_MARKUP) + FABRICATION_COST_PER_SQFT) * sq
    return {
        "base_material_and_fab_component": mat + fab,
        "base_install_cost_component": ins,
        "ib_cost_component": ib,
        "total_customer_facing_base_cost": mat + fab + ins,
    }
