# tests/test_handlers.py
"""
Тесты обработчиков.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery, User as TgUser, Chat
from aiogram.fsm.context import FSMContext

from handlers.start import router as start_router
from handlers.match import router as match_router


class TestStartHandlers:
    """Тесты обработчиков старта"""

    @pytest.mark.asyncio
    async def test_command_start_new_user(self):
        """Тест команды /start для нового пользователя"""
        # Создаем моки
        message = MagicMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123456789
        message.from_user.username = "new_user"
        message.from_user.first_name = "New"
        message.from_user.last_name = "User"
        message.answer = AsyncMock()

        state = MagicMock(spec=FSMContext)
        state.clear = AsyncMock()

        # Мокаем сессию
        with patch('handlers.start.async_session', new_callable=AsyncMock) as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()

            # Вызываем обработчик
            from handlers.start import command_start
            await command_start(message, state)

            # Проверяем вызовы
            state.clear.assert_called_once()
            message.answer.assert_called_once()

            # Проверяем, что в ответе есть приветствие
            call_args = message.answer.call_args
            assert "Добро пожаловать" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_command_help(self):
        """Тест команды /help"""
        message = MagicMock(spec=Message)
        message.answer = AsyncMock()

        from handlers.start import command_help
        await command_help(message)

        message.answer.assert_called_once()

        # Проверяем содержание справки
        call_args = message.answer.call_args
        assert "Помощь" in call_args[0][0]
        assert "/start" in call_args[0][0]
        assert "/help" in call_args[0][0]


class TestMatchHandlers:
    """Тесты обработчиков матчей"""

    @pytest.mark.asyncio
    async def test_command_play_no_team(self):
        """Тест команды /play без команды"""
        message = MagicMock(spec=Message)
        message.from_user = MagicMock(spec=TgUser)
        message.from_user.id = 123456789
        message.answer = AsyncMock()

        # Мокаем сессию без команды
        with patch('handlers.match.async_session', new_callable=AsyncMock) as mock_session:
            mock_session_obj = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_obj

            # Пользователь есть, команды нет
            mock_user = MagicMock()
            mock_session_obj.get.return_value = mock_user

            from handlers.match import command_play
            await command_play(message)

            # Должен быть ответ с предложением создать команду
            message.answer.assert_called_once()
            call_args = message.answer.call_args
            assert "создать команду" in call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_match_type_selection(self):
        """Тест выбора типа матча"""
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=TgUser)
        callback.from_user.id = 123456789
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        state = MagicMock(spec=FSMContext)

        # Мокаем сессию
        with patch('handlers.match.async_session', new_callable=AsyncMock) as mock_session:
            mock_session_obj = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_obj

            # Есть пользователь и команда
            mock_user = MagicMock()
            mock_team = MagicMock()
            mock_team.name = "Test Team"
            mock_team.formation = "1-4-4-2"

            mock_session_obj.get.side_effect = lambda model, id: {
                (User, 123456789): mock_user,
                (Team, 123456789): mock_team
            }.get((model, id))

            # Нет активных матчей
            mock_session_obj.execute.return_value.scalar_one_or_none.return_value = None

            from handlers.match import match_type_vs_random
            await match_type_vs_random(callback, state)

            # Должен быть создан матч и отправлен ответ
            callback.message.edit_text.assert_called_once()
            callback.answer.assert_called_once()