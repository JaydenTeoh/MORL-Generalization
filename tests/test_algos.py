"""Mostly tests to make sure the algorithms are able to run."""
import time

import mo_gymnasium as mo_gym
import gymnasium as gym
import numpy as np
import torch as th
from mo_gymnasium.envs.deep_sea_treasure.deep_sea_treasure import CONCAVE_MAP

from mo_utils.evaluation import eval_mo, eval_mo_reward_conditioned
from mo_utils.scalarization import tchebicheff
from algos.multi_policy.capql.capql import CAPQL
from algos.multi_policy.envelope.envelope import Envelope
from algos.multi_policy.gpi_pd.gpi_pd import GPIPD
from algos.multi_policy.gpi_pd.gpi_pd_continuous_action import (
    GPIPDContinuousAction,
)
from algos.multi_policy.linear_support.linear_support import LinearSupport
from algos.multi_policy.multi_policy_moqlearning.mp_mo_q_learning import (
    MPMOQLearning,
)
from algos.multi_policy.pareto_q_learning.pql import PQL
from algos.multi_policy.pcn.pcn import PCN
from algos.multi_policy.pgmorl.pgmorl import PGMORL
from algos.single_policy.esr.eupg import EUPG
from algos.single_policy.ser.mo_q_learning import MOQLearning


from envs.registration import make as gym_make
from morl_generalization.generalization_evaluator import MORLGeneralizationEvaluator

def test_pql():
    env_id = "deep-sea-treasure-v0"
    env = mo_gym.make(env_id, dst_map=CONCAVE_MAP)
    ref_point = np.array([0, -25])

    agent = PQL(
        env,
        ref_point,
        gamma=1.0,
        initial_epsilon=1.0,
        epsilon_decay_steps=5000,
        final_epsilon=0.2,
        seed=1,
        log=False,
    )

    # Training
    pf = agent.train(total_timesteps=1000, log_every=100, action_eval="hypervolume", ref_point=ref_point, eval_env=env)
    assert len(pf) > 0

    # Policy following
    target = np.array(pf.pop())
    tracked = agent.track_policy(target, env=env)
    assert np.all(tracked == target)


def test_eupg():
    env = mo_gym.make("fishwood-v0")
    eval_env = mo_gym.make("fishwood-v0")

    def scalarization(reward: np.ndarray, w=None):
        reward = th.tensor(reward) if not isinstance(reward, th.Tensor) else reward
        # Handle the case when reward is a single tensor of shape (2, )
        if reward.dim() == 1 and reward.size(0) == 2:
            return min(reward[0], reward[1] // 2).item()

        # Handle the case when reward is a tensor of shape (200, 2)
        elif reward.dim() == 2 and reward.size(1) == 2:
            return th.min(reward[:, 0], reward[:, 1] // 2)

    agent = EUPG(env, scalarization=scalarization, gamma=0.99, log=False)
    agent.train(total_timesteps=10000, eval_env=eval_env, eval_freq=100)

    scalar_return, scalarized_disc_return, vec_ret, vec_disc_ret = eval_mo_reward_conditioned(
        agent, env=eval_env, scalarization=scalarization, w=np.ones(2)
    )
    assert len(vec_ret) == 2
    assert len(vec_disc_ret) == 2


def test_moql():
    env_id = "deep-sea-treasure-v0"
    env = mo_gym.make(env_id, dst_map=CONCAVE_MAP)
    eval_env = mo_gym.make(env_id, dst_map=CONCAVE_MAP)
    scalarization = tchebicheff(tau=4.0, reward_dim=2)
    weights = np.array([0.3, 0.7])

    agent = MOQLearning(env, scalarization=scalarization, weights=weights, log=False)
    agent.train(
        total_timesteps=1000,
        start_time=time.time(),
        eval_freq=100,
        eval_env=eval_env,
    )

    scalar_return, scalarized_disc_return, vec_ret, vec_disc_ret = eval_mo(agent, env=eval_env, w=weights)
    assert scalar_return != 0
    assert scalarized_disc_return != 0
    assert len(vec_ret) == 2
    assert len(vec_disc_ret) == 2


def test_mp_moql():
    env_id = "deep-sea-treasure-v0"
    env = mo_gym.make(env_id, dst_map=CONCAVE_MAP)
    eval_env = mo_gym.make(env_id, dst_map=CONCAVE_MAP)
    scalarization = tchebicheff(tau=4.0, reward_dim=2)

    agent = MPMOQLearning(
        env,
        scalarization=scalarization,
        initial_epsilon=0.9,
        epsilon_decay_steps=int(1e3),
        log=False,
    )
    agent.train(eval_env=eval_env, ref_point=np.array([0.0, -25.0]), total_timesteps=2000, timesteps_per_iteration=1000)

    front = agent.linear_support.ccs
    assert len(front) > 0


def test_ols():
    env = mo_gym.make("deep-sea-treasure-v0")

    ols = LinearSupport(num_objectives=2, epsilon=0.1, verbose=False)
    policies = []
    while True:
        w = ols.next_weight()
        if ols.ended():
            break

        new_policy = MOQLearning(
            env,
            weights=w,
            learning_rate=0.3,
            gamma=0.9,
            initial_epsilon=1,
            final_epsilon=0.01,
            epsilon_decay_steps=int(1e5),
            log=False,
        )
        new_policy.train(0, total_timesteps=int(1e4))

        _, _, vec, discounted_vec = new_policy.policy_eval(eval_env=env, weights=w)
        policies.append(new_policy)

        removed_inds = ols.add_solution(discounted_vec, w)

        for ind in removed_inds:
            policies.pop(ind)  # remove policies that are no longer needed


def test_envelope():
    env = mo_gym.make("minecart-v0")
    eval_env = mo_gym.make("minecart-v0")

    agent = Envelope(
        env,
        log=False,
    )

    agent.train(
        total_timesteps=1000,
        eval_env=eval_env,
        ref_point=np.array([0.0, 0.0, -200.0]),
        eval_freq=100,
    )

    scalar_return, scalarized_disc_return, vec_ret, vec_disc_ret = eval_mo(agent, env=eval_env, w=np.array([0.5, 0.4, 0.1]))
    assert scalar_return != 0
    assert scalarized_disc_return != 0
    assert len(vec_ret) == 3
    assert len(vec_disc_ret) == 3


def test_gpi_pd():
    env = mo_gym.make("minecart-v0")
    eval_env = mo_gym.make("minecart-v0")

    agent = GPIPD(
        env,
        log=False,
    )

    agent.train_iteration(
        total_timesteps=1000,
        weight=np.array([1.0, 0.0, 0.0]),
        weight_support=[np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])],
        eval_env=eval_env,
        eval_freq=100,
    )

    scalar_return, scalarized_disc_return, vec_ret, vec_disc_ret = eval_mo(agent, env=eval_env, w=np.array([0.5, 0.4, 0.1]))
    assert scalar_return != 0
    assert scalarized_disc_return != 0
    assert len(vec_ret) == 3
    assert len(vec_disc_ret) == 3


def test_gpi_pd_continuous_action():
    env = mo_gym.make("mo-hopper-v4", cost_objective=False, max_episode_steps=500)
    eval_env = mo_gym.make("mo-hopper-v4", cost_objective=False, max_episode_steps=500)

    agent = GPIPDContinuousAction(
        env,
        log=False,
    )

    agent.train_iteration(
        total_timesteps=1000,
        weight=np.array([1.0, 0.0]),
        weight_support=[np.array([0.0, 1.0])],
        eval_env=eval_env,
        eval_freq=100,
    )

    scalar_return, scalarized_disc_return, vec_ret, vec_disc_ret = eval_mo(agent, env=eval_env, w=np.array([0.5, 0.5]))
    assert scalar_return != 0
    assert scalarized_disc_return != 0
    assert len(vec_ret) == 2
    assert len(vec_disc_ret) == 2


# This test is a bit long to execute, idk what to do with it.
def test_pgmorl():
    env_id = "mo-mountaincarcontinuous-v0"
    eval_env = mo_gym.make(env_id)
    algo = PGMORL(
        env_id=env_id,
        origin=np.array([0.0, 0.0]),
        num_envs=4,
        pop_size=6,
        warmup_iterations=2,
        evolutionary_iterations=2,
        num_weight_candidates=5,
        log=False,
    )
    algo.train(eval_env=eval_env, total_timesteps=int(1e4), ref_point=np.array([0.0, 0.0]))

    # Execution of trained policies
    for a in algo.archive.individuals:
        scalarized, discounted_scalarized, reward, discounted_reward = eval_mo(
            agent=a, env=eval_env, w=np.array([1.0, 1.0]), render=False
        )
        assert scalarized != 0
        assert discounted_scalarized != 0
        assert len(reward) == 2
        assert len(discounted_reward) == 2


def test_pcn():
    env = mo_gym.make("minecart-deterministic-v0")

    agent = PCN(
        env,
        scaling_factor=np.array([1, 1, 0.1, 0.1]),
        learning_rate=1e-3,
        batch_size=256,
        log=False,
    )

    agent.train(
        total_timesteps=10,
        ref_point=np.array([0, 0, -200.0]),
        num_er_episodes=1,
        max_buffer_size=50,
        num_model_updates=50,
        max_return=np.array([1.5, 1.5, -0.0]),
        eval_env=env,
    )

    agent.set_desired_return_and_horizon(np.array([1.5, 1.5, -0.0]), 100)
    scalar_return, scalarized_disc_return, vec_ret, vec_disc_ret = eval_mo(
        agent, env=env, w=np.array([0.4, 0.4, 0.2]), render=False
    )
    assert scalar_return != 0
    assert scalarized_disc_return != 0
    assert len(vec_ret) == 3
    assert len(vec_disc_ret) == 3


def test_capql():
    env = mo_gym.make("mo-hopper-v4", cost_objective=False, max_episode_steps=500)
    eval_env = mo_gym.make("mo-hopper-v4", cost_objective=False, max_episode_steps=500)

    agent = CAPQL(
        env,
        log=False,
    )

    agent.train(
        total_timesteps=1000,
        eval_env=eval_env,
        ref_point=np.array([0.0, 0.0]),
        eval_freq=100,
    )

    scalar_return, scalarized_disc_return, vec_ret, vec_disc_ret = eval_mo(agent, env=eval_env, w=np.array([0.5, 0.5]))
    assert scalar_return != 0
    assert scalarized_disc_return != 0
    assert len(vec_ret) == 2
    assert len(vec_disc_ret) == 2


def test_capql_dr():
    env = gym_make("MOLunarLanderDR-v0", seed=88)
    eval_env = gym_make("MOLunarLanderDR-v0", seed=88)
    env = MORLGeneralizationEvaluator(env, 
                          generalization_algo="domain_randomization", 
                          test_env=[
                                "MOLunarLanderDR-v0",
                                "LunarLanderEvalOne",
                                "LunarLanderEvalTwo",
                                "LunarLanderEvalThree",
                                "LunarLanderEvalFour"
                              ])

    agent = CAPQL(
        env,
        log=False,  
        test_generalization=True
    )

    agent.train(
        total_timesteps=1000,
        eval_env=eval_env,
        ref_point=np.array([0.0, 0.0]),
        eval_freq=100,
    )

    scalar_return, scalarized_disc_return, vec_ret, vec_disc_ret = eval_mo(agent, env=eval_env, w=np.array([0.5, 0.5]))
    assert scalar_return != 0
    assert scalarized_disc_return != 0
    assert len(vec_ret) == 2
    assert len(vec_disc_ret) == 2
