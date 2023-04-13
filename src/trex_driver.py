"""
TRex controller shell driver API. The business logic is implemented in trex_handler.py.
"""
from typing import Union

from cloudshell.shell.core.driver_context import CancellationContext, InitCommandContext, ResourceCommandContext
from cloudshell.traffic.tg import TgControllerDriver, enqueue_keep_alive

from trex_handler import TrexHandler


class TrexController2GDriver(TgControllerDriver):
    """TRex controller shell driver API."""

    def __init__(self) -> None:
        """Initialize object variables, actual initialization is performed in initialize method."""
        super().__init__()
        self.handler = TrexHandler()

    def initialize(self, context: InitCommandContext) -> None:
        """Initialize TRex controller shell (from API)."""
        super().initialize(context)
        self.handler.initialize(context, self.logger)

    def cleanup(self) -> None:
        """Cleanup TRex controller shell (from API)."""
        self.handler.cleanup()
        super().cleanup()

    def load_config(self, context: ResourceCommandContext, config_file_location: str) -> None:
        """Load configuration and reserve ports."""
        enqueue_keep_alive(context)
        self.handler.load_config(context, config_file_location)

    def start_traffic(self, context: ResourceCommandContext, blocking: str) -> None:  # pylint: disable=unused-argument
        """Start traffic on all ports."""
        self.handler.start_traffic(blocking)

    def stop_traffic(self, context: ResourceCommandContext) -> None:  # pylint: disable=unused-argument
        """Stop traffic on all ports."""
        self.handler.stop_traffic()

    def get_statistics(self, context: ResourceCommandContext, view_name: str, output_type: str) -> Union[dict, str]:
        """Get view statistics."""
        return self.handler.get_statistics(context, view_name, output_type)

    def keep_alive(self, context: ResourceCommandContext, cancellation_context: CancellationContext) -> None:
        """Keep TRex controller shell sessions alive (from TG controller API).

        Parent commands are not visible so we re re-define this method in child.
        """
        super().keep_alive(context, cancellation_context)
