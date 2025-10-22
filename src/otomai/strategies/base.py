# %% IMPORTS

import abc
import typing as T
import re

import pydantic as pdt

from otomai.services import (
    ExchangeServiceKind,
    NotifierServiceKind,
    DatabaseService,
    DynamoDB,
)
from otomai.core.parameters import TradingParams, StrategyParams
from otomai.strategies.managers import PositionMonitor, OrderManager

# %% VARIABLES

SYMBOL_REGEX: re.Pattern = re.compile(r"^[A-Z0-9]+/[A-Z0-9]+(:[A-Z0-9]+)?$")

# %% STRATEGY


class Strategy(abc.ABC, pdt.BaseModel, strict=True, extra="forbid"):
    KIND: str

    symbol: T.Optional[str] = pdt.Field(
        default=None,
        pattern=r"^[A-Z0-9]+/USDT:USDT$",
        description="Trading pair symbol in the format BASE/QUOTE[:EXCHANGE] (e.g., ETH/USDT:USDT)",
        strict=True,
    )
    exchange_service: ExchangeServiceKind = pdt.Field(..., discriminator="KIND")
    notifier_service: NotifierServiceKind = pdt.Field(..., discriminator="KIND")
    database_service: DatabaseService = DynamoDB()
    strategy_params: StrategyParams = pdt.Field(...)
    trading_params: TradingParams = pdt.Field(...)

    _position_monitor: T.Optional[PositionMonitor] = None
    _order_manager: T.Optional[OrderManager] = None

    @property
    def position_monitor(self) -> PositionMonitor:
        """Lazy initialization of PositionMonitor."""
        if self._position_monitor is None:
            self._position_monitor = PositionMonitor(
                exchange_service=self.exchange_service,
                notifier_service=self.notifier_service,
                database_service=self.database_service,
                strategy_name=self.strategy_params.name,
            )
        return self._position_monitor

    @property
    def order_manager(self) -> OrderManager:
        """Lazy initialization of OrderManager."""
        if self._order_manager is None:
            self._order_manager = OrderManager(exchange_service=self.exchange_service)
        return self._order_manager

    def __enter__(self) -> "Strategy":
        """
        Enter method for context manager.
        """
        # You can initialize resources here if needed
        return self

    def __exit__(
        self,
        exc_type: T.Type[BaseException],
        exc_value: BaseException,
        traceback: T.Any,
    ) -> None:
        """
        Exit method for context manager.
        """

    def position_opening_available(self, max_simultaneous_positions: int) -> bool:
        """Check if a new position can be opened."""
        return self.position_monitor.check_position_opening_available(
            max_simultaneous_positions
        )

    async def monitor_position_opening(self, symbol: str, order_timeout: int = 600):
        """Monitor position opening until it's confirmed or times out."""
        return await self.position_monitor.monitor_position_opening(
            symbol, order_timeout
        )

    async def monitor_position_closing(
        self,
        symbol: str,
        open_date: str,
    ):
        """Monitor position closing and save to database when closed."""
        return await self.position_monitor.monitor_position_closing(
            symbol, open_date, str(self.strategy_params)
        )

    async def monitor_position(self, symbol: str, open_date: str):
        """Monitor both opening and closing of a position."""
        await self.position_monitor.monitor_position(
            symbol, open_date, str(self.strategy_params)
        )

    @abc.abstractmethod
    async def run(self) -> T.Any:
        """
        Abstract method to run the strategy. Must be implemented by subclasses.
        """
        pass
