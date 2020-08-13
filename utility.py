#!/usr/bin/env python3

# Če želite na svojem računalniku namestiti knjižnico python-ev3dev 
# in uprorabljati "code auto-completition":
# pip install python-ev3dev
from ev3dev.ev3 import TouchSensor, Button, LargeMotor, MediumMotor, Sound
# Na EV3 robotu je potrebno namestiti paketa ujson in pycurl:
# sudo apt-get update
# sudo apt-get install python3-pycurl
# sudo apt-get install python3-ujson
import pycurl
import sys
import math
from io import BytesIO
from time import time, sleep
from enum import Enum
from collections import deque

# Funkcije lepote

def drop(motor_left, motor_right, motor_medium):
    motor_medium.run_timed(time_sp=2000, speed_sp=-900)
    sleep(3)
    

def lift(motor_left, motor_right, motor_medium):
    motor_medium.run_timed(time_sp=2000, speed_sp=900)
    sleep(3)

def drive(motor_left, motor_right, motor_medium):
    motor_left.run_timed(time_sp=2000, speed_sp=450)
    motor_right.run_timed(time_sp=2000, speed_sp=450)
    sleep(2)

def reverse(motor_left, motor_right, motor_medium):
    motor_left.run_timed(time_sp=2000, speed_sp=-450)
    motor_right.run_timed(time_sp=2000, speed_sp=-450)
    sleep(2)



utilities = {
    "drive": drive,
    "reverse": reverse,
    "lift": lift,
    "drop": drop
}

print(len(sys.argv))
for x in sys.argv:
    print(x)

if len(sys.argv) == 0:
    print("No arguments passed: [ drive | reverse | drop | lift ]")
    sys.exit(1)

if len(sys.argv) > 1:
    print("Too many arguments: [ drive | reverse | drop | lift ]")
    sys.exit(1)

function = sys.argv[0]
if function not in utilities:
    print("Wrong argument: [ drive | reverse | drop | lift ]")
    sys.exit(1)


# Priklop motorjev na izhode.
MOTOR_LEFT_PORT = 'outD'
MOTOR_RIGHT_PORT = 'outA'
MOTOR_MEDIUM_PORT = 'outB'


def init_large_motor(port: str) -> LargeMotor:
    """
    Preveri, ali je motor priklopljen na izhod `port`.
    Vrne objekt za motor (LargeMotor).
    """
    motor = LargeMotor(port)
    while not motor.connected:
        print('\nPriklopi motor na izhod ' + port +
              ' in pritisni ter spusti gumb DOL.')
        wait_for_button('down')
        motor = LargeMotor(port)
    return motor


def init_medium_motor(port: str) -> MediumMotor:
    """
    Preveri, ali je motor priklopljen na izhod `port`.
    Vrne objekt za motor (MediumMotor).
    """
    motor = MediumMotor(port)
    while not motor.connected:
        print('\nPriklopi motor na izhod ' + port +
              ' in pritisni ter spusti gumb DOL.')
        wait_for_button('down')
        motor = MediumMotor(port)
    return motor


def init_sensor_touch() -> TouchSensor:
    """
    Preveri, ali je tipalo za dotik priklopljeno na katerikoli vhod. 
    Vrne objekt za tipalo.
    """
    sensor = TouchSensor()
    while not sensor.connected:
        print('\nPriklopi tipalo za dotik in pritisni ter spusti gumb DOL.')
        wait_for_button('down')
        sensor = TouchSensor()
    return sensor


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


def robot_die():
    """
    Končaj s programom na robotu. Ustavi motorje.
    """
    print('KONEC')
    motor_left.stop(stop_action='brake')
    motor_right.stop(stop_action='brake')

    Sound.play_song((
        ('D4', 'e'),
        ('C4', 'e'),
        ('A3', 'h')))

    sys.exit(0)




# -----------------------------------------------------------------------------
# NASTAVITVE TIPAL, MOTORJEV
# -----------------------------------------------------------------------------
# Nastavimo tipala in gumbe.
print('Priprava tipal ... ', end='', flush=True)
btn = Button()
#sensor_touch = init_sensor_touch()
#print('OK!')

# Nastavimo velika motorja. Priklopljena naj bosta na izhoda A in D.
print('Priprava motorjev ... ', end='')
motor_left = init_large_motor(MOTOR_LEFT_PORT)
motor_right = init_large_motor(MOTOR_RIGHT_PORT)
motor_medium = init_medium_motor(MOTOR_MEDIUM_PORT)


SONG_LYRICS = "Executing utility functions"
Sound.speak(SONG_LYRICS)

utilities[function](motor_left, motor_right, motor_medium)
sleep(3)
robot_die()