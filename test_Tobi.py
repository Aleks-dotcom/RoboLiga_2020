# Ce zelite na svojem racunalniku namestiti ev3dev knjiznico za Python:
# pip install python-ev3dev
from ev3dev.ev3 import TouchSensor, Button, LargeMotor, Sound
# Na EV3 robotu je potrebno namestiti paketa ujson in pycurl:
# sudo apt-get update
# sudo apt-get install python3-pycurl -
# sudo apt-get install python3-ujson
import pycurl
import ujson
import sys
import math
from io import BytesIO
from time import time, sleep
from enum import Enum
from collections import deque
btn = Button()

def wait_for_button(btn_name: str = 'down'):
    """
    Čakaj v zanki dokler ni gumb z imenom `btn_name` pritisnjen in nato sproščen.
    """
    while not getattr(btn, btn_name):
        pass
    flag = False
    while getattr(btn, btn_name):
        if not flag:
            flag = True


def init_large_motor(port: str) -> LargeMotor:
    """
    Preveri, ali je motor priklopljen na izhod `port`.
    Vrne objekt za motor (LargeMotor).
    """
    motor = LargeMotor(port)
    while not motor.connected:
        print('\nPriklopi motor na izhod ' + port +
              ' in pritisni + spusti gumb DOL.')
        wait_for_button('down')
        motor = LargeMotor(port)
    return motor


speed_right = 1000
speed_left = 1000

MOTOR_LEFT_PORT = 'outA'
MOTOR_RIGHT_PORT = 'outD'

motor_left = init_large_motor(MOTOR_LEFT_PORT)
motor_right = init_large_motor(MOTOR_RIGHT_PORT)

motor_right.run_forever(speed_sp=speed_right)
motor_left.run_forever(speed_sp=speed_left)