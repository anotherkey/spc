import numpy as np
import torch
import torch.nn as nn
from torch.autograd import Variable
import torch.nn.functional as F
import os
from replay_buffer import replay_buffer
from utils import clear_visualization_dir, reset_env, naive_driver, init_criteria, draw_from_pred, from_variable_to_numpy, sample_action, sample_continuous_action, convert_state_dict

from scipy.misc import imsave
from scipy.misc.pilutil import imshow
import matplotlib.pyplot as plt

def sample_one_step(args, true_obs, env, model, posxyz):
    exploration = args.exploration_decay ** args.epoch
    data = {'obs': true_obs}

    if args.continuous:
        action, dqn_action = sample_continuous_action(args, true_obs, model) # need updating
        data['dqn_action'] = dqn_action
    else:
        action = sample_action(args, true_obs, model) # need updating
    data['action'] = action

    obs, reward, done, info = env.step(action)
    with open('env_log.txt', 'a') as f:
        f.write('reward = %0.4f\n' % reward)
    obs = (obs.transpose(2, 0, 1) - args.obs_avg) / args.obs_std
    if args.frame_len > 1:
        true_obs = np.concatenate((true_obs[3:], obs), axis = 0)
    else:
        true_obs = obs

    if args.use_dqn:
        data['reward'] = reward
    if args.use_seg:
        data['target_seg'] = env.get_segmentation().astype(np.uint8)

    data['target_coll'] = int(reward <= -2.5 or abs(info['trackPos']) > 7)
    data['target_off'] = int(info['trackPos'] >= 3 or info['trackPos'] <= -1)
    if args.use_center_dist:
        data['target_dist'] = abs(info['trackPos'])
    else:
        data['target_dist'] = info['speed'] * (np.cos(info['angle']) - np.abs(np.sin(info['angle'])) - np.abs(info['trackPos']) / 9.0)

    if args.use_xyz:
        data['target_xyz'] = np.array(info['pos']) - posxyz
        posxyz = np.array(info['pos'])
    
    done = done or reward <= -2.5 # or abs(info['trackPos']) > args.coll_rescale or abs(info['off']) > args.off_rescale
    if done:
        with open('env_log.txt', 'a') as f:
            f.write('done')
        true_obs, posxyz = reset_env(args, env)
    data['done'] = int(done)
    return data, true_obs, posxyz

def train_data(args, train_data, model, dqn, optimizer): # need updating
    LOSS = np.zeros((args.num_steps + 1, 3))
    criterion = init_criteria()
    weight, loss = 1, 0

    hx, cx = Variable(torch.zeros(args.batch_size, args.hidden_dim)), Variable(torch.zeros(args.batch_size, args.hidden_dim))
    for step in range(args.num_steps):
        hx, cx, (coll_prob, offroad_prob, dist) = model(inputs[step], actions[step], hx, cx)
        output_coll[step] = coll_prob
        output_off[step] = offroad_prob
        output_dist[step] = dist
        loss0 = criterion['BCE'](coll_prob, target_coll[step])
        loss1 = criterion['BCE'](offroad_prob, target_off[step])
        loss2 = criterion['L2'](dist, target_dist[step])
        loss += weight * (loss0 + loss1 + loss2)
        LOSS[step, 0] = from_variable_to_numpy(loss0)
        LOSS[step, 1] = from_variable_to_numpy(loss1)
        LOSS[step, 2] = from_variable_to_numpy(loss2)
        weight *= args.loss_decay

        q_a_values = dqn_net(inputs[step]).gather(1, dqn_actions[step])
        q_a_values_tp1 = target_Q(inputs[step]).detach().max(1)[0]
        target_values = rewards[step] + (0.99 * q_a_values_tp1)
        loss += ((target_values.view(q_a_values.size()) - q_a_values)**2).mean()

    # _feature_map = model(inputs[0])
    # _prediction = up(_feature_map)
    # prediction[0] = _prediction
    # loss0 = criterion['CE'](_prediction, targets[0])
    # _feature_map = _feature_map.detach()
    # _feature_map.requires_grad = False

    # _output_coll, _output_off = further(_feature_map)
    # output_coll[0], output_off[0] = _output_coll, _output_off

    # loss2 = criterion['L2'](_output_coll, target_coll[0]) * 10
    # loss3 = criterion['L2'](_output_off, target_off[0]) * 10
    # loss = loss0 + loss2 + loss3
    # LOSS[0, 0] = from_variable_to_numpy(loss0)
    # LOSS[0, 2] = from_variable_to_numpy(loss2)
    # LOSS[0, 3] = from_variable_to_numpy(loss3)

    # for i in range(1, args.num_steps + 1):
    #     weight *= args.loss_decay
    #     __feature_map = model(inputs[i])
    #     _outputs = up(__feature_map)
    #     loss0 = criterion['CE'](_outputs, targets[i])
    #     __feature_map = __feature_map.detach()
    #     __feature_map.requires_grad = False

    #     _feature_map = predictor(_feature_map, actions[i - 1])
    #     _prediction = up(_feature_map)
    #     prediction[i] = _prediction
    #     loss1 = criterion['CE'](_prediction, targets[i])

    #     _output_coll, _output_off = further(__feature_map)
    #     output_coll[i], output_off[i] = _output_coll, _output_off

    #     loss2 = criterion['L2'](_output_coll, target_coll[i]) * 10
    #     loss3 = criterion['L2'](_output_off, target_off[i]) * 10
    #     loss += loss0 + weight * (loss1 + loss2 + loss3)

    #     LOSS[i, 0] = from_variable_to_numpy(loss0)
    #     LOSS[i, 1] = from_variable_to_numpy(loss1)
    #     LOSS[i, 2] = from_variable_to_numpy(loss2)
    #     LOSS[i, 3] = from_variable_to_numpy(loss3)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    return LOSS, from_variable_to_numpy(loss)

def visualize_data(args, train_data): # need updating
    clear_visualization_dir(args)
    # batch_id = np.random.randint(args.batch_size)
    # pred = torch.argmax(prediction[:, batch_id, :, :, :], dim = 1)
    # all_obs = torch.round(inputs.data[:, batch_id, -3:, :, :] * args.obs_std + args.obs_avg)
    # if torch.cuda.is_available():
    #     all_obs = all_obs.cpu()
    # all_obs = all_obs.numpy().transpose(0, 2, 3, 1)
    with open(os.path.join(args.visualize_dir, 'cmp.txt'), 'w') as f:
        f.write('target coll:\n%s\n' % str(from_variable_to_numpy(target_coll)))
        f.write('predicted coll:\n%s\n\n' % str(from_variable_to_numpy(output_coll)))
        f.write('target off:\n%s\n' % str(from_variable_to_numpy(target_off)))
        f.write('predicted off:\n%s\n' % str(from_variable_to_numpy(output_off)))
        f.write('target dist:\n%s\n' % str(from_variable_to_numpy(target_dist)))
        f.write('predicted dist:\n%s\n' % str(from_variable_to_numpy(output_dist)))
    # for i in range(args.num_steps + 1):
    #     imsave(os.path.join(args.visualize_dir, '%d.png' % i), np.concatenate((all_obs[i], draw_from_pred(targets[i, batch_id]), draw_from_pred(pred[i])), axis = 1))


def train(args, model, env):
    model.train()
    model.module.dqn.target_Q.eval()

    buffer = replay_buffer(args)
    optimizer = torch.optim.Adam(list(model.parameters()), args.lr, amsgrad = True)
    true_obs, posxyz = reset_env(args, env)

    while True:
        for i in range(50): # args.collect_steps
            data, true_obs, posxyz = sample_one_step(args, true_obs, env, model, posxyz)
            buffer.store(data)
        train_data = buffer.sample()
        return
        LOSS, loss = train_data(args, train_data, model, optimizer)
        args.epoch += 1

        print(LOSS)
        print('Iteration %d, mean loss %f' % (args.epoch, loss))
        with open('pred_log.txt', 'a') as f:
            f.write('%s\nIteration %d, mean loss %f\n' % (str(LOSS), args.epoch, loss))

        if args.epoch % 10 == 0:
            print('Visualizing data.')
            visualize_data(args, train_data)
        
        if args.epoch % 20 == 0:
            target_Q.load_state_dict(convert_state_dict(dqn.state_dict()))
            torch.save(model.state_dict(), os.path.join(args.model_dir, 'model_epoch%d.dat' % args.epoch))
    #     break
    # env.close()