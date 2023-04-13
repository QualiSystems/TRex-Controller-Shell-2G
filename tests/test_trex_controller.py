"""
Test TrexController2GDriver.
"""
# pylint: disable=redefined-outer-name
import json
from pathlib import Path
from typing import Iterable

import pytest
import yaml
from _pytest.fixtures import SubRequest
from cloudshell.api.cloudshell_api import AttributeNameValue, CloudShellAPISession, InputNameValue
from cloudshell.shell.core.driver_context import ResourceCommandContext
from cloudshell.traffic.helpers import get_reservation_id, get_resources_from_reservation, set_family_attribute
from cloudshell.traffic.tg import TREX_CHASSIS_MODEL, TREX_CONTROLLER_MODEL
from shellfoundry_traffic.test_helpers import TgTestHelpers, session, test_helpers  # pylint: disable=unused-import

from src.trex_driver import TrexController2GDriver

ALIAS = "TRex Controller"
TREX_USER = "trex"


@pytest.fixture(params=["quali_sut.yaml"], ids=["linux"])
def ports(request: SubRequest) -> list:
    """Yield TRex device under test parameters."""
    with open(request.param, "r") as yaml_file:
        trex_yaml = yaml.safe_load(yaml_file)
    return trex_yaml["ports"]


@pytest.fixture()
def driver(test_helpers: TgTestHelpers) -> Iterable[TrexController2GDriver]:
    """Yield initialized TrexController2GDriver."""
    attributes = {f"{TREX_CONTROLLER_MODEL}.User": TREX_USER}
    init_context = test_helpers.service_init_command_context(TREX_CONTROLLER_MODEL, attributes)
    driver = TrexController2GDriver()
    driver.initialize(init_context)
    yield driver
    driver.cleanup()


@pytest.fixture()
def context(session: CloudShellAPISession, test_helpers: TgTestHelpers, ports: list) -> ResourceCommandContext:
    """Yield ResourceCommandContext for shell command testing."""
    attributes = [AttributeNameValue(f"{TREX_CONTROLLER_MODEL}.User", TREX_USER)]
    session.AddServiceToReservation(test_helpers.reservation_id, TREX_CONTROLLER_MODEL, ALIAS, attributes)
    context = test_helpers.resource_command_context(service_name=ALIAS)
    session.AddResourcesToReservation(test_helpers.reservation_id, ports)
    reservation_ports = get_resources_from_reservation(context, f"{TREX_CHASSIS_MODEL}.GenericTrafficGeneratorPort")
    set_family_attribute(context, reservation_ports[0].Name, "Logical Name", "test_profile_1.yaml")
    set_family_attribute(context, reservation_ports[1].Name, "Logical Name", "test_profile_2.yaml")
    return context


class TestTrexControllerDriver:
    """Test direct driver calls."""

    def test_load_config(self, driver: TrexController2GDriver, context: ResourceCommandContext) -> None:
        """Test load configuration command."""
        self._load_config(driver, context)

    def test_run_traffic(self, driver: TrexController2GDriver, context: ResourceCommandContext) -> None:
        """Test complete cycle - from load_config to get_statistics."""
        self._load_config(driver, context)
        driver.start_traffic(context, "True")
        driver.stop_traffic(context)
        stats = driver.get_statistics(context, "Port", "JSON")
        assert int(stats["server/port0"]["opackets"]) == 300
        assert int(stats["server/port1"]["opackets"]) == 300
        driver.get_statistics(context, "Port", "CSV")

    @staticmethod
    def _load_config(driver: TrexController2GDriver, context: ResourceCommandContext) -> None:
        """Get full path to the requested configuration file based on fixture and run load_config."""
        config_file = Path(__file__).parent
        driver.load_config(context, config_file.as_posix())


class TestTrexControllerShell:
    """Test indirect Shell calls."""

    def test_load_config(self, session: CloudShellAPISession, context: ResourceCommandContext) -> None:
        """Test load configuration command."""
        self._load_config(session, context, ALIAS)

    def test_run_traffic(self, session: CloudShellAPISession, context: ResourceCommandContext) -> None:
        """Test complete cycle - from load_config to get_statistics."""
        self._load_config(session, context, ALIAS)
        session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "stop_traffic")
        cmd_inputs = [InputNameValue("blocking", "True")]
        session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "start_traffic", cmd_inputs)
        cmd_inputs = [
            InputNameValue("view_name", "Port"),
            InputNameValue("output_type", "JSON"),
        ]
        stats = session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "get_statistics", cmd_inputs)
        assert int(json.loads(stats.Output)["server/port0"]["opackets"]) == 300

    @staticmethod
    def _load_config(session: CloudShellAPISession, context: ResourceCommandContext, alias: str) -> None:
        """Get full path to the requested configuration file based on fixture and run load_config."""
        config_file = Path(__file__).parent
        cmd_inputs = [InputNameValue("config_file_location", config_file.as_posix())]
        session.ExecuteCommand(get_reservation_id(context), alias, "Service", "load_config", cmd_inputs)
