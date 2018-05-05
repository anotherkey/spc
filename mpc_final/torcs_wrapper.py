from utils import *
import cv2
import numpy as np

class TorcsWrapper:
    def __init__(self, env, imsize=(256, 256)):
        self.env = env
        self.imsize = imsize
        self.doneCond = DoneCondition(30)
        self.epi_len = 0

    def reset(self):
        obs = self.env.reset()
        self.doneCond = DoneCondition(30)
        self.epi_len = 0
        return cv2.resize(obs, self.imsize)
         
    def step(self, action):
        self.epi_len += 1
        obs, reward, real_done, info = self.env.step(action)
        dist_this = info['speed']*(np.cos(info['angle'])-np.abs(np.sin(info['angle']))-np.abs(info['trackPos'])/9.0)
        reward_with_pos = info['speed']*(np.cos(info['angle'])-np.abs(np.sin(info['angle']))-np.abs(info['trackPos'])/9.0)/40.0
        reward_without_pos = info['speed']*(np.cos(info['angle'])-np.abs(np.sin(info['angle'])))/40.0
        done = self.doneCond.isdone(info['trackPos'], dist_this, info['pos']) or self.epi_len > 1000
        
        off_flag = int(info['trackPos']>=3 or info['trackPos']<=-1)
        coll_flag = int(abs(info['trackPos'])>7)
        obs = cv2.resize(obs, self.imsize)
        reward = {}
        reward['with_pos'] = reward_with_pos
        reward['without_pos'] = reward_without_pos
        info['off_flag'] = off_flag
        info['coll_flag'] = coll_flag

        return obs, reward, done, info

    def close(self):
        self.env.close()