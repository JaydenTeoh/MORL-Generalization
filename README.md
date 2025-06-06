# MORL-Generalization

<img src="https://github.com/user-attachments/assets/22096c55-9e1c-4f56-b444-3e9085b5a300" width="100%" alt="GIFS of environments in MORL-Generalization" />
&nbsp

MORL-Generalization is a benchmark for evaluating the capabilities of Multi-Objective Reinforcement Learning (MORL) algorithms to generalize across environments. This software is developed as part of our ICLR'25 paper ["On Generalization Across Environments In Multi-Objective Reinforcement Learning"](https://arxiv.org/abs/2503.00799).

Our domains are adapted from [MO-Gymnasium](https://github.com/Farama-Foundation/mo-gymnasium) and the implementations of the baseline algorithms are adapted from [MORL-Baselines](https://github.com/LucasAlegre/morl-baselines).

## Setup
To install the necessary dependencies, first make sure you have the necessary packages to install [pycddlib](https://pycddlib.readthedocs.io/en/latest/quickstart.html). Then, run the following commands:
```bash
pip install swig
pip install -r requirements.txt
```

## Dataset
The evaluations of 8 state-of-the-art algorithms and SAC on our benchmark domains can be found on [https://wandb.ai/jayden-teoh/MORL-Generalization](https://wandb.ai/jayden-teoh/MORL-Generalization).
There are also CSV files of the data (for metrics specific to plotting results in the paper) in the `/plotting/data` folder.

## Instructions
1. To run the same experiments as in the paper, please refer to the `/scripts` folder.
2. To plot the results, please refer to the `/experiments/plotting/notebooks` folder for the Jupyter notebooks labelled step by step with Markdown explanations.
3. The algorithms are adapted from [MORL-Baselines](https://github.com/LucasAlegre/morl-baselines) and can be found in the `/algos` folder. However, note that there are additional experimental algorithms like MORL/D-Discrete, asymmetric actor-critic, recurrent GPI-LS (see old commits) implemented which are unique to our codebase, though not presented in the paper.
4. The benchmark evironments can be found in the `/envs` folder.
5. The `MORLGeneralizationEvaluator` class is responsible for all evaluations regarding MORL-Generalization and can be found in `morl_generalization/generalization_evaluator.py`.

If further clarification is needed beyond the codebase, feel free to put in an issue or contact me directly at t3ohjingxiang[at]gmail.com and I will be responsive.

## Updates
**[2025/01]** Our paper "On Generalization Across Environments In Multi-Objective Reinforcement Learning" has been accepted at ICLR 2025! 🎉🎉

## Citing

<!-- start citation -->

If you use this repository in your research, please cite:
```bibtex
@inproceedings{
  teoh2025morlgeneralization,
  title={On Generalization Across Environments In Multi-Objective Reinforcement Learning},
  author={Jayden Teoh and Pradeep Varakantham and Peter Vamplew},
  booktitle={The Thirteenth International Conference on Learning Representations},
  year={2025},
  url={https://openreview.net/forum?id=tuEP424UQ5}
}
```
Please also cite [MO-Gymnasium](https://github.com/Farama-Foundation/mo-gymnasium) if you use any of the baseline algorithms for evaluations.
