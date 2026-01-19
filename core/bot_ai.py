# core/bot_ai.py
"""
Искусственный интеллект для игры против бота в Final 4.
Строго соответствует правилам игры.
"""

import random
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class BotDifficulty(Enum):
    """Уровень сложности бота"""
    EASY = 1  # Случайные допустимые ходы
    MEDIUM = 2  # Базовая стратегия, следует правилам
    HARD = 3  # Оптимальная стратегия, предсказывает


class Final4BotAI:
    """ИИ для бота в Final 4 (согласно правилам из документа)"""

    def __init__(self, difficulty: BotDifficulty = BotDifficulty.MEDIUM):
        self.difficulty = difficulty

        # Счетчики для соблюдения правил (на 1 матч)
        self.used_players = set()  # На каких игроков уже ставили
        self.gk_odd_even_done = False  # Ставка на вратаря сделана
        self.odd_even_count = 0  # Ставок Чет/Нечет (макс 6)
        self.goal_bets = {  # Ставок на гол по позициям
            'DF': 0,  # Макс 1
            'MF': 0,  # Макс 3
            'FW': 0  # Макс 4
        }
        self.current_turn = 1
        self.my_actions = {'goals': 0, 'passes': 0, 'defenses': 0}

    def reset_for_new_match(self):
        """Сброс для нового матча"""
        self.used_players.clear()
        self.gk_odd_even_done = False
        self.odd_even_count = 0
        self.goal_bets = {'DF': 0, 'MF': 0, 'FW': 0}
        self.current_turn = 1
        self.my_actions = {'goals': 0, 'passes': 0, 'defenses': 0}

    def make_turn_decision(self, turn: int, my_team: List[Dict],
                           my_formation: str, opponent_actions: Dict) -> Dict:
        """
        Принимает решение на ход.
        Возвращает: {'player_id': X, 'bet_type': 'odd_even/less_more/exact', 'bet_value': '...'}
        """
        self.current_turn = turn

        # 1. Определяем активных игроков по формации
        active_players = self._get_active_players(my_team, my_formation)

        # 2. Фильтруем по правилам
        available_choices = self._get_legal_choices(active_players)

        if not available_choices:
            # Если нет легальных ходов (невозможно), берем первого доступного
            return self._fallback_choice(active_players[0]) if active_players else None

        # 3. Выбираем лучший ход по стратегии
        if self.difficulty == BotDifficulty.EASY:
            choice = random.choice(available_choices)
        elif self.difficulty == BotDifficulty.MEDIUM:
            choice = self._medium_strategy(available_choices, opponent_actions)
        else:  # HARD
            choice = self._hard_strategy(available_choices, opponent_actions, turn)

        # 4. Обновляем счетчики
        self._update_counters(choice)

        return choice

    def _get_active_players(self, team: List[Dict], formation: str) -> List[Dict]:
        """Возвращает игроков на поле по формации"""
        # Пример: формация "1-4-4-2" -> 1 GK, 4 DF, 4 MF, 2 FW
        parts = formation.split('-')
        gk_needed = int(parts[0])
        df_needed = int(parts[1])
        mf_needed = int(parts[2])
        fw_needed = int(parts[3])

        active = []
        counts = {'GK': 0, 'DF': 0, 'MF': 0, 'FW': 0}

        for player in team:
            pos = player['position']
            if counts[pos] < {'GK': gk_needed, 'DF': df_needed,
                              'MF': mf_needed, 'FW': fw_needed}[pos]:
                active.append(player)
                counts[pos] += 1

        return active

    def _get_legal_choices(self, active_players: List[Dict]) -> List[Dict]:
        """Возвращает только легальные ходы по правилам"""
        choices = []

        for player in active_players:
            player_id = player['id']
            position = player['position']

            # Нельзя ставить на одного игрока дважды
            if player_id in self.used_players:
                continue

            # ПРАВИЛО: Первый ход - обязательно ставка на вратаря Чет/Нечет
            if self.current_turn == 1 and position == 'GK' and not self.gk_odd_even_done:
                choices.append({
                    'player_id': player_id,
                    'player_position': position,
                    'bet_type': 'odd_even',
                    'bet_value': random.choice(['чет', 'нечет'])
                })
                continue

            # ПРАВИЛО: Форварды не могут ставить Чет/Нечет
            if position != 'FW':
                # ПРАВИЛО: Макс 6 ставок Чет/Нечет (включая вратаря)
                if self.odd_even_count < 6:
                    choices.append({
                        'player_id': player_id,
                        'player_position': position,
                        'bet_type': 'odd_even',
                        'bet_value': random.choice(['чет', 'нечет'])
                    })

            # ПРАВИЛО: Все кроме вратаря могут ставить Меньше/Больше
            if position != 'GK':
                choices.append({
                    'player_id': player_id,
                    'player_position': position,
                    'bet_type': 'less_more',
                    'bet_value': random.choice(['меньше', 'больше'])
                })

            # ПРАВИЛО: Ставки на гол с ограничениями
            if position == 'DF' and self.goal_bets['DF'] < 1:
                choices.append({
                    'player_id': player_id,
                    'player_position': position,
                    'bet_type': 'exact',
                    'bet_value': str(random.randint(1, 6))
                })
            elif position == 'MF' and self.goal_bets['MF'] < 3:
                choices.append({
                    'player_id': player_id,
                    'player_position': position,
                    'bet_type': 'exact',
                    'bet_value': str(random.randint(1, 6))
                })
            elif position == 'FW' and self.goal_bets['FW'] < 4:
                choices.append({
                    'player_id': player_id,
                    'player_position': position,
                    'bet_type': 'exact',
                    'bet_value': str(random.randint(1, 6))
                })

        return choices

    def _medium_strategy(self, choices: List[Dict], opponent_actions: Dict) -> Dict:
        """Средняя стратегия: баланс атаки и защиты"""
        # Считаем текущий баланс
        my_def = self.my_actions['defenses']
        my_pass = self.my_actions['passes']
        opp_def = opponent_actions.get('defenses', 0)

        # Если у соперника много защит, нужно больше передач
        if opp_def > my_pass + 2:
            # Предпочитаем ставки на передачи
            for choice in choices:
                if choice['bet_type'] == 'less_more':
                    return choice

        # Если у нас мало защит, нужно больше отбитий
        if my_def < 5:
            for choice in choices:
                if choice['bet_type'] == 'odd_even':
                    return choice

        # Иначе стремимся к голам
        for choice in choices:
            if choice['bet_type'] == 'exact':
                return choice

        # Если ничего не подошло, случайный выбор
        return random.choice(choices)

    def _hard_strategy(self, choices: List[Dict], opponent_actions: Dict, turn: int) -> Dict:
        """Сложная стратегия: оптимизация по вероятности выигрыша"""
        best_choice = None
        best_score = -1000

        for choice in choices:
            score = self._calculate_choice_score(choice, opponent_actions, turn)
            if score > best_score:
                best_score = score
                best_choice = choice

        return best_choice or random.choice(choices)

    def _calculate_choice_score(self, choice: Dict, opponent_actions: Dict, turn: int) -> float:
        """Оценивает полезность выбора"""
        score = 0.0
        pos = choice['player_position']
        bet_type = choice['bet_type']

        # Вероятности успеха (грубо)
        if bet_type == 'odd_even':
            prob = 0.5  # 50%
            value = {'GK': 3, 'DF': 2, 'MF': 1}.get(pos, 0)
            score = prob * value * 2  # Защита важна

        elif bet_type == 'less_more':
            prob = 0.5  # 50%
            value = {'DF': 1, 'MF': 2, 'FW': 1}.get(pos, 0)
            score = prob * value

        else:  # exact
            prob = 1 / 6  # 16.7%
            value = 1  # гол
            score = prob * value * 3  # Голы очень важны

        # Корректировка по ходу
        if turn <= 2:  # Ранние ходы
            if bet_type in ['odd_even', 'less_more']:
                score *= 1.5  # Важнее защита и передачи
        else:  # Поздние ходы
            if bet_type == 'exact':
                score *= 2.0  # Важнее голы

        return score

    def _fallback_choice(self, player: Dict) -> Dict:
        """Запасной выбор, если нет легальных"""
        position = player['position']

        if position == 'GK':
            bet_type = 'odd_even'
            bet_value = random.choice(['чет', 'нечет'])
        elif position == 'FW':
            bet_type = 'less_more'
            bet_value = random.choice(['меньше', 'больше'])
        else:
            bet_type = random.choice(['odd_even', 'less_more', 'exact'])
            if bet_type == 'odd_even':
                bet_value = random.choice(['чет', 'нечет'])
            elif bet_type == 'less_more':
                bet_value = random.choice(['меньше', 'больше'])
            else:
                bet_value = str(random.randint(1, 6))

        return {
            'player_id': player['id'],
            'player_position': position,
            'bet_type': bet_type,
            'bet_value': bet_value
        }

    def _update_counters(self, choice: Dict):
        """Обновляет счетчики после выбора"""
        player_id = choice['player_id']
        position = choice['player_position']
        bet_type = choice['bet_type']

        self.used_players.add(player_id)

        if position == 'GK' and bet_type == 'odd_even':
            self.gk_odd_even_done = True

        if bet_type == 'odd_even':
            self.odd_even_count += 1

        if bet_type == 'exact':
            if position == 'DF':
                self.goal_bets['DF'] += 1
            elif position == 'MF':
                self.goal_bets['MF'] += 1
            elif position == 'FW':
                self.goal_bets['FW'] += 1

    def update_my_actions(self, new_actions: Dict):
        """Обновляет наши набранные действия"""
        for key in ['goals', 'passes', 'defenses']:
            self.my_actions[key] += new_actions.get(key, 0)

    def decide_card_usage(self, drawn_card: Dict, match_state: Dict) -> bool:
        """Решает, использовать ли вытянутую карточку 'Свисток'"""
        # ПРАВИЛО ИГРЫ: Любую вытянутую карточку "Свисток" нужно использовать сразу
        # Отказаться от использования карточки нельзя
        return True