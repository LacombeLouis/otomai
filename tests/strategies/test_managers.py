import pytest
from unittest.mock import MagicMock, AsyncMock

# Import directly from module to avoid Strategy class initialization
from otomai.strategies.managers.position_monitor import PositionMonitor
from otomai.strategies.managers.order_manager import OrderManager
from otomai.core.enums import OrderSide, TradeSide


class TestPositionMonitor:
    """Tests for PositionMonitor class."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        exchange_service = MagicMock()
        exchange_service.session = MagicMock()
        notifier_service = MagicMock()
        notifier_service.send_message = AsyncMock()
        database_service = MagicMock()
        return exchange_service, notifier_service, database_service

    @pytest.fixture
    def position_monitor(self, mock_services):
        """Create a PositionMonitor instance."""
        exchange_service, notifier_service, database_service = mock_services
        return PositionMonitor(
            exchange_service=exchange_service,
            notifier_service=notifier_service,
            database_service=database_service,
            strategy_name="TestStrategy",
        )

    def test_check_position_opening_available_true(
        self, position_monitor, mock_services
    ):
        """Test when position opening is available."""
        exchange_service, _, _ = mock_services
        exchange_service.session.fetch_positions.return_value = []
        exchange_service.session.fetch_open_orders.return_value = []

        result = position_monitor.check_position_opening_available(
            max_simultaneous_positions=2
        )
        assert result is True

    def test_check_position_opening_available_false(
        self, position_monitor, mock_services
    ):
        """Test when position opening is not available."""
        exchange_service, _, _ = mock_services
        exchange_service.session.fetch_positions.return_value = [1, 2]
        exchange_service.session.fetch_open_orders.return_value = []

        result = position_monitor.check_position_opening_available(
            max_simultaneous_positions=2
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_monitor_position_opening_success(
        self, position_monitor, mock_services
    ):
        """Test successful position opening monitoring."""
        exchange_service, notifier_service, _ = mock_services
        exchange_service.session.fetch_position.return_value = {"id": "123"}

        await position_monitor.monitor_position_opening(symbol="BTC/USDT:USDT")

        notifier_service.send_message.assert_called_once()
        message = notifier_service.send_message.call_args[1]["message"]
        assert "Position successfully open" in message

    @pytest.mark.asyncio
    async def test_monitor_position_opening_timeout(
        self, position_monitor, mock_services
    ):
        """Test position opening monitoring timeout."""
        exchange_service, notifier_service, _ = mock_services
        exchange_service.session.fetch_position.return_value = {}

        # Use a very short timeout for testing
        await position_monitor.monitor_position_opening(
            symbol="BTC/USDT:USDT", order_timeout=1
        )

        notifier_service.send_message.assert_called_once()
        message = notifier_service.send_message.call_args[1]["message"]
        assert "Timeout" in message


class TestOrderManager:
    """Tests for OrderManager class."""

    @pytest.fixture
    def mock_exchange_service(self):
        """Create mock exchange service for testing."""
        exchange_service = MagicMock()
        exchange_service.session = MagicMock()
        return exchange_service

    @pytest.fixture
    def order_manager(self, mock_exchange_service):
        """Create an OrderManager instance."""
        return OrderManager(exchange_service=mock_exchange_service)

    def test_get_order_creation_amount_success(
        self, order_manager, mock_exchange_service
    ):
        """Test successful order amount calculation."""
        mock_exchange_service.session.fetch_balance.return_value = {
            "USDT": {"free": 1000.0}
        }

        amount = order_manager.get_order_creation_amount(equity_trade_pct=10.0)
        assert amount == 100.0

    def test_get_order_creation_amount_error(
        self, order_manager, mock_exchange_service
    ):
        """Test order amount calculation with error."""
        mock_exchange_service.session.fetch_balance.side_effect = Exception("API Error")

        amount = order_manager.get_order_creation_amount(equity_trade_pct=10.0)
        assert amount == 0.0

    def test_calculate_prices(self, order_manager, mock_exchange_service):
        """Test price calculation."""
        mock_exchange_service.session.fetch_ticker.return_value = {
            "info": {"lastPr": "50000"}
        }

        last_price, tp_price, sl_price = order_manager.calculate_prices(
            symbol="BTC/USDT:USDT",
            order_side=OrderSide.BUY,
            take_profit_pct=10.0,
            stop_loss_pct=5.0,
            leverage=1,
        )

        assert last_price == 50000.0
        assert tp_price > last_price  # Take profit should be higher for BUY
        assert sl_price < last_price  # Stop loss should be lower for BUY

    def test_set_margin_mode_and_leverage(self, order_manager, mock_exchange_service):
        """Test setting margin mode and leverage."""
        order_manager.set_margin_mode_and_leverage(
            symbol="BTC/USDT:USDT", margin_mode="isolated", leverage=10
        )

        mock_exchange_service.set_margin_mode_and_leverage.assert_called_once_with(
            symbol="BTC/USDT:USDT", margin_mode="isolated", leverage=10
        )

    def test_create_order(self, order_manager, mock_exchange_service):
        """Test order creation."""
        mock_exchange_service.create_order.return_value = {"id": "order123"}

        order = order_manager.create_order(
            symbol="BTC/USDT:USDT",
            order_side=OrderSide.BUY,
            amount=0.1,
            order_type="market",
            margin_mode="isolated",
            trade_side=TradeSide.OPEN,
            reduce=False,
        )

        assert order == {"id": "order123"}
        mock_exchange_service.create_order.assert_called_once()
