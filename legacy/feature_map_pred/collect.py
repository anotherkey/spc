import torch
import torch.nn as nn
import numpy as np
import math
import time
import drn
import os
from scipy.misc import imsave
from scipy.misc.pilutil import imshow
import matplotlib.pyplot as plt
from py_TORCS import torcs_envs
from kill_torcses import kill_torcses

def fill_up_weights(up):
    w = up.weight.data
    f = math.ceil(w.size(2) / 2)
    c = (2 * f - 1 - f % 2) / (2. * f)
    for i in range(w.size(2)):
        for j in range(w.size(3)):
            w[0, 0, i, j] = \
                (1 - math.fabs(i / f - c)) * (1 - math.fabs(j / f - c))
    for c in range(1, w.size(0)):
        w[c, 0, :, :] = w[0, 0, :, :]

def up_sampler(classes, use_torch_up=False):
    if use_torch_up:
        up = nn.UpsamplingBilinear2d(scale_factor=8)
    else:
        up = nn.ConvTranspose2d(classes, classes, 16, stride=8, padding=4,
                                output_padding=0, groups=classes, bias=False)
        fill_up_weights(up)
    return up

class DRNSeg(nn.Module):
    def __init__(self, model_name, classes, pretrained_model=None,
                 pretrained=False, use_torch_up=False, num_actions = 6):
        super(DRNSeg, self).__init__()
        model = drn.__dict__.get(model_name)(
            pretrained=pretrained, num_classes=1000)
        pmodel = nn.DataParallel(model)
        if pretrained_model is not None:
            pmodel.load_state_dict(pretrained_model)
        self.base = nn.Sequential(*list(model.children())[:-2])

        self.seg = nn.Conv2d(model.out_dim, classes,
                             kernel_size=1, bias=True)
        self.softmax = nn.LogSoftmax()
        m = self.seg
        n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
        m.weight.data.normal_(0, math.sqrt(2. / n))
        m.bias.data.zero_()
        self.up0 = up_sampler(classes)
        self.up1 = up_sampler(classes)
        self.up2 = up_sampler(classes)
        self.up3 = up_sampler(classes)
        self.up4 = up_sampler(classes)
        self.up5 = up_sampler(classes)

    def forward(self, x):
        x = self.base(x)
        x = self.seg(x)
        # if action == 0:
        #     y = self.up0(x)
        # elif action == 1:
        #     y = self.up1(x)
        # elif action == 2:
        #     y = self.up2(x)
        # elif action == 3:
        #     y = self.up3(x)
        # elif action == 4:
        #     y = self.up4(x)
        # elif action == 5:
        #     y = self.up5(x)
        return x

    def optim_parameters(self, memo=None):
        for param in self.base.parameters():
            yield param
        for param in self.seg.parameters():
            yield param

def draw_from_pred(pred):
    pred = pred.data.cpu().numpy()[0]
    illustration = np.zeros((480, 640, 3)).astype(np.uint8)
    illustration[:, :, 0] = 255
    illustration[pred == 1] = np.array([0, 255, 0])
    illustration[pred == 2] = np.array([0, 0, 0])
    illustration[pred == 3] = np.array([0, 0, 255])
    return illustration


num_steps = 12
obs_avg = 112.62289744791671
obs_std = 56.1524832523

def collect_RGB(env, dir = 'dataset'):
    if not os.path.isdir(dir):
        os.mkdir(dir)
    os.system('rm ' + dir + '/*.png')
    obs = env.reset()
    for i in range(100):
        action = np.random.randint(6)
        obs, reward, done, info = env.step(action)
        imsave(os.path.join(dir, '%d.png' % i), obs)
        if done or reward <= -2.5:
            obs = env.reset()

def collect_feature_map(env):
    model = DRNSeg('drn_d_22', 4)
    model.load_state_dict(torch.load('models/epoch5.dat'))
    inputs = torch.autograd.Variable(torch.ones(1, 3, 480, 640), requires_grad = False)
    if torch.cuda.is_available():
        model = model.cuda()
        inputs = inputs.cuda()

    for i in range(2000):
        obs = env.reset()
        obs = (obs.transpose(2, 0, 1) - obs_avg) / obs_std
        inputs[0] = torch.from_numpy(obs)
        feature_map = model(inputs).detach().data.cpu().numpy()
        np.save('dataset/episode%d_step%d.npy' % (i, 0), feature_map)
        for j in range(1, 201):
            action = np.random.randint(6)
            obs, reward, done, info = env.step(action)
            obs = (obs.transpose(2, 0, 1) - obs_avg) / obs_std
            inputs[0] = torch.from_numpy(obs)
            feature_map = model(inputs).detach().data.cpu().numpy()
            np.save('dataset/episode%d_step%d_action%d.npy' % (i, j, action), feature_map)

def collect_segmentation(env, dir = 'dataset'):
    if not os.path.isdir(dir):
        os.mkdir(dir)
    os.system('rm ' + dir + '/*.npz')
    obs = env.reset()
    obs = (obs.transpose(2, 0, 1) - obs_avg) / obs_std
    for i in range(6000):
        old = obs
        action = np.random.randint(6)
        obs, reward, done, info = env.step(action)
        obs = (obs.transpose(2, 0, 1) - obs_avg) / obs_std
        seg = env.get_segmentation().astype(np.uint8)
        np.savez(os.path.join(dir, '%d.npz' % i), obs = old, action = np.array([action]), seg = seg)
        if done or reward <= -2.5:
            obs = env.reset()
            obs = (obs.transpose(2, 0, 1) - obs_avg) / obs_std

