import RPi.GPIO as GPIO
import queue
import threading
import time

limit_switch_top_gpio = 8
limit_switch_bottom_gpio = 10
motor_direction_gpio = 24
motor_pulse_gpio = 23

class Switches(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.messageQueue = queue.Queue()
        self.start()

class Motor(threading.Thread):
    def __init__(self, period):
        threading.Thread.__init__(self)
        GPIO.setup(motor_direction_gpio, GPIO.OUT)
        GPIO.setup(motor_pulse_gpio, GPIO.OUT)
        self.isOn = False
        self.period = period
        self.start()

    def on(self):
        self.isOn = True

    def off(self):
        self.isOn = False

    def run(self):
        while self.isOn:
            GPIO.output(motor_pulse_gpio, 0)
            time.sleep(self.period)
            GPIO.output(motor_pulse_gpio, 1)
            time.sleep(self.period)