from dataclasses import dataclass
from enum import Enum, auto


class SAPOperation(Enum):
    MMBE = auto()
    ZMRN = auto()
    ZPACK = auto()
    IW73 = auto()
    ZSTS = auto()
    IE03 = auto()
    ZIH3 = auto()
    ZLPR = auto()


@dataclass(slots=True, kw_only=True)
class SAPOptions:
    material: str = ""
    machine: str = ""
    service_order: str = ""
    plant: str = ""
    sales_org: str = ""


@dataclass(frozen=True, slots=True)
class SAPOperationInfo:
    title: str
    inputs: frozenset[str]


SAP_OPERATIONS = {
    SAPOperation.MMBE: SAPOperationInfo(
        title="MMBE - Stock Overview",
        inputs=frozenset({"material"}),
    ),
    SAPOperation.ZMRN: SAPOperationInfo(
        # title="ZMRN - Material Request Monitor",
        title="ZMRN - Material Request",
        inputs=frozenset({"material", "machine", "service_order"}),
    ),
    SAPOperation.ZSTS: SAPOperationInfo(
        title="ZSTS - Check Consumable",
        inputs=frozenset({"material"}),
    ),
    SAPOperation.IW73: SAPOperationInfo(
        title="IW73 - Display Service Order",
        inputs=frozenset({"machine"}),
    ),
    SAPOperation.ZPACK: SAPOperationInfo(
        title="ZPACK - Packaging Info",
        inputs=frozenset({"material"}),
    ),
    SAPOperation.IE03: SAPOperationInfo(
        title="IE03 - Equipment info",
        inputs=frozenset({"machine"}),
    ),
    SAPOperation.ZIH3: SAPOperationInfo(
        title="ZIH3 - Equipment Structure",
        inputs=frozenset({"machine"}),
    ),
    SAPOperation.ZLPR: SAPOperationInfo(
        title="ZLPR - Material Prices",
        inputs=frozenset({"material"}),
    ),
}
