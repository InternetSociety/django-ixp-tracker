import importlib
import logging
from datetime import datetime
from typing import Protocol, TypedDict

logger = logging.getLogger("ixp_tracker")


class ASNGeoLookup(Protocol):

    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        pass

    def get_status(self, asn: int, as_at: datetime) -> str:
        pass

    def get_asns_for_country(self, country: str, as_at: datetime) -> list[int]:
        pass

    def get_routed_asns_for_country(self, country: str, as_at: datetime) -> list[int]:
        pass


class ASNCustomerLookup(Protocol):

    def get_customer_asns(self, asns: list[int], as_at: datetime) -> list[int]:
        pass


class MANRSParticipantsLookup(Protocol):

    def get_manrs_participants(self, as_at: datetime) -> list[int]:
        pass


class RPKIData(TypedDict):
    roa_v4_valid: int
    roa_v4_invalid: int
    roa_v4_unknown: int
    roa_v6_valid: int
    roa_v6_invalid: int
    roa_v6_unknown: int


class RPKILookup(Protocol):

    def get_rpki_data(self, asn: int, as_at: datetime) -> RPKIData:
        pass


class AdditionalDataSources(ASNGeoLookup, ASNCustomerLookup, MANRSParticipantsLookup, RPKILookup):
    pass


class DefaultAdditionalDataSources(ASNGeoLookup, ASNCustomerLookup, MANRSParticipantsLookup):

    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        return "ZZ"

    def get_status(self, asn: int, as_at: datetime) -> str:
        return "assigned"

    def get_asns_for_country(self, country: str, as_at: datetime) -> list[int]:
        return []

    def get_customer_asns(self, asns: list[int], as_at: datetime) -> list[int]:
        return []

    def get_manrs_participants(self, as_at: datetime) -> list[int]:
        return []

    def get_rpki_data(self, asn: int, as_at: datetime) -> RPKIData:
        return {
            "roa_v4_valid": 0,
            "roa_v4_invalid": 0,
            "roa_v4_unknown": 0,
            "roa_v6_valid": 0,
            "roa_v6_invalid": 0,
            "roa_v6_unknown": 0,
        }


def load_lookup(lookup_name):
    if lookup_name is not None:
        lookup_parts = lookup_name.split(".")
        factory_name = lookup_parts.pop()
        module_name = ".".join(lookup_parts)
        logger.debug("Trying to load geo lookup", extra={"module_name": module_name, "factory": factory_name})
        if module_name and factory_name:
            imported_module = importlib.import_module(module_name)
            factory = getattr(imported_module, factory_name)
            return factory()
    return None
