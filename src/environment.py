# -*- coding: utf-8 -*-
#
# Written by Matthieu Sarkis, https://github.com/MatthieuSarkis
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import gym
import numpy as np
import pandas as pd
from typing import Tuple

from src.utilities import append_corr_matrix
class Environment(gym.Env):

    def __init__(self, 
                 stock_market_history: pd.DataFrame,                
                 initial_cash_in_bank: float,
                 buy_rate: float,
                 sell_rate: float,
                 bank_rate: float,
                 limit_n_stocks: float = 200,
                 buy_rule: str = 'most_first',
                 use_corr_matrix: bool = False,
                 window: int = 20,
                 ) -> None:
        
        super(Environment, self).__init__()
        
        self.stock_market_history = stock_market_history
        self.stock_space_dimension = stock_market_history.shape[1]
        self.buy_rule = buy_rule
        self.use_corr_matrix = use_corr_matrix
        self.window = window
        
        if self.use_corr_matrix:
            self.stock_market_history = append_corr_matrix(df=self.stock_market_history,
                                                           window=self.window)
            
        self.time_horizon = stock_market_history.shape[0]
        
        self.state_space_dimension = 2 * self.stock_space_dimension + 1
        self.action_space_dimension = self.stock_space_dimension
        
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(self.state_space_dimension,))
        self.action_space = gym.spaces.Box(low=-1, high=1, shape=(self.action_space_dimension,)) 
        self.limit_n_stocks = limit_n_stocks
        
        self.initial_cash_in_bank = initial_cash_in_bank
        
        self.buy_rate = buy_rate
        self.sell_rate = sell_rate
        self.bank_rate = bank_rate
        
        self.current_step = None
        self.cash_in_bank = None
        self.stock_prices = None
        self.number_of_shares = None

        self.reset()
    
    def reset(self) -> np.array:  
        
        self.current_step = 0
        self.cash_in_bank = self.initial_cash_in_bank
        self.stock_prices = self.stock_market_history.iloc[self.current_step]
        self.number_of_shares = np.zeros(self.stock_space_dimension)
        
        return self._get_observation()
        
    def step(self, 
             actions: np.array,
             ) -> Tuple[np.array, float, bool, dict]:
        
        self.current_step += 1      
        initial_value_portfolio = self._get_portfolio_value()
        self.stock_prices = self.stock_market_history.iloc[self.current_step] 
        
        self._trade(actions)
        
        self.cash_in_bank *= 1 + self.bank_rate # should this line be before the trade?       
        new_value_portfolio = self._get_portfolio_value()
        done = self.current_step == (self.time_horizon - 1)
        info = {'value_portfolio': new_value_portfolio}
        
        reward = new_value_portfolio - initial_value_portfolio 
           
        return self._get_observation(), reward, done, info
       
    def _trade(self, 
               actions: np.array) -> None:
        
        actions = (actions * self.limit_n_stocks).astype(int)
        sorted_indices = np.argsort(actions)
        
        sell_idx = sorted_indices[ : np.where(actions<0)[0].size]
        buy_idx = sorted_indices[::-1][ : np.where(actions>0)[0].size]

        for idx in sell_idx:  
            self._sell(idx, actions[idx])
        
        if self.buy_rule == 'most_first':
            for idx in buy_idx: 
                self._buy(idx, actions[idx])
                
        if self.buy_rule == 'cyclic':
            should_buy = np.copy(actions[buy_idx])
            i = 0
            while self.cash_in_bank > 0 and not np.all((should_buy == 0)):
                if should_buy[i] > 0:
                    self._buy(buy_idx[i])
                    should_buy[i] -= 1
                i = (i + 1) % len(buy_idx) 
                
        if self.buy_rule == 'random':
            should_buy = np.copy(actions[buy_idx])
            while self.cash_in_bank > 0 and not np.all((should_buy == 0)):
                i = np.random.choice(np.where(should_buy > 0))
                self._buy(buy_idx[i])
                should_buy[i] -= 1
        
    def _sell(self, 
              idx: int, 
              action: int,
              ) -> None:
    
        if int(self.number_of_shares[idx]) < 1:
            return
         
        n_stocks_to_sell = min(-action, int(self.number_of_shares[idx]))
        money_inflow = n_stocks_to_sell * self.stock_prices[idx] * (1 - self.sell_rate)
        self.cash_in_bank += money_inflow
        self.number_of_shares[idx] -= n_stocks_to_sell
            
    def _buy(self, 
             idx: int, 
             action: int,
             ) -> None:
        
        if self.cash_in_bank < 0:
            return
        
        n_stocks_to_buy = min(action, self.cash_in_bank // self.stock_prices[idx])
        money_outflow = n_stocks_to_buy * self.stock_prices[idx] * (1 + self.buy_rate)
        self.cash_in_bank -= money_outflow
        self.number_of_shares[idx] += n_stocks_to_buy   
        
    def _get_observation(self) -> np.array:
        
        observation = np.empty(self.state_space_dimension)
        observation[0] = self.cash_in_bank
        observation[1 : self.stock_prices.shape[0]+1] = self.stock_prices
        observation[self.stock_prices.shape[0]+1 : ] = self.number_of_shares
        
        return observation
    
    def _get_portfolio_value(self) -> float:
        
        portfolio_value = self.cash_in_bank + self.number_of_shares.dot(self.stock_prices[:self.stock_space_dimension])
        return portfolio_value

        
        
        
    