# %% IMPORTS

import typing as T

from otomai.core import utils
from otomai.core.enums import OrderSide, TradeSide
from otomai.logger import Logger

logger = Logger(__name__)

# %% ORDER MANAGER


class OrderManager:
    """Handles order creation and management."""

    def __init__(self, exchange_service: T.Any):
        self.exchange_service = exchange_service

    def open_future_order(
        self,
        symbol: str,
        equity_trade_pct: float,
        order_type: str,
        order_side: OrderSide,
        margin_mode: str,
        leverage: int,
        take_profit_pct: float,
        stop_loss_pct: float,
        safety_margin: float,
        max_retries: int,
    ) -> T.Dict:
        """Open a futures order with the given parameters."""
        return self.exchange_service.open_future_order(
            symbol=symbol,
            equity_trade_pct=equity_trade_pct,
            order_type=order_type,
            order_side=order_side,
            margin_mode=margin_mode,
            leverage=leverage,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            safety_margin=safety_margin,
            max_retries=max_retries,
        )

    def create_order(
        self,
        symbol: str,
        order_side: OrderSide,
        amount: float,
        order_type: str,
        margin_mode: str,
        trade_side: TradeSide,
        reduce: bool,
        take_profit_price: T.Optional[float] = None,
        stop_loss_price: T.Optional[float] = None,
    ) -> T.Dict:
        """Create an order with the given parameters."""
        return self.exchange_service.create_order(
            symbol=symbol,
            side=order_side,
            amount=amount,
            type=order_type,
            margin_mode=margin_mode,
            trade_side=trade_side,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            reduce=reduce,
        )

    def set_margin_mode_and_leverage(
        self, symbol: str, margin_mode: str, leverage: int
    ):
        """Set margin mode and leverage for a symbol."""
        self.exchange_service.set_margin_mode_and_leverage(
            symbol=symbol,
            margin_mode=margin_mode,
            leverage=leverage,
        )

    def get_order_creation_amount(self, equity_trade_pct: float) -> float:
        """Calculate the amount for order creation based on available balance."""
        try:
            balance = self.exchange_service.session.fetch_balance()
            free_amount = balance["USDT"]["free"]
            return free_amount * equity_trade_pct / 100
        except Exception as e:
            logger.error(f"Error calculating new position amount: {e}")
            return 0.0

    def calculate_prices(
        self,
        symbol: str,
        order_side: OrderSide,
        take_profit_pct: float,
        stop_loss_pct: float,
        leverage: int,
    ) -> T.Tuple[float, float, float]:
        """Calculate last price, take profit price, and stop loss price."""
        ticker = self.exchange_service.session.fetch_ticker(symbol=symbol)
        last_price = float(ticker["info"]["lastPr"])

        take_profit_price = utils.calculate_take_profit_price(
            last_price,
            order_side,
            take_profit_pct,
            leverage,
        )
        stop_loss_price = utils.calculate_stop_loss_price(
            last_price,
            order_side,
            stop_loss_pct,
            leverage,
        )

        return last_price, take_profit_price, stop_loss_price
