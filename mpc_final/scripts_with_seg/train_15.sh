#!/bin/bash
python3 train_torcs.py \
    --resume \
    --save-path mpc_15_10_cont \
    --continuous \
    --use-seg \
    --normalize \
    --num-total-act 2 \
    --pred-step 15 \
    --use-collision \
    --use-offroad \
    --use-distance \
    --use-seg \
    --use-pos \
    --use-angle \
    --use-speed \
    --use-xyz \
    --use-dqn \
    --num-dqn-action 10 \
    --sample-with-angle \
    --num-same-step 1 \
    --target-speed 2 \
    --id 13
