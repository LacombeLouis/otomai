# %% IMPORTS

import asyncio
import time
import typing as T

from otomai.configs import logger
from otomai.core import utils
from otomai.core.models import Position


# %% POSITION MONITOR


class PositionMonitor:
    """Handles monitoring of position opening and closing."""

    def __init__(
        self,
        exchange_service: T.Any,
        notifier_service: T.Any,
        database_service: T.Any,
        strategy_name: str,
    ):
        self.exchange_service = exchange_service
        self.notifier_service = notifier_service
        self.database_service = database_service
        self.strategy_name = strategy_name

    def check_position_opening_available(self, max_simultaneous_positions: int) -> bool:
        """Check if a new position can be opened."""
        open_positions = len(self.exchange_service.session.fetch_positions())
        open_orders = len(self.exchange_service.session.fetch_open_orders())
        return open_positions + open_orders < max_simultaneous_positions

    async def monitor_position_opening(self, symbol: str, order_timeout: int = 600):
        """Monitor position opening until it's confirmed or times out."""
        open_position = {}
        start_time = time.time()

        while not open_position:
            open_position = self.exchange_service.session.fetch_position(symbol)
            if open_position:
                await self.notifier_service.send_message(
                    message=f"### {self.strategy_name} ### \n\n✅ Position successfully open for {symbol}."
                )
                return

            if time.time() - start_time > order_timeout:
                await self.notifier_service.send_message(
                    message=f"### {self.strategy_name} ### \n\n⚠️ Timeout: Failed to open position for {symbol} within {order_timeout} seconds."
                )
                return

            await asyncio.sleep(1)

    async def monitor_position_closing(
        self,
        symbol: str,
        open_date: str,
        strategy_params: str,
    ):
        """Monitor position closing and save to database when closed."""
        sleep_time = 60
        while True:
            positions_history = self.exchange_service.session.fetch_positions_history(
                symbols=[symbol], since=utils.get_ts_in_ms_from_date(open_date)
            )

            if positions_history:
                position_history = positions_history[0]
                position_history_info = position_history.get("info", {})
                net_profit = position_history_info.get("netProfit")

                if net_profit is not None:
                    try:
                        position = Position(
                            symbol=symbol,
                            net_profit=str(net_profit),
                            open_price=str(position_history_info.get("openAvgPrice")),
                            close_price=str(position_history_info.get("closeAvgPrice")),
                            hold_side=str(position_history_info.get("holdSide")),
                            open_date=str(
                                utils.get_date_from_ts_in_ms(
                                    int(position_history_info["ctime"])
                                )
                            ),
                            close_date=str(
                                utils.get_date_from_ts_in_ms(
                                    int(position_history_info["utime"])
                                )
                            ),
                            strategy_params=strategy_params,
                        )
                        self.database_service.insert_position(position)
                        logger.info(
                            f"Position for {symbol} saved successfully with net profit: {net_profit}"
                        )
                        await self.notifier_service.send_message(
                            message=(
                                f"### {self.strategy_name} ###\n\n"
                                f"Position successfully closed for {symbol} with {position.net_profit}$ net profit"
                            )
                        )
                        return
                    except Exception as e:
                        logger.error(f"Failed to insert position for {symbol}: {e}")
                        raise RuntimeError(
                            f"Error inserting position for {symbol}"
                        ) from e
                else:
                    logger.info(
                        f"No net profit available yet for {symbol}, retrying in {sleep_time} seconds..."
                    )

            await asyncio.sleep(sleep_time)

    async def monitor_position(self, symbol: str, open_date: str, strategy_params: str):
        """Monitor both opening and closing of a position."""
        await self.monitor_position_opening(symbol)
        await self.monitor_position_closing(symbol, open_date, strategy_params)
