from functools import cmp_to_key
from math import floor
from .utils import TrieNode, GameplayError

class Player:
    def __init__(self, id:str):
        self.id = id
        self.score = 0
        self.reset_round()

    def reset_round(self):
        self.score = 0
        self.reset_turn()
        
    def reset_turn(self):
        self.took_bet = False # Had player bet somebody else?
        self.bet_id = None # Who had the player bet?
        self.stake = None # This round's stake.
        self.betted = None # How many people betted on the player? (For deduct)
        self.bet_reward = None # Points that the player earned in this turn's bet.
        self.card_spent = None # Points that the player spent on buying random cards.
        self.card_reward = None # Points that the player earned on card events.
        self.card_reward_merged = False # If card reward has been calculated. 
                                        # Only used for distingushing phases in __str__

        self.played = False # Did the player submit the playscore?
        self.playing_score = None # This round's playscore.
        self.rank = None # The player's rank in this turn's playing.
        self.cur_pt = None # Points that the player earned in this turn's playing.

    def __lt__(self, other):
        return self.score < other.score

    def __str__(self):
        if self.card_reward_merged: # After bet eval + card award
            if self.bet_reward < 0:
                return f'{self.id} ({self.score-self.bet_reward-self.card_reward}-{-self.bet_reward}+{self.card_reward}={self.score})'
            else:
                return f'{self.id} ({self.score-self.bet_reward-self.card_reward}+{self.bet_reward}+{self.card_reward}={self.score})'
        elif not self.bet_reward is None: # After bet eval + without card reward
            if self.bet_reward < 0:
                return f'{self.id} ({self.score-self.bet_reward}-{-self.bet_reward}={self.score})'
            else:
                return f'{self.id} ({self.score-self.bet_reward}+{self.bet_reward}={self.score})'
        elif not self.betted is None: # After bet deduct
            return f'{self.id} ({self.score+self.betted}-{self.betted}={self.score})'
        elif not self.cur_pt is None: # After score rank eval
            return f'{self.id} ({self.score-self.cur_pt}+{self.cur_pt}={self.score})'
        elif not self.card_spent is None: # After buy card (and take bet)
            return f'{self.id} ({self.score+self.card_spent}-{self.card_spent}={self.score})'
        elif not self.took_bet is None: # After take bet + without buy card
            return f'{self.id} ({self.score})'
        else: # Before take bet
            return f'{self.id} ({self.score})'
    
class PlayerManager:
    def __init__(self):
        self.betted_decrease = True
        self.bet_failed_decrease = True
        self.player_list = []
        self.player_id_trie = TrieNode()

        # set evaluate function
        self.reset_round()

    def reset_round(self):
        for player in self.player_list:
            player.reset_round()
        self.reset_turn

    # reset function
    def reset_turn(self):
        for player in self.player_list:
            player.reset_turn()
        self.betted_decrease = True
        self.bet_failed_decrease = True
        self.double_reward = False
        self.set_score = self.default_set_score
        self.ranking_cmp = self.default_ranking_cmp
        self.rank_to_score = self.default_rank_to_score

    @property
    def player_num(self):
        return len(self.player_list)

    # player function
    def find_player(self, id:str):
        return self.player_id_trie.find(id)

    def add_player(self, id:str):
        id = str.strip(id)
        if len(id) >= 15:
            raise GameplayError("Player id should be less than 15 character!")
        player = Player(id)
        self.player_list.append(player)
        self.player_id_trie.insert(id, player)

    def remove_player(self, id:str):
        _, player_id = self.player_id_trie.delete(id) 
        for i, player in enumerate(self.player_list):
            if player.id == player_id:
                del(self.player_list[i])
                return

    # default evaluate function
    def default_set_score(self, player:Player, score):
        if not isinstance(score, int):
            raise GameplayError("Score should be a integer")
        player.playing_score = score

    
    # Compare funcs:
    def default_ranking_cmp(self, a:Player, b:Player):
        if not a.rank is None and not b.rank is None and a.rank != b.rank:
            return b.rank - a.rank
        elif a.playing_score != b.playing_score:
            return a.playing_score - b.playing_score
        elif a.score != b.score:
            return b.score - a.score
        else:
            return a.id > b.id
    
    def score_cmp(self, a:Player, b:Player):
        if a.score != b.score:
            return a.score - b.score
        else:
            return a.id > b.id
    
    def playscore_cmp(self, a:Player, b:Player):
        if a.playing_score != b.playing_score:
            return a.playing_score - b.playing_score
        else:
            return a.id > b.id

    # Play rank to score:
    def default_rank_to_score(self, member):
        pt = (len(member)+1)//2
        for i, player in enumerate(member):
            player.rank = i
            player.cur_pt = pt
            player.score += pt
            if pt > 0:
                pt -= 1

    def default_score_evaluate(self, player_list):
        self.player_list = sorted(self.player_list, reverse=True)
        max_score = self.player_list[0].score
        score_list = [0 for _ in range(self.player_num)]

        for i, player in enumerate(self.player_list):
            if player.bet_id:
                bet_player = self.find_player(player.bet_id)
                if bet_player.score == max_score:
                    if self.double_reward:
                        score_list[i] = player.stake * 2
                    else:
                        score_list[i] = player.stake
                elif self.bet_failed_decrease:
                    score_list[i] = -player.stake

        for i, player in enumerate(self.player_list):
            
            player.bet_reward = score_list[i]
            player.score += score_list[i]


    # buy card cost
    def card_bought_deduct(self, deduct_list):
        if len(deduct_list):
            half_score = floor(len(self.player_list)/2)
            for player in deduct_list:
                player.score -= half_score
                player.card_spent = half_score
    
    # evaluate function
    def preprocess_playing_score(self, process_func):
        self.player_list = process_func(self.player_list)

    # sort play score
    def evaluate_playing_score(self, sort_func):
        'sort_func(a:Player, b:Player) -> compare_result'
        self.player_list = sorted(self.player_list, reverse=True, 
            key=cmp_to_key(sort_func))
        self.rank_to_score(self.player_list)
    
    # bet target rearrange
    def preprocess_bet_target(self, process_func):
        self.player_list = process_func(self.player_list)

    # deduct bet target score
    def evaluate_bet_deduct(self, evaluate_func):
        self.player_list = evaluate_func(self.player_list)

    # effects before bet score calculate
    def preprocess_bet_score(self, evaluate_func):
        self.player_list = evaluate_func(self.player_list)

    # calculate bet score
    def evaluate_bet_score(self, func_evaluate):
        self.player_list = func_evaluate(self.player_list)

    # effects after bet score calculate
    def postprocess_bet_score(self, evaluate_func):
        self.player_list = evaluate_func(self.player_list)
        self.player_list = sorted(self.player_list, reverse=True)

    @property
    def player_num(self):
        return len(self.player_list)

# test
if __name__ == '__main__':
    playerManager = PlayerManager()
    playerManager.add_player("aaa")
    playerManager.add_player("aab")
    playerManager.add_player("abb")
    playerManager.add_player("bcc")

    print(len(playerManager.player_list))   # 4
    print(playerManager.find_player("ab"))  # abb(0)

    playerManager.remove_player("aaa")      # delete aaa
    print(len(playerManager.player_list))   # 3

    print(playerManager.find_player("aa"))  # aab(0)
    playerManager.remove_player("aa")       # delete aab
    print(len(playerManager.player_list))   # 2

    print(playerManager.find_player("ab"))  # abb(0)
    print(playerManager.find_player("b"))   # bcc(0)
    print(playerManager.find_player("aa"))  # error