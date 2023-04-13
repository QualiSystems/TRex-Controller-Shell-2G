"""
IxNetwork controller handler.
"""
import csv
import io
import json
import logging
from pathlib import Path
from typing import Union

from cloudshell.shell.core.driver_context import InitCommandContext, ResourceCommandContext
from cloudshell.traffic.helpers import get_family_attribute, get_resources_from_reservation
from cloudshell.traffic.tg import TREX_CHASSIS_MODEL, attach_stats_csv, is_blocking
from pytrex.trex_app import TrexApp
from pytrex.trex_statistics_view import TrexPortStatistics, TrexStreamStatistics
from trafficgenerator import TgnError

from trex_data_model import TrexControllerShell2G


class TrexHandler:
    """TRex controller shell business logic."""

    def __init__(self) -> None:
        """Initialize object variables, actual initialization is performed in initialize method."""
        self.trex: TrexApp = None
        self.logger: logging.Logger = None
        self.service: TrexControllerShell2G = None

    def initialize(self, context: InitCommandContext, logger: logging.Logger) -> None:
        """Init logger and create service."""
        self.logger = logger
        logging.getLogger("tgn.trex").setLevel(logger.level)
        self.service = TrexControllerShell2G.create_from_context(context)

    def cleanup(self) -> None:
        """Release all ports and disconnect from TRex server."""
        self.trex.server.disconnect()

    def load_config(self, context: ResourceCommandContext, trex_config_file_path: str) -> None:
        """Reserve ports and load TRex profiles."""
        ports = get_resources_from_reservation(context, f"{TREX_CHASSIS_MODEL}.GenericTrafficGeneratorPort")

        ip = ports[0].FullAddress.split("/")[0]
        self.trex = TrexApp(self.service.user, ip)
        self.trex.server.connect()

        locations = [int(port.FullAddress.split("/")[2].replace("P", "")) for port in ports]
        self.trex.server.reserve_ports(locations, force=True, reset=True)

        config_files = {get_family_attribute(context, port.Name, "Logical Name").strip(): port for port in ports}

        for port, config_file in zip(self.trex.server.ports.values(), config_files):
            port.remove_all_streams()
            port.load_streams(Path(trex_config_file_path).joinpath(config_file))
            port.write_streams()

        self.logger.info("Port Reservation Completed")

    def start_traffic(self, blocking: str) -> None:
        """Start traffic on all ports."""
        self.trex.server.clear_stats()
        self.trex.server.start_transmit(blocking=is_blocking(blocking))

    def stop_traffic(self) -> None:
        """Start traffic on all ports."""
        self.trex.server.stop_transmit()

    def get_statistics(self, context: ResourceCommandContext, view_name: str, output_type: str) -> Union[dict, str]:
        """Get statistics for the requested view."""
        if view_name == "Port":
            stats_obj = TrexPortStatistics(self.trex.server)
        elif view_name == "Stream":
            stats_obj = TrexStreamStatistics(self.trex.server)
        else:
            raise TgnError(f'Invalid Statistics View "{view_name}" - should be Port/Stream')

        statistics = stats_obj.read()
        if output_type.lower().strip() == "json":
            return json.loads(statistics.dumps())
        if output_type.lower().strip() == "csv":
            output = io.StringIO()
            captions = [view_name] + list(list(statistics.values())[0].keys())
            csv_writer = csv.DictWriter(output, captions)
            csv_writer.writeheader()
            for obj, stats in statistics.items():
                row = {view_name: obj.name}
                row.update(stats)
                csv_writer.writerow(row)
            attach_stats_csv(context, self.logger, view_name, output.getvalue().strip())
            return output.getvalue().strip()
        raise TgnError(f'Invalid Output Type "{output_type}" - should be CSV/JSON')
