# -*- coding: utf-8 -*-

__author__ = 'Brett Feltmate'

import klibs
from klibs import P
from klibs.KLAudio import Tone
from klibs.KLExceptions import TrialException
from klibs.KLGraphics import KLDraw as kld
from klibs.KLConstants import STROKE_INNER
from klibs.KLCommunication import message
from klibs.KLGraphics import fill, flip, blit, clear
from klibs.KLText import add_text_style
from klibs.KLUserInterface import (
    key_pressed,
    pump,
    ui_request,
    get_clicks,
    mouse_pos,
    smart_sleep,
)
from klibs.KLBoundary import BoundarySet, CircleBoundary, RectangleBoundary

from math import trunc
from random import randrange, choice, shuffle


# For Arduino communication
# from pyfirmata import serial # commented out from og file


# Trigger values sent to PLATO goggles via Arduino
OPEN = b'55'
CLOSE = b'56'
BAUD = 9600

# Dummy class to replace actual goggles/Arduino hardware
class DummyGoggles:
    def __init__(self, *args, **kwargs):
        pass

    def write(self, *args, **kwargs):
        # Do nothing — prevents crashes when the experiment
        # calls self.goggles.write(OPEN/CLOSE)
        pass

#Stimulus and Task Constrants 

# Stimulus sizes
UNIT = 9  # 9 mm; converted to px at runtime
CIRCLE_DIAM = 2  # this & rest are multiples of UNIT
OFFSET = 21  # up from screen bottom
RECT_WIDTH = 13
RECT_HEIGHT = 9
FIX_WIDTH = 2
THICKNESS = 0.1  # thickness of stimulus [out]lines

# Colors
RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
WHITE = (255, 255, 255, 255)
NONE = (0, 0, 0, 0)

# Color-outcome mappings
PENALTY_OUTLINE = RED
PENALTY_FILL = NONE
REWARD_OUTLINE = GREEN
REWARD_FILL = NONE

# Point values
REWARD_PAYOUT = 100
PENALTY_PAYOUT = -600
VENN_PAYOUT = -500
MISS_PAYOUT = 0
TIMEOUT_PAYOUT = -700

# Simulus onset asynchronies
RECT_ONSET = 1000  # fix (immediate) -> rect
CIRC_ONSET = 500  # rect -> circles
PREVIEW_WINDOW = 300   # circle onset -> go signal
TIMEOUT_AFTER = 650  # circles -> (no) response

# Labels
COM6 = 'COM6'  # Serial port for arduino communication
START = 'start'
FIX = 'fix'
RECT = 'rect'
REWARD = 'reward'
VISION = 'vision'
PENALTY = 'penalty'
OUTSIDE = 'outside'
OVERLAP = 'overlap'
ENDPOINT = 'endpoint'
SPACE = 'space'
RECTANGLE_ONSET = 'rectangle_onset'
CIRCLE_ONSET = 'circle_onset'
GO_SIGNAL = 'go_signal'
TRIAL_TIMEOUT = 'trial_timeout'
NA = 'NA'

#New feedback conditions
REWARD_VAR = 'reward_var'      # Condition 1: reward varies, penalty fixed
PENALTY_VAR = 'penalty_var'    # Condition 2: penalty varies, reward fixed
BOTH_VAR = 'both_var'          # Condition 3: both vary


class reward_feedback_pointing_2025(klibs.Experiment):
    # Run first, and once, at the start of the experiment
    def setup(self):

	# needed to comment out for new set up
	#      	 if P.condition not in ["reward_var", "penalty_var", "both_var"]:
	#    raise ValueError(
	#        "Condition must be one of: reward_var, penalty_var, both_var.\n"
	#        "Run using, e.g.: klibs run 24 -c reward_var"
	#    )

        self.fixed_condition = REWARD_VAR

        # Randomize the order of all four probability blocks
        self.probability_block_order = [
            "50_50",
            "50_50",
            "80_20_low",
            "80_20_high"
        ]
        shuffle(self.probability_block_order)

        print("PROBABILITY BLOCK ORDER:", self.probability_block_order, flush=True)


    # Handles communication with arduino (goggles)
        # self.goggles = serial.Serial(port=COM6, baudrate=BAUD) #commented out for this 
        self.goggles = DummyGoggles()

        # Earnings total 
        self.total_earnings = 0
	
        # Go-signal
        self.go_tone = Tone(100)

        #
        #   Set up visual properties
        #

        # Now that screensize is known, convert sizes to px
        self.unit = (P.ppi / 25.4) * UNIT
        self.offset = self.unit * OFFSET
        self.rect_w = self.unit * RECT_WIDTH
        self.rect_h = self.unit * RECT_HEIGHT
        self.target_circle_d = self.unit * CIRCLE_DIAM
        self.start_circle_d = self.unit * CIRCLE_DIAM * 3
        self.fix_w = self.unit * FIX_WIDTH
        self.thick = self.unit * THICKNESS


    # Define visual stimulus objects
        self.stimuli = {
            START: kld.Circle(
                diameter=self.start_circle_d,
                fill=BLUE,
                stroke=[self.thick, BLUE, STROKE_INNER],
            ),
            FIX: kld.FixationCross(
                size=self.fix_w, thickness=self.thick, fill=WHITE
            ),
            RECT: kld.Rectangle(
                width=self.rect_w,
                height=self.rect_h,
                stroke=[self.thick, BLUE, STROKE_INNER],
            ),
            REWARD: kld.Circle(
                diameter=self.target_circle_d,
                fill=REWARD_FILL,
                stroke=[self.thick, REWARD_OUTLINE, STROKE_INNER],
            ),
            PENALTY: kld.Circle(
                diameter=self.target_circle_d,
                fill=PENALTY_FILL,
                stroke=[self.thick, PENALTY_OUTLINE, STROKE_INNER],
            ),
            ENDPOINT: kld.Asterisk(
                size=self.target_circle_d // 3,
                thickness=self.thick * 2,
                fill=WHITE,
            ),
        }

        # Define boundaries for touch detection
        # TODO: add KLibs feature: accept KLDrawbject, create matching boundary
        self.bs = BoundarySet()
        self.bs.add_boundary(
            CircleBoundary(
                label=START,
                center=(P.screen_x / 2, P.screen_y),  
                radius=self.start_circle_d / 2,  
            )
        )
        self.bs.add_boundary(
            RectangleBoundary(
                label=RECT,
                p1=(
                    (P.screen_x / 2) + (self.rect_w / 2),                          			(P.screen_y - self.offset) - (self.rect_h / 2),  # type: ignore[operator]
                ),
                p2=(
                    (P.screen_x / 2) - (self.rect_w / 2),  # type: ignore[operator]
                    (P.screen_y - self.offset) + (self.rect_h / 2),  # type: ignore[operator]
                ),
            )
        )

        #
        #   Set up condition order
        #

        
        # All blocks in this run use the same feedback condition.
        # self.conditions = [P.condition] * P.blocks_per_experiment
        self.conditions = [self.fixed_condition] * P.blocks_per_experiment

        # If desired, insert practice block at start of experiment
        if P.run_practice_blocks:
            self.insert_practice_block(
                block_nums=[1],
                trial_counts=P.trials_per_practice_block,  
            )

        #
        #   Instruction set
        #

        self.instructions = {
            REWARD_VAR: (
                "On each trial, you will see two overlapping circles:\n"
                "GREEN = reward (+600 or +100)\n"
                "RED = penalty (-100) \n\n"
                "The overlapping region is worth the sum of the reward and penalty circles.\n\n"
                "After each trial, you will see your trial payout\n"
                "and your total points so far.\n\n"
                "Your goal is to earn as many points as possible.\n"
            ),
            PENALTY_VAR: (
                "In this block, the PENALTY amount can change from trial to trial, "
                "but the REWARD amount stays the same.\n\n"
                "Each trial, you'll see two overlapping circles: a GREEN circle (reward) "
                "and a RED circle (penalty). The GREEN circle is always worth +100 points, "
                "and the RED circle will be worth either -100 or -600 points.\n\n"
                "After each trial, you'll see feedback showing + or - and the number of points you gained or lost, "
                "as well as your total points so far.\n\n"
                f"You will complete {P.blocks_per_experiment * P.trials_per_block} trials in this run; "
                "you may take a break between blocks whenever you need."
            ),
            BOTH_VAR: (
                "In this block, BOTH the REWARD and the PENALTY amounts can change from trial to trial.\n\n"
                "Each trial, you'll see two overlapping circles: a GREEN circle (reward) "
                "and a RED circle (penalty). The GREEN circle will be worth either +100 or +600 points, "
                "and the RED circle will be worth either -100 or -600 points.\n\n"
                "After each trial, you'll see feedback showing + or - and the number of points you gained or lost, "
                "as well as your total points so far.\n\n"
                f"You will complete {P.blocks_per_experiment * P.trials_per_block} trials in this run; "
                "you may take a break between blocks whenever you need."
            ),
        }


    # First function called at start of each block
    def block(self):
        self.goggles.write(OPEN)

        # get task condition for block
        if P.practicing:
            self.condition = 'practice'
        else:
            self.condition = self.conditions.pop(0)

            # Track the current testing block
            if not hasattr(self, "probability_block_number"):
                self.probability_block_number = 0

            self.probability_block_number += 1

            # Get the randomized probability condition
            block_type = self.probability_block_order[
                self.probability_block_number - 1
                ]

            if block_type == "50_50":
                self.probability_context = "50_50"
                self.dominant_value = "none"
                n_low = 15
                n_high = 15

            elif block_type == "80_20_low":
                self.probability_context = "80_20"
                self.dominant_value = 100
                n_low = 24
                n_high = 6

            else:
                self.probability_context = "80_20"
                self.dominant_value = 600
                n_low = 6
                n_high = 24

            # Create and randomize the block's reward values
            self.reward_schedule = (
                    [100] * n_low + [600] * n_high
            )
            shuffle(self.reward_schedule)

        # for storing block earnings
        self.bank = 0

        # SCREEN 1: General task instructions
        instrux = '(PRACTICE BLOCK)\n' if P.practicing else '(TESTING BLOCK)\n'

        if not P.practicing:
            instrux += self.instructions[self.condition]

        instrux += "\n\nPress SPACE to continue."

        fill()
        message(
            text=instrux,
            location=(P.screen_x * 0.55, P.screen_y * 0.50),
            blit_txt=True
        )
        flip()

        while True:
            q = pump(True)
            _ = ui_request(queue=q)
            if key_pressed(SPACE, queue=q):
                break

        # SCREEN 2: Block-specific probability instructions
        if not P.practicing:

            if self.probability_context == "50_50":
                probability_text = (
                    "REWARD PROBABILITIES\n\n"
                    "In this block, the two reward values are equally likely.\n\n"
                    "+100 points: 50% of trials\n"
                    "+600 points: 50% of trials"
                )

            elif self.dominant_value == 100:
                probability_text = (
                    "REWARD PROBABILITIES\n\n"
                    "In this block, the reward values have different probabilities.\n\n"
                    "+100 points: 80% of trials\n"
                    "+600 points: 20% of trials"
                )

            else:
                probability_text = (
                    "REWARD PROBABILITIES\n\n"
                    "In this block, the reward values have different probabilities.\n\n"
                    "+100 points: 20% of trials\n"
                    "+600 points: 80% of trials"
                )

            probability_text += (
                "\n\nUse these probabilities to help maximize your points."
                "\n\nPress SPACE to begin the block."
            )

            fill()
            message(
                text=probability_text,
                location=(P.screen_x * 0.55, P.screen_y * 0.50),
                blit_txt=True
            )
            flip()

            while True:
                q = pump(True)
                _ = ui_request(queue=q)
                if key_pressed(SPACE, queue=q):
                    break

    # First function called immediately prior to each trial
    def trial_prep(self):
        print("RUNNING CONDITION:", self.fixed_condition, flush=True)
        self.goggles.write(OPEN)
        # determine circle positions
        self.positions = self.get_circle_placements()
        # Set trial-specific reward and penalty amounts based on feedback condition
        # Default values (used for practice, just in case)
        self.reward_amount = 100
        self.penalty_amount = -600

        if not P.practicing:
            if self.condition == REWARD_VAR:
                # Select the reward value from this block's schedule
                self.reward_amount = self.reward_schedule.pop()
                self.penalty_amount = -100

                # Record whether this trial uses the dominant value
                if self.probability_context == "50_50":
                    self.value_frequency = "equal"
                elif self.reward_amount == self.dominant_value:
                    self.value_frequency = "common"
                else:
                    self.value_frequency = "rare"


            elif self.condition == PENALTY_VAR:
                # Penalty varies: -100 or -600, reward fixed at +100
                self.reward_amount = 100
                self.penalty_amount = choice([-100, -600])

            elif self.condition == BOTH_VAR:
                # Both reward and penalty vary
                self.reward_amount = choice([100, 600])
                self.penalty_amount = choice([-100, -600])

        # How to treat the overlapping region:
        # overlap is now the NET value of the reward and penalty circles
        self.overlap_amount = self.penalty_amount + self.reward_amount

        # this changes for each trial, so needs to be (re)defined here
        self.bs.add_boundaries(
            [
                CircleBoundary(
                    PENALTY,
                    self.positions[PENALTY],
                    self.target_circle_d / 2,
                ),
                CircleBoundary(
                    REWARD,
                    self.positions[REWARD],
                    self.target_circle_d / 2,
                ),
            ]
        )

        # practice trial have "no" timeout, but code is cleaner if made excessively long instead
        trial_timeout = (
            TIMEOUT_AFTER if not P.practicing else 30000
        )  # 30s when practicing

        # Defined event sequence within trial
        self.evm.add_event(RECTANGLE_ONSET, RECT_ONSET)
        self.evm.add_event(CIRCLE_ONSET, CIRC_ONSET, after=RECTANGLE_ONSET)
        self.evm.add_event(GO_SIGNAL, PREVIEW_WINDOW, after=CIRCLE_ONSET)
        self.evm.add_event(TRIAL_TIMEOUT, trial_timeout, after=GO_SIGNAL)

        # present fix
        self.draw_display(fix=True)

        # trial started by having participant contact start position
        at_start_pos = False

        while not at_start_pos:
            # Monitor for any commands to quit, etc
            q = pump(True)
            _ = ui_request(queue=q)

            # NOTE: touchscreens reports touches as left-clicks
            touch_events = get_clicks(queue=q)

            # Break on any touches within start boundary
            if touch_events:
                at_start_pos = self.bs.within_boundary(
                    label=START, p=touch_events[0]
                )

    # Main trial logic
    def trial(self):  # type: ignore[override]

        # When (dev) testing, blit mouse to start position
        if P.development_mode:
            mouse_pos(position=(P.screen_x // 2, P.screen_y))  # type: ignore[operator]

        # Draw stimuli as appropriate; admonish early movements
        while self.evm.before(GO_SIGNAL):
            # Fetch any input events since last loop
            q = pump(True)

            # Check for events of interest
            _ = ui_request(queue=q)
            touch_events = get_clicks(released=True, queue=q)
            if touch_events:
                self.evm.stop_clock()

                msg = message(
                    'Please wait for the tone before moving from the starting position.'
                )
                self.draw_display(
                    also=(msg, self.bs.boundaries[RECT].center),
                )

                smart_sleep(2000)  # type: ignore[attr-defined]

                # NOTE:
                # Return the unused reward value to the schedule
                if not P.practicing:
                    self.reward_schedule.append(self.reward_amount)
                    shuffle(self.reward_schedule)
                # Retry the interrupted trial
                raise TrialException('Premptive movement')

            rect_visible, circles_visible = False, False

            # Draw appropriate stimuli at appropriate time
            if self.evm.after(RECTANGLE_ONSET) and not rect_visible:
                self.draw_display(rect=True)
                rect_visible = True  # don't do redundant redraws

            if (
                self.evm.after(CIRCLE_ONSET)
                and not P.practicing
                and not circles_visible
            ):
                self.draw_display(rect=True, circles=True, show_values=False)
                circles_visible = True

        #
        #   Response period
        #

        # Response period
        self.go_tone.play()
        tone_played_at = self.evm.trial_time_ms

        # Remove numerical values at the go-signal
        # while keeping the circles and rectangle visible
        if not P.practicing:
            self.draw_display(rect=True, circles=True, show_values=False)


        rt, mt, clicked_on, clicked_at, pay = None, None, None, None, None

        while rt is None and self.evm.before(TRIAL_TIMEOUT):
            q = pump(True)
            _ = ui_request(queue=q)

            touch_events = get_clicks(released=True, queue=q)

            if touch_events:
                rt = self.evm.trial_time_ms - tone_played_at  # type: ignore[operator]

                # conditionally close goggles at movement start
                # if self.condition == REWARD:
                #    self.goggles.write(CLOSE)

        while mt is None and self.evm.before(TRIAL_TIMEOUT):
            # q = pump(True)
            # _ = ui_request(queue=q)

            # log touched point, if any
            # FIX: having get_clicks() and listen_for_click() is needlessly confusing
            clicked_at, clicked_on = self.listen_for_click()

            if clicked_on is not None:
                mt = self.evm.trial_time_ms - rt - tone_played_at  # type: ignore[operator]

        #
        #   Feedback phase
        #

        clear()  # the display

        # determine payout
        pay = self.get_payout(clicked_on)
        self.bank += pay
        self.total_earnings += pay

        # Present feedback
        if clicked_on is not None:

            # only movement time provided on practice trials
            if self.condition == 'practice':
                text = f"Movement time was: {trunc(mt)} ms."
                self.draw_display(
                    rect=True,
                    also=(message(text), self.bs.boundaries[RECT].center),
                )
                smart_sleep(P.feedback_duration)  # type: ignore[attr-defined]

            else:
                # On all test trials, display trial payout (+/- value) and total bank.
                # Format payout with an explicit sign.
                if pay > 0:
                    payout_text = f"+{pay}"
                elif pay < 0:
                    payout_text = f"{pay}"  # already has '-'
                else:
                    payout_text = "0"

                # Show trial payout
                msg = message(f"Trial payout: {payout_text}", blit_txt=False)
                self.draw_display(
                    rect=True,
                    also=(msg, self.bs.boundaries[RECT].center),
                )
                smart_sleep(P.feedback_duration)  # type: ignore[attr-defined]

                # Show running total
                msg = message(f"Total points: {self.bank}")
                self.draw_display(
                    rect=True,
                    also=(msg, self.bs.boundaries[RECT].center),
                )
                smart_sleep(1000)  # type: ignore[attr-defined]

        # on failures to complete movement within timeframe
        else:
            msg = message('Trial timed-out!\nNo response was detected!')
            self.draw_display(
                rect=True,
                also=(msg, self.bs.boundaries[RECT].center),
            )

        smart_sleep(P.feedback_duration)  


       
        # Gets aggregated in sqlite database
        return {
            'practicing': P.practicing,
            'block_num': P.block_number,
            'trial_num': P.trial_number,
            'feedback_condition': self.condition,
            'probability_order': "-".join(self.probability_block_order),
            'probability_context': (
                self.probability_context if not P.practicing else "practice"
            ),
            'dominant_value': (
                self.dominant_value if not P.practicing else None
            ),
            'value_frequency': (
                self.value_frequency if not P.practicing else "practice"
            ),
            'reward_side': self.reward_side,  # type: ignore[defined]
            'reward_x': self.positions[REWARD][0],
            'reward_y': self.positions[REWARD][1],
            'clicked_on': clicked_on if clicked_on is not None else NA,
            'clicked_x': clicked_at[0] if clicked_at is not None else NA,
            'clicked_y': clicked_at[1] if clicked_at is not None else NA,
            'reaction_time': rt,
            'movement_time': mt,
            'reward_amount': self.reward_amount,
            'penalty_amount': self.penalty_amount,
            'overlap_amount': self.overlap_amount,
            'trial_earnings': pay,
            'block_earnings': self.bank,
        }

    # Called at end of each trial
    def trial_clean_up(self):
        # If last trial of reward block, present total earnings
        if self.condition in [REWARD_VAR, PENALTY_VAR, BOTH_VAR]:
            if P.trial_number % P.trials_per_block == 0:
                clear()
                self.goggles.write(OPEN)

                fill()
                message(
                    text=f'End of block!\nBlock: {self.bank}\nTotal: {self.total_earnings}\nPress spacebar to continue.',
                    location=P.screen_c,
                    blit_txt=True,
                )
                flip()

                while True:
                    q = pump(True)
                    _ = ui_request(queue=q)
                    if key_pressed(SPACE, queue=q):
                        break

                clear()

    # Called once at experiment end; almost never needed, like here
    def clean_up(self):
        fill()
        message(
            text=f"Experiment complete!\nTotal earnings: {self.total_earnings} points",
            location=P.screen_c,
            blit_txt=True
        )
        flip()

        while True:
            q = pump(True)
            _ = ui_request(queue=q)
            if key_pressed(SPACE):
                break

    # TODO: this could/should have been a dict
    def get_payout(self, clicked_on=None):
        if clicked_on is None:
            return TIMEOUT_PAYOUT

        elif clicked_on == REWARD:
            return self.reward_amount

        elif clicked_on == PENALTY:
            return self.penalty_amount

        elif clicked_on == OVERLAP:
            return self.overlap_amount

        elif clicked_on == OUTSIDE:
            return 0

        else:
            return MISS_PAYOUT

    # Logic for deciding "which" surface they touched
    # Also returns touch coordinates
    def listen_for_click(self):
        clicks = get_clicks()
        clicked = None

        if len(clicks):
            clicked_reward = self.bs.within_boundary(REWARD, p=clicks[0])
            clicked_penalty = self.bs.within_boundary(PENALTY, p=clicks[0])
            clicked_rect = self.bs.within_boundary(RECT, p=clicks[0])

            if clicked_rect:
                if clicked_reward and not clicked_penalty:
                    clicked = REWARD

                elif clicked_penalty and not clicked_reward:
                    clicked = PENALTY

                elif clicked_reward and clicked_penalty:
                    clicked = OVERLAP

                else:
                    clicked = RECT

            else:
                clicked = OUTSIDE
        else:
            clicks = [[-1, -1]]

        return clicks[0], clicked

    # Does what it says
    def draw_display(
        self,
        fix: bool = False,
        rect: bool = False,
        circles: bool = False,
            show_values: bool = False,
            also=None,
    ):

        fill()

        if fix:
            blit(
                self.stimuli[START],
                location=self.bs.boundaries[START].center,
                registration=5,
            )

            blit(
                self.stimuli[FIX],
                location=self.bs.boundaries[RECT].center,
                registration=5,
            )

        if rect:
            blit(
                self.stimuli[RECT],
                location=self.bs.boundaries[RECT].center,
                registration=5,
            )

        if circles:
            blit(
                self.stimuli[PENALTY],
                location=self.positions[PENALTY],
                registration=5,
            )
            blit(
                self.stimuli[REWARD],
                location=self.positions[REWARD],
                registration=5,
            )

        # Display reward and penalty values during preview
        if circles and show_values and not P.practicing:
            # Shift labels away from the overlapping region
            label_offset = self.target_circle_d * 0.18

            reward_x, reward_y = self.positions[REWARD]
            penalty_x, penalty_y = self.positions[PENALTY]

            if reward_x > penalty_x:
                reward_x += label_offset
                penalty_x -= label_offset
            else:
                reward_x -= label_offset
                penalty_x += label_offset

            reward_text = f"+{self.reward_amount}"
            penalty_text = f"{self.penalty_amount}"

            reward_label = message(
                reward_text,
                color=GREEN,
                blit_txt=False,
            )
            penalty_label = message(
                penalty_text,
                color=RED,
                blit_txt=False,
            )

            blit(
                reward_label,
                location=(reward_x, reward_y),
                registration=5,
            )
            blit(
                penalty_label,
                location=(penalty_x, penalty_y),
                registration=5,
            )

        if also:
            blit(also[0], location=also[1], registration=5)

        flip()

    # Randomly determine circle placements within rectangle
    def get_circle_placements(self):
        rad_px = self.target_circle_d / 2
        circle_offset = 0.5 * rad_px
        padd = self.thick * 2

        rect_p1 = [int(xy) for xy in self.bs.boundaries[RECT].p1]
        rect_p2 = [int(xy) for xy in self.bs.boundaries[RECT].p2]

        origin_x = randrange(
            start=int(rect_p1[0] + (1.5 * rad_px) + padd),
            stop=int(rect_p2[0] - (1.5 * rad_px) - padd),
        )
        origin_y = randrange(
            start=int(rect_p1[1] + rad_px + padd),
            stop=int(rect_p2[1] - rad_px - padd),
        )

        if self.reward_side == 'right':  # type: ignore[attr-defined]
            placements = {
                PENALTY: (origin_x - circle_offset, origin_y),
                REWARD: (origin_x + circle_offset, origin_y),
            }
        else:
            placements = {
                REWARD: (origin_x - circle_offset, origin_y),
                PENALTY: (origin_x + circle_offset, origin_y),
            }

        return placements
