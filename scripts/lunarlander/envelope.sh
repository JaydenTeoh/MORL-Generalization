#!/bin/bash

python3 -u launch_experiment.py \
--algo envelope \
--env-id MOLunarLanderDR-v0 \
--seed 92 \
--num-timesteps 3000000 \
--gamma 0.99 \
--ref-point '-101' '-1001' '-101' '-101' \
--wandb-group 'domain_randomization' \
--test-generalization True \
--init-hyperparams "batch_size:128" "buffer_size:1000000" "net_arch:[256, 256, 256, 256]" initial_epsilon:1.0 final_epsilon:0.05 epsilon_decay_steps:1000000 initial_homotopy_lambda:0.95 num_sample_w:8 target_net_update_freq:1000 \
--train-hyperparams eval_mo_freq:50000 \
--generalization-hyperparams num_eval_weights:100 num_eval_episodes:1 "generalization_algo:'dr_state_action_history'" history_len:2 \
--test-envs "MOLunarLanderDefault-v0,MOLunarLanderHighGravity-v0,MOLunarLanderWindy-v0,MOLunarLanderTurbulent-v0,MOLunarLanderLowMainEngine-v0,MOLunarLanderLowSideEngine-v0,MOLunarLanderStartRight-v0,MOLunarLanderHard-v0" \
# --record-video True \