import RPi.GPIO as GPIO
import queue
import threading
import time

limit_switch_top_gpio = 8
limit_switch_bottom_gpio = 25
motor_direction_gpio = 24
motor_pulse_gpio = 23

class Switches(threading.Thread):
    def __init__(self, period):
        threading.Thread.__init__(self)
        GPIO.setup(limit_switch_top_gpio, GPIO.IN, GPIO.PUD_DOWN)
        GPIO.setup(limit_switch_bottom_gpio, GPIO.IN, GPIO.PUD_DOWN)
        self.period = period
        self.queue = queue.Queue()
        self.start()
    
    def readTop(self, boolean=True):
        self.queue.put((True, boolean))

    def readBottom(self, boolean=True):
        self.queue.put((False, boolean))
    
    def run(self):
        top, bottom = False, False
        topLastState, bottomLastState = 0, 0
        while True:
            try:
                switch, boolean = self.queue.get(False)
                if switch:
                    top = boolean
                else:
                    bottom = boolean
            except queue.Empty:
                pass
            if top and topLastState != GPIO.input(limit_switch_top_gpio):
                topLastState = GPIO.input(limit_switch_top_gpio)
                print("Top State: " + str(topLastState))
            if bottom and bottomLastState != GPIO.input(limit_switch_bottom_gpio):
                bottomLastState = GPIO.input(limit_switch_bottom_gpio)
                print("Bottom State: " + str(bottomLastState))
            time.sleep(self.period)

class Motor(threading.Thread):
    def __init__(self, period):
        threading.Thread.__init__(self)
        GPIO.setup(motor_direction_gpio, GPIO.OUT)
        GPIO.setup(motor_pulse_gpio, GPIO.OUT)
        self.period = period
        self.queue = queue.Queue()
        self.start()

    def on(self):
        self.queue.put(True)

    def off(self):
        self.queue.put(False)

    def run(self):
        isOn = False
        while True:
            try:
                isOn = self.queue.get(False)
            except queue.Empty:
                pass
            if isOn:
                GPIO.output(motor_pulse_gpio, 0)
                time.sleep(self.period)
                GPIO.output(motor_pulse_gpio, 1)
                time.sleep(self.period)
            else:
                time.sleep(self.period)