"""Configuration used when connecting to a device.

A configuration describes a device, e.g. it's name, IP address and credentials. It is
possible to manually create a configuration, but generally scanning for devices will
provide configurations for you.

For a configuration to be usable ("ready") it must have either a `DMAP` or `MRP`
configuration (or both), as connecting to plain `AirPlay` devices it not supported.
"""
from ipaddress import IPv4Address
from typing import Dict, List, Optional

from pyatv import exceptions
from pyatv.const import Protocol, OperatingSystem
from pyatv.support.device_info import lookup_model, lookup_version
from pyatv.interface import BaseService, DeviceInfo


class AppleTV:
    """Representation of an Apple TV configuration.

    An instance of this class represents a single device. A device can have
    several services depending on the protocols it supports, e.g. DMAP or
    AirPlay.
    """

    def __init__(self, address: IPv4Address, name: str) -> None:
        """Initialize a new AppleTV."""
        self.address = address
        self.name = name
        self._services = {}  # type: Dict[Protocol, BaseService]

    @property
    def ready(self) -> bool:
        """Return if configuration is ready, i.e. has a main service."""
        has_dmap = Protocol.DMAP in self._services
        has_mrp = Protocol.MRP in self._services
        return has_dmap or has_mrp

    @property
    def identifier(self) -> Optional[str]:
        """Return the main identifier associated with this device."""
        for prot in [Protocol.MRP, Protocol.DMAP, Protocol.AirPlay]:
            service = self._services.get(prot)
            if service:
                return service.identifier
        return None

    @property
    def all_identifiers(self) -> List[str]:
        """Return all unique identifiers for this device."""
        return [x.identifier for x in self.services if x.identifier is not None]

    def add_service(self, service: BaseService) -> None:
        """Add a new service.

        If the service already exists, it will be merged.
        """
        existing = self._services.get(service.protocol)
        if existing is not None:
            existing.merge(service)
        else:
            self._services[service.protocol] = service

    def get_service(self, protocol: Protocol) -> Optional[BaseService]:
        """Look up a service based on protocol.

        If a service with the specified protocol is not available, None is
        returned.
        """
        return self._services.get(protocol)

    @property
    def services(self) -> List[BaseService]:
        """Return all supported services."""
        return list(self._services.values())

    def main_service(self, protocol: Protocol = None) -> BaseService:
        """Return suggested service used to establish connection."""
        protocols = (
            [protocol] if protocol is not None else [Protocol.MRP, Protocol.DMAP]
        )

        for prot in protocols:
            service = self._services.get(prot)
            if service is not None:
                return service

        raise exceptions.NoServiceError("no service to connect to")

    def set_credentials(self, protocol: Protocol, credentials: str) -> bool:
        """Set credentials for a protocol if it exists."""
        service = self.get_service(protocol)
        if service:
            service.credentials = credentials
            return True
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return general device information."""
        properties = self._all_properties()

        if Protocol.MRP in self._services:
            os_type = OperatingSystem.TvOS
        elif Protocol.DMAP in self._services:
            os_type = OperatingSystem.Legacy
        else:
            os_type = OperatingSystem.Unknown

        build = properties.get("SystemBuildVersion")
        model = properties.get("model")
        version = properties.get("osvers", lookup_version(build))

        mac = properties.get("macAddress", properties.get("deviceid"))
        if mac:
            mac = mac.upper()

        return DeviceInfo(os_type, version, build, lookup_model(model), mac)

    def _all_properties(self) -> Dict[str, str]:
        properties = {}  # type: Dict[str, str]
        for service in self.services:
            properties.update(service.properties)
        return properties

    def __eq__(self, other) -> bool:
        """Compare instance with another instance."""
        if isinstance(other, self.__class__):
            return self.identifier == other.identifier
        return False

    def __str__(self) -> str:
        """Return a string representation of this object."""
        device_info = self.device_info
        services = [" - {0}".format(s) for s in self._services.values()]
        identifiers = [" - {0}".format(x) for x in self.all_identifiers]
        return (
            "       Name: {0}\n"
            "   Model/SW: {1}\n"
            "    Address: {2}\n"
            "        MAC: {3}\n"
            "Identifiers:\n"
            "{4}\n"
            "Services:\n"
            "{5}".format(
                self.name,
                device_info,
                self.address,
                device_info.mac,
                "\n".join(identifiers),
                "\n".join(services),
            )
        )


# pylint: disable=too-few-public-methods
class DmapService(BaseService):
    """Representation of a DMAP service."""

    def __init__(
        self,
        identifier: str,
        credentials: str,
        port: int = None,
        properties: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialize a new DmapService."""
        super().__init__(identifier, Protocol.DMAP, port or 3689, properties)
        self.credentials = credentials


# pylint: disable=too-few-public-methods
class MrpService(BaseService):
    """Representation of a MediaRemote Protocol (MRP) service."""

    def __init__(
        self,
        identifier: str,
        port: int,
        credentials: str = None,
        properties: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialize a new MrpService."""
        super().__init__(identifier, Protocol.MRP, port, properties)
        self.credentials = credentials


# pylint: disable=too-few-public-methods
class AirPlayService(BaseService):
    """Representation of an AirPlay service."""

    def __init__(
        self,
        identifier: str,
        port: int = 7000,
        credentials: str = None,
        properties: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialize a new AirPlayService."""
        super().__init__(identifier, Protocol.AirPlay, port, properties)
        self.credentials = credentials