def collect_seq(env, dir = 'dataset2'):
    if not os.path.isdir(dir):
        os.mkdir(dir)
    os.system('rm ' + dir + '/*.npz')
    obs = env.reset()
    obs = (obs.transpose(2, 0, 1) - obs_avg) / obs_std
    seg = env.get_segmentation().astype(np.uint8)
    seg_list = np.repeat(np.expand_dims(seg, axis = 0), num_steps + 1, axis = 0)
    true_obs = np.repeat(obs, 3, axis = 0)
    obs_list = [true_obs for i in range(num_steps)]
    action_array = np.repeat(np.array([4]), num_steps)
    offroad_array = np.zeros(num_steps + 1)
    collision_array = np.zeros(num_steps + 1)
    dist_array = np.zeros(num_steps + 1)

    for i in range(2000):
        action = np.random.randint(5)
        if action == 4:
            action = 5
        obs, reward, done, info = env.step(action)
        obs = (obs.transpose(2, 0, 1) - obs_avg) / obs_std
        seg = np.expand_dims(env.get_segmentation().astype(np.uint8), axis = 0)
        seg_list = np.concatenate((seg_list[1:], seg), axis = 0)
        action_array = np.concatenate((action_array[1:], np.array([action])))
        offroad = 1 - int(-1 < info['trackPos'] < 5)
        offroad_array = np.concatenate((offroad_array[1:], np.array([offroad])))
        collision = int(reward <= -2.5 or abs(info['trackPos']) > 7)
        collision_array = np.concatenate((collision_array[1:], np.array([collision])))
        dist = info['speed'] * (np.cos(info['angle']) - np.abs(np.sin(info['angle'])) - np.abs(info['trackPos']) / 9.0) / 40.0
        dist_array = np.concatenate((dist_array[1:], np.array([dist])))
        np.savez('dataset2/%d.npz' % i, obs = obs_list[-num_steps], action = action_array, seg = seg_list, off = offroad_array, coll = collision_array, dist = dist_array)
        true_obs = np.concatenate((true_obs[3:], obs), axis=0)
        obs_list = obs_list[1:] + [true_obs]
        if done or reward <= -2.5:
            obs = env.reset()
            true_obs = np.repeat((obs.transpose(2, 0, 1) - obs_avg) / obs_std, 3, axis = 0)
            obs_list = [true_obs for i in range(num_steps)]
            action_array = np.repeat(np.array([4]), num_steps)
            seg = env.get_segmentation().astype(np.uint8)
            seg_list = np.repeat(np.expand_dims(seg, axis = 0), num_steps + 1, axis = 0)

def collect_new(env, dir = 'dataset2'):
    if not os.path.isdir(dir):
        os.mkdir(dir)
    os.system('rm ' + dir + '/*.npz')
    obs = env.reset()
    true_obs = np.repeat((obs.transpose(2, 0, 1) - obs_avg) / obs_std, 3, axis = 0)
    obs_list = [true_obs for i in range(num_steps)]
    seg = env.get_segmentation().astype(np.uint8)
    seg_list = np.repeat(np.expand_dims(seg, axis = 0), num_steps + 1, axis = 0)
    action_array = np.repeat(np.array([4]), num_steps)
    pos_array = np.ones(num_steps + 1) * 0.431906836373
    angle_array = np.ones(num_steps + 1) * 0.0201784928692
    speed_array = np.zeros(num_steps + 1)

    for i in range(2000):
        action = np.random.randint(5)
        if action == 4:
            action = 5
        obs, reward, done, info = env.step(action)
        obs = (obs.transpose(2, 0, 1) - obs_avg) / obs_std
        true_obs = np.concatenate((true_obs[3:], obs), axis=0)
        obs_list = obs_list[1:] + [true_obs]

        seg = np.expand_dims(env.get_segmentation().astype(np.uint8), axis = 0)
        seg_list = np.concatenate((seg_list[1:], seg), axis = 0)

        action_array = np.concatenate((action_array[1:], np.array([action])))

        pos_array = np.concatenate((pos_array[1:], np.array([info['trackPos'] / 7.0])))
        angle_array = np.concatenate((angle_array[1:], np.array([info['angle']])))
        speed_array = np.concatenate((speed_array[1:], np.array([info['speed']])))

        np.savez(dir + '/%d.npz' % i, obs = obs_list[-num_steps], 
                                      action = action_array, 
                                      seg = seg_list, 
                                      pos = pos_array, 
                                      angle = angle_array, 
                                      speed = speed_array)
        if done or reward <= -2.5:
            obs = env.reset()
            true_obs = np.repeat((obs.transpose(2, 0, 1) - obs_avg) / obs_std, 3, axis = 0)
            obs_list = [true_obs for i in range(num_steps)]
            seg = env.get_segmentation().astype(np.uint8)
            seg_list = np.repeat(np.expand_dims(seg, axis = 0), num_steps + 1, axis = 0)
            action_array = np.repeat(np.array([4]), num_steps)
            pos_array = np.ones(num_steps + 1) * 0.431906836373
            angle_array = np.ones(num_steps + 1) * 0.0201784928692
            speed_array = np.zeros(num_steps + 1)

if __name__ == '__main__':
    np.random.seed(0)
    kill_torcses()


    envs = torcs_envs(num = 1, mkey_start = 1000)
    env = envs.get_envs()[0]

    collect_new(env)
    
    env.close()