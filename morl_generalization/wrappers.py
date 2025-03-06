import os
import numpy as np
from typing import Callable, List

import gymnasium as gym
from gymnasium import error, logger
from gymnasium.core import ActType, ObsType, RenderFrame
from gymnasium.wrappers import FlattenObservation, FrameStackObservation

class ObsToNumpy(gym.ObservationWrapper):
    def __init__(self, env):
        super().__init__(env)

    def observation(self, obs):
        return np.asarray(obs)
    
class StateHistoryWrapper(gym.Wrapper, gym.utils.RecordConstructorArgs):
    def __init__(self, env: gym.Env, history_len: int = 3):
        """
            Augments the observation with
            a stack of the previous "history_len" states
            observed.
        """
        gym.utils.RecordConstructorArgs.__init__(self, history_len=history_len)
        gym.Wrapper.__init__(self, env)

        self.history_len = history_len
        env = FrameStackObservation(env, history_len + 1)  # FrameStackObservation considers the current obs as 1 stack
        env = ObsToNumpy(env)
        env = FlattenObservation(env)
        self.env = env

class ActionHistoryWrapper(gym.Wrapper, gym.utils.RecordConstructorArgs):
    def __init__(self, env: gym.Env, history_len: int = 3):
        """
            Augments the observation with
            a stack of the previous "history_len" actions
            taken.
        """
        gym.utils.RecordConstructorArgs.__init__(self, history_len=history_len)
        gym.Wrapper.__init__(self, env)
        assert env.action_space.sample().ndim == 1, 'Actions are assumed to be flat on one-dim vector'

        self.history_len = history_len
        self.actions_buffer = np.zeros((history_len, env.action_space.shape[0]), dtype=np.float32)

        # Modify the observation space to include the history buffer
        obs_space = env.observation_space
        action_stack_low = np.repeat(env.action_space.low, history_len)
        action_stack_high = np.repeat(env.action_space.high, history_len)
        low = np.concatenate([obs_space.low.flatten(), action_stack_low], axis=0)
        high = np.concatenate([obs_space.high.flatten(), action_stack_high], axis=0)
        self.observation_space = gym.spaces.Box(low=low, high=high, dtype=obs_space.dtype)

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self.actions_buffer.fill(0)
        return self._stack_actions_to_obs(obs), info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        self.actions_buffer[:-1] = self.actions_buffer[1:]
        self.actions_buffer[-1] = action
        obs = self._stack_actions_to_obs(obs)
        return obs, reward, terminated, truncated, info

    def _stack_actions_to_obs(self, obs):
        obs = np.concatenate([obs.flatten(), self.actions_buffer.flatten()], axis=0)
        return obs
    
class HistoryWrapper(gym.Wrapper, gym.utils.RecordConstructorArgs):
    def __init__(self, env: gym.Env, history_len: int = 3, state_history=False, action_history=False):
        """
            Augments the observation with a stack of the previous "history_len" states and actions observed.
            e.g. for history_len=3, the observation will be: [s_{t-3}, a_{t-3}, s_{t-2}, a_{t-2}, s_{t-1}, a_{t-1}, s_t]
        """
        gym.utils.RecordConstructorArgs.__init__(self, history_len=history_len)
        gym.Wrapper.__init__(self, env)

        self.history_len = history_len
        self.state_history = state_history
        self.action_history = action_history

        self.is_discrete = isinstance(env.action_space, gym.spaces.Discrete)

        if not self.is_discrete:
            assert env.action_space.sample().ndim == 1, 'Actions are assumed to be flat on one-dim vector'

        if self.state_history:
            self.states_buffer = np.zeros((history_len, env.observation_space.shape[0]), dtype=np.float32)
        if self.action_history:
            if self.is_discrete:
                self.actions_buffer = np.zeros((history_len,), dtype=np.int32)  # int for discrete
            else:
                self.actions_buffer = np.zeros((history_len, env.action_space.shape[0]), dtype=np.float32)

        # Modify the observation space to include the history buffer
        new_obs_low = []
        new_obs_high = []
        for _ in range(history_len):
            if self.state_history:
                new_obs_low.extend(env.observation_space.low.flatten())
                new_obs_high.extend(env.observation_space.high.flatten())
            if self.action_history:
                if self.is_discrete:
                    new_obs_low.append(0)  # Min action (always 0 for Discrete)
                    new_obs_high.append(env.action_space.n - 1)  # Max action
                else:
                    new_obs_low.extend(env.action_space.low.flatten())
                    new_obs_high.extend(env.action_space.high.flatten())
        low = np.concatenate([new_obs_low, env.observation_space.low.flatten()])
        high = np.concatenate([new_obs_high, env.observation_space.high.flatten()])
        self.observation_space = gym.spaces.Box(low=low, high=high, dtype=env.observation_space.dtype)

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        if self.action_history:
            self.actions_buffer.fill(0)
        if self.state_history:
            self.states_buffer[:] = obs # fill the buffer with the repeated initial state
        return self._stack_actions_states_to_obs(obs), info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        if self.action_history:
            self.actions_buffer[:-1] = self.actions_buffer[1:]
            self.actions_buffer[-1] = action
        stack_obs = self._stack_actions_states_to_obs(obs)
        if self.state_history:
            self.states_buffer[:-1] = self.states_buffer[1:]
            self.states_buffer[-1] = obs
        return stack_obs, reward, terminated, truncated, info

    def _stack_actions_states_to_obs(self, obs):
        for i in range(self.history_len - 1, -1, -1):
            if self.action_history:
                obs = np.concatenate([self.actions_buffer[i].flatten(), obs.flatten()], axis=0)
            if self.state_history:
                obs = np.concatenate([self.states_buffer[i].flatten(), obs.flatten()], axis=0)
        return obs


def capped_cubic_video_schedule(episode_id: int) -> bool:
    """The default episode trigger.

    This function will trigger recordings at the episode indices 0, 1, 8, 27, ..., :math:`k^3`, ..., 729, 1000, 2000, 3000, ...

    Args:
        episode_id: The episode number

    Returns:
        If to apply a video schedule number
    """
    if episode_id < 1000:
        return int(round(episode_id ** (1.0 / 3))) ** 3 == episode_id
    else:
        return episode_id % 1000 == 0

    
class MORecordVideo(gym.Wrapper[ObsType, ActType, ObsType, ActType], gym.utils.RecordConstructorArgs):
    """Multi-objective RecordVideo wrapper for recording videos. 
    Allows intermittent recording of videos based on number of weights evaluted by specifying ``weight_trigger``.
    To increased weight_number, call `env.reset(options={"weights": w, "step":s})` at the beginning of each evaluation. 
    If weight trigger is activated, the video recorded file name will include the  current step `s` and evaluated weight `w` as a suffix. 
    `w` must be a numpy array and `s` must be an integer.
    """

    def __init__(
        self,
        env: gym.Env,
        video_folder: str,
        weight_trigger: Callable[[int], bool] = None,
        episode_trigger: Callable[[int], bool] = None,
        step_trigger: Callable[[int], bool] = None,
        video_length: int = 0,
        name_prefix: str = "mo-rl-video",
        fps: int | None = None,
        disable_logger: bool = False,
    ):
        """Wrapper records videos of rollouts.

        Args:
            env: The environment that will be wrapped
            video_folder (str): The folder where the recordings will be stored
            weight_trigger: Function that accepts an integer and returns ``True`` iff a recording should be started at this weight evaluation
            episode_trigger: Function that accepts an integer and returns ``True`` iff a recording should be started at this episode
            step_trigger: Function that accepts an integer and returns ``True`` iff a recording should be started at this step
            video_length (int): The length of recorded episodes. If 0, entire episodes are recorded.
                Otherwise, snippets of the specified length are captured
            name_prefix (str): Will be prepended to the filename of the recordings
            disable_logger (bool): Whether to disable moviepy logger or not.
        """
        gym.utils.RecordConstructorArgs.__init__(
            self,
            video_folder=video_folder,
            episode_trigger=episode_trigger,
            weight_trigger=weight_trigger,
            step_trigger=step_trigger,
            video_length=video_length,
            name_prefix=name_prefix,
            disable_logger=disable_logger,
        )
        gym.Wrapper.__init__(self, env)

        if env.render_mode in {None, "human", "ansi", "ansi_list"}:
            raise ValueError(
                f"Render mode is {env.render_mode}, which is incompatible with"
                f" RecordVideo. Initialize your environment with a render_mode"
                f" that returns an image, such as rgb_array."
            )
        if episode_trigger is None and step_trigger is None and weight_trigger is None:
            episode_trigger = capped_cubic_video_schedule

        trigger_count = sum(x is not None for x in [episode_trigger, step_trigger, weight_trigger])
        assert trigger_count == 1, "Must specify exactly one trigger"

        self.weight_trigger = weight_trigger
        self.episode_trigger = episode_trigger
        self.step_trigger = step_trigger
        self.disable_logger = disable_logger

        self.video_folder = os.path.abspath(video_folder)
        # Create output folder if needed
        if os.path.isdir(self.video_folder):
            logger.warn(
                f"Overwriting existing videos at {self.video_folder} folder "
                f"(try specifying a different `video_folder` for the `RecordVideo` wrapper if this is not desired)"
            )
        os.makedirs(self.video_folder, exist_ok=True)

        if fps is None:
            fps = self.metadata.get("render_fps", 30)
        self.frames_per_sec: int = fps
        self.name_prefix: str = name_prefix
        self._video_name: str | None = None
        self.video_length: int = video_length if video_length != 0 else float("inf")
        self.recording: bool = False
        self.recorded_frames: list[RenderFrame] = []
        self.render_history: list[RenderFrame] = []

        self.step_id = -1
        self.episode_id = -1

        # Custom multi-objective attributes
        self.weight_id = -1
        self.current_weight = None
        self.current_step = 0

        try:
            self.is_vector_env = self.get_wrapper_attr("is_vector_env")
        except AttributeError:
            self.is_vector_env = False

    def _capture_frame(self):
        assert self.recording, "Cannot capture a frame, recording wasn't started."

        frame = self.env.render()
        if isinstance(frame, List):
            if len(frame) == 0:  # render was called
                return
            self.render_history += frame
            frame = frame[-1]

        if isinstance(frame, np.ndarray):
            self.recorded_frames.append(frame)
        else:
            self.stop_recording()
            logger.warn(
                f"Recording stopped: expected type of frame returned by render to be a numpy array, got instead {type(frame)}."
            )

    def reset(self, **kwargs):
        """Reset the environment, set multi-objective weights if provided, and start video recording if enabled."""
        # Check for multi-objective weights in kwargs
        options = kwargs.get("options", {})
        if options and "weights" in options and "step" in options:
            assert isinstance(options["weights"], np.ndarray)
            assert isinstance(options["step"], int)
            self.current_weight = np.array2string(options["weights"], precision=2, separator=',')
            self.weight_id += 1
            self.current_step = options["step"]
        
        observations = super().reset(**kwargs)
        self.episode_id += 1
        if self.recording and self.video_length == float("inf"):
            self.stop_recording()

        if self.episode_trigger and self.episode_trigger(self.episode_id):
            self.start_recording(f"{self.name_prefix}-episode-{self.episode_id}")
        if self.weight_trigger and self.weight_trigger(self.weight_id):
            self.start_recording(f"{self.name_prefix}-step{self.current_step}-weight-{self.current_weight}")
        if self.recording:
            self._capture_frame()
            if len(self.recorded_frames) > self.video_length:
                self.stop_recording()

        return observations

    def step(self, action):
        """Steps through the environment using action, recording observations if :attr:`self.recording`."""
        (
            observations,
            rewards,
            terminateds,
            truncateds,
            infos,
        ) = self.env.step(action)

        self.step_id += 1

        if self.step_trigger and self.step_trigger(self.step_id):
            self.start_recording(f"{self.name_prefix}-step-{self.step_id}")
        if self.recording:
            self._capture_frame()

            if len(self.recorded_frames) > self.video_length:
                self.stop_recording()

        return observations, rewards, terminateds, truncateds, infos

    def render(self) -> RenderFrame | list[RenderFrame]:
        """Compute the render frames as specified by render_mode attribute during initialization of the environment."""
        render_out = super().render()
        if self.recording and isinstance(render_out, List):
            self.recorded_frames += render_out

        if len(self.render_history) > 0:
            tmp_history = self.render_history
            self.render_history = []
            return tmp_history + render_out
        else:
            return render_out

    def close(self):
        """Closes the wrapper then the video recorder."""
        super().close()
        if self.recording:
            self.stop_recording()

    def start_recording(self, video_name: str):
        """Start a new recording. If it is already recording, stops the current recording before starting the new one."""
        if self.recording:
            self.stop_recording()

        self.recording = True
        self._video_name = video_name

    def stop_recording(self):
        """Stop current recording and saves the video."""
        assert self.recording, "stop_recording was called, but no recording was started"

        if len(self.recorded_frames) == 0:
            logger.warn("Ignored saving a video as there were zero frames to save.")
        else:
            try:
                from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
            except ImportError as e:
                raise error.DependencyNotInstalled(
                    'MoviePy is not installed, run `pip install "gymnasium[other]"`'
                ) from e

            clip = ImageSequenceClip(self.recorded_frames, fps=self.frames_per_sec)
            moviepy_logger = None if self.disable_logger else "bar"
            path = os.path.join(self.video_folder, f"{self._video_name}.mp4")
            clip.write_videofile(path, logger=moviepy_logger)

        self.recorded_frames = []
        self.recording = False
        self._video_name = None

    def __del__(self):
        """Warn the user in case last video wasn't saved."""
        if len(self.recorded_frames) > 0:
            logger.warn("Unable to save last video! Did you call close()?")