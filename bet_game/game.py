from .player import PlayerManager
from .song  import *
from .quest import QuestPool
from .event import RandomEvent
from .card import RandomCard
from .utils import GameplayError, log, divideline
from functools import cmp_to_key

class Game:
    STATUS_000_UNAVAILABLE = 0
    STATUS_100_DRAW_EVENT = 100
    STATUS_101_DRAW_QUEST = 101
    STATUS_102_BET = 102
    STATUS_103_PLAY = 103
    STATUS_1031_CARD_DECIDE = 1031 # only for __str__ printing
    STATUS_104_EVALUATE_SCORE = 104
    STATUS_105_BET_DEDUCT = 105
    STATUS_106_EVALUATE_BET = 106
    STATUS_107_EVALUATE_CARD = 107
    STATUS_200_FINISHED = 200

    def __init__(self, game_type='arcaea', turns=5, random_p=0.5, random_card=False):
        if game_type == "arcaea":
            self.song_manager = ArcaeaSongPackageManager()
        elif game_type == "phigros":
            self.song_manager = PhigrosSongPackageManager()
        else:
            raise GameplayError("Currently Only Support arcaea and phigros")
        self.__play_manager = PlayerManager()
        self.__quest_pool = QuestPool()
        self.__turns = turns
        self.__random_event = RandomEvent(self.__play_manager, game_type=game_type, random_p=random_p)
        self.__random_card = RandomCard(game_type=game_type, random_card=random_card)
        self.reset_round(turns)

    @property
    def finished(self):
        return self.__status == self.STATUS_200_FINISHED

    @property
    def winner(self):
        if not self.__winner is None:
            return self.__winner
        if self.__status == self.STATUS_200_FINISHED:
            max_score = None
            for player in self.__play_manager.player_list:
                if max_score is None or player.score > max_score:
                    max_score = player.score

            winner = ""
            for player in self.__play_manager.player_list:
                if player.score == max_score:
                    winner = winner + player.id + ", "
            self.__winner = winner[:-2]
            return self.__winner
        else:
            return ""

    def reset_round(self, turn):
        self.__turns = turn
        self.__winner = None
        self.__current_quest = None
        self.__status = self.STATUS_000_UNAVAILABLE
        self.__play_manager.reset_round()
        self.reset_turn()

    def reset_turn(self):
        self.__play_manager.reset_turn()
        self.__current_card = self.__random_card.default_card()
        self.__current_quest = None
        self.__bet_num = 0
        self.__gameplay_num = 0

    # helper function
    def check_status(self, status):
        if self.__status != status:
            raise GameplayError(f'Invalid operation. The current status is {self.__status}')

    # player and init
    def enroll(self, id:str):
        self.__play_manager.add_player(id)

    def remove(self, id:str):
        self.__play_manager.remove_player(id)

    def add_quest(self, quest_list:list):
        cur_quest_list = self.song_manager.add_quest_list(quest_list)
        self.__quest_pool.set_quest_list(cur_quest_list)

    def enable_all(self, en_package=True, en_difficulties=True):
        if en_package:
            self.song_manager.enable_all_packages()
        if en_difficulties:
            self.song_manager.enable_all_difficulties()

    def disable_all(self, dis_package=True, dis_difficulties=True):
        if dis_package:
            self.song_manager.disable_all_packages()
        if dis_difficulties:
            self.song_manager.disable_all_difficulties()

    def enable(self, pac:str):
        self.song_manager.enable(pac)

    def disable(self, pac:str):
        self.song_manager.disable(pac)

    # game play
    def start(self):
        self.player_num = self.__play_manager.player_num
        self.__random_card.set_player_list(self.__play_manager.player_list)
        self.__status = self.STATUS_100_DRAW_EVENT
        log(f'Starting game with {self.__turns} turns.')

    def draw_event(self):
        self.check_status(self.STATUS_100_DRAW_EVENT)
        self.__random_event.draw_event()
        self.__status = self.STATUS_101_DRAW_QUEST

    def draw_quest(self):
        if self.__status == self.STATUS_102_BET:
            if self.__bet_num > 0:
                raise GameplayError(f'Cannot redraw quests. Some players have already bet')
            redraw = True
            self.__quest_pool.remove_quest(self.__current_quest)
        else:
            self.check_status(self.STATUS_101_DRAW_QUEST)
            redraw = False

        self.__current_quest = self.__quest_pool.draw_quest()
        self.__status = self.STATUS_102_BET

        if redraw:
            log(f'Redrawing quest: {self.__current_quest.description}.')
        else:
            log(f'{self.__turns} turn{"s" if self.__turns > 1 else ""} left. Drawing quest: {self.__current_quest.description}.')

    def bet(self, player_id, bet_id, stake=1):
        if self.__status == self.STATUS_103_PLAY:
            if self.__gameplay_num != 0:
                raise GameplayError(f'Cannot re-bet. Some players have already played')
        else:
            self.check_status(self.STATUS_102_BET)
            if not self.__bet_num:
                divideline()
    
        player = self.__play_manager.find_player(player_id)
        bet_id_actual = ''
        if not player.took_bet:
            if bet_id:
                bet_player = self.__play_manager.find_player(bet_id)
                if (bet_player.id == player.id):
                    raise GameplayError(f'Cannot bet oneself: {bet_player.id}')
                bet_id_actual = bet_player.id
            player.took_bet = True
            self.__bet_num += 1

        player.bet_id = bet_id
        if bet_id:
            player.bet_id = bet_id_actual
            player.stake = max(min(stake, self.player_num), 1)
            log(f'Player {player.id} bets {stake} point{"s" if stake > 1 else ""} on {bet_id}.')
        else:
            log(f'Player {player.id} doesn\'t take bet this turn.')

        if self.__bet_num == self.player_num:
            self.__status = self.STATUS_103_PLAY
        
    def draw_card(self, player_id):
        if self.__status == self.STATUS_103_PLAY:
            if self.__gameplay_num != 0:
                raise GameplayError(f'Cannot buy random card. Some players have already played')
        else:
            self.check_status(self.STATUS_102_BET)
            if not self.__bet_num:
                divideline()
        player = self.__play_manager.find_player(player_id)
        self.__random_card.add_pending_queue(player)
        self.__bet_num += 1
        if self.__bet_num == self.player_num:
            self.__status = self.STATUS_103_PLAY

    def show_card(self):
        if (self.__status != self.STATUS_104_EVALUATE_SCORE):
            self.check_status(self.STATUS_103_PLAY)
        divideline()
        self.__status = self.STATUS_1031_CARD_DECIDE
        temp_card = self.__random_card.print_card()
        self.__play_manager.card_bought_deduct(temp_card.user_deduct_list)
        log(f'Player {temp_card.user} get card {temp_card.description}.')
        if input('Use card? [Y/N] ').lower() == 'y':
            self.__current_card = temp_card
        divideline()
        log(str(self))
        self.__status = self.STATUS_103_PLAY
        

    def play(self, player_id, score):
        if (self.__status != self.STATUS_104_EVALUATE_SCORE):
            self.check_status(self.STATUS_103_PLAY)
            if not self.__gameplay_num:
                divideline()
        player = self.__play_manager.find_player(player_id)
        self.__play_manager.set_score(player, score)
        
        if not player.played:
            player.played = True
            self.__gameplay_num += 1
        
        if self.__gameplay_num == self.player_num:
            self.__status = self.STATUS_104_EVALUATE_SCORE
        log(f'Player {player.id} plays the quest with score "{score}".')

    def evaluate_score(self):
        self.check_status(self.STATUS_104_EVALUATE_SCORE)
        divideline()
        self.__play_manager.preprocess_playing_score(self.__current_card.playing_score_preprocess)
        self.__play_manager.evaluate_playing_score(self.__current_card.score_rank_cmp)
        log(str(self))
        divideline()
        self.__status = self.STATUS_105_BET_DEDUCT    

    def evaluate_bet(self):
        self.check_status(self.STATUS_105_BET_DEDUCT)
        self.__play_manager.preprocess_bet_target(self.__current_card.target_rearrange)
        self.__play_manager.evaluate_bet_deduct(self.__current_card.bet_deduct)
        log(str(self))
        divideline()

        self.__status = self.STATUS_106_EVALUATE_BET
        self.__play_manager.preprocess_bet_score(self.__current_card.bet_score_preprocess)
        self.__play_manager.evaluate_bet_score(self.__current_card.bet_score_evaluate)
        log(str(self))
        divideline()

        self.__status = self.STATUS_107_EVALUATE_CARD
        self.__play_manager.postprocess_bet_score(self.__current_card.bet_score_postprocess)
        log(str(self))
        divideline()
        divideline()

        self.__turns -= 1
        self.__random_card.set_player_list(self.__play_manager.player_list)
        self.reset_turn()
        if self.__turns <= 0:
            self.__status = self.STATUS_200_FINISHED
        else:
            self.__status = self.STATUS_100_DRAW_EVENT

    def __str__(self):
        turn = f'{self.__turns} turn{"s" if self.__turns > 1 else ""} left.\n'

        head = ''
        if self.__status == self.STATUS_100_DRAW_EVENT:
            head = f'Drawing the next event.\n'
        if self.__status == self.STATUS_101_DRAW_QUEST:
            head = f'Drawing the next quest.\n'
        elif self.__status == self.STATUS_102_BET:
            head = f'The quest is {self.__current_quest.description}. Players are betting.\n'
        elif self.__status == self.STATUS_1031_CARD_DECIDE:
            head = f'Final bet & card results are:\n'
        elif self.__status == self.STATUS_103_PLAY:
            head = f'Playing {self.__current_quest.description}.\n'
        elif self.__status == self.STATUS_104_EVALUATE_SCORE:
            head = f'Evaluating scores of {self.__current_quest.description}.\n'
        elif self.__status == self.STATUS_105_BET_DEDUCT:
            head = f'Evaluating bet target deducts.\n'
        elif self.__status == self.STATUS_106_EVALUATE_BET:
            head = f'Evaluating bet results.\n'
        elif self.__status == self.STATUS_107_EVALUATE_CARD:
            head = f'Evaluating random card effects.\n'

        if self.__status == self.STATUS_1031_CARD_DECIDE:
            player_infos = []
            for player in sorted(self.__play_manager.player_list, reverse=True,
                    key=cmp_to_key(self.__play_manager.score_cmp)):
                if player.bet_id:
                    player_infos.append(f'{player} {"bets " + str(player.stake) + " point(s) on " + player.bet_id}')
                elif player.card_spent:
                    player_infos.append(f'{player} {"spends " + str(player.card_spent) + " point(s) on random card."}')
                else:
                    player_infos.append(f'{player} {"not betting"}')
        elif self.__status == self.STATUS_104_EVALUATE_SCORE:
            player_infos = [
                f'{player} (result: {player.playing_score})'
                for player in sorted(self.__play_manager.player_list, reverse=True,
                    key=cmp_to_key(self.__play_manager.playscore_cmp))
            ]
        elif self.__status == self.STATUS_105_BET_DEDUCT or \
            self.__status == self.STATUS_106_EVALUATE_BET:
            player_infos = [
                f'{player} {"bets " + str(player.stake) + " point(s) on " + player.bet_id if player.bet_id else "not betting"}'
                for player in sorted(self.__play_manager.player_list, reverse=True,
                    key=cmp_to_key(self.__play_manager.score_cmp))
            ]
        else:
            player_infos = [f'{player}' for player in self.__play_manager.player_list]
        player_infos_str = '\n'.join(player_infos)
        return f'{turn}{head}{player_infos_str}'
