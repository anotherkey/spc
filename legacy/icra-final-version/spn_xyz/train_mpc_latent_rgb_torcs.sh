#!/bin/bash
python train_torcs.py \
    --pred-step 10 \
    --save-path 'torcs_mpc_latent_rgb_pred_10' \
    --buffer-size 50000 \
    --num-total-act 2 \
    --epsilon-frames 100000 \
    --resume \
    --seed 0 \
    --data-parallel \
    --batch-size 32 \
    --num-train-steps 100 \
    --env 'torcs-v0' \
    --continuous \
    --use-collision \
    --use-offroad \
    --use-distance \
    --use-speed \
    --sample-with-offroad \
    --sample-with-collision \
    --sample-with-distance \
    --id 20