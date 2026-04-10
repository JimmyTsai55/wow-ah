from dataclasses import dataclass, field


@dataclass
class Reagent:
    item_id: int
    name: str
    quantity: int


@dataclass
class Recipe:
    name: str
    output_item_id: int
    output_quantity: int
    reagents: list[Reagent] = field(default_factory=list)
