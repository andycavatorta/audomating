import queue
import threading
import time
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

names.LIMIT_SWITCH_TOP_gpio = 8
names.LIMIT_SWITCH_BOTTOM_gpio = 10
limit_switch_polling_delay_interval = 0.02 
motor_direction_gpio = 4
motor_pulse_gpio = 4

names.MOTOR_COUNTER_VALUE_max_safety = 1000000

class names:
	LIMIT_SWITCH_TOP = "LIMIT_SWITCH_TOP_gpio"
	LIMIT_SWITCH_BOTTOM = "LIMIT_SWITCH_BOTTOM_gpio"
	MOTOR_DECEND_QUICKLY = "decend_quickly"
	MOTOR_ASCEND_QUICKLY = "ascend_quickly"
	MOTOR_ASCEND_SLOWLY = "ascend_slowly"
	MOTOR_STOP = "MOTOR_STOP"
	MOTOR_COUNTER_RESET = "MOTOR_COUNTER_RESET"
	MOTOR_COUNTER_VALUE = "MOTOR_COUNTER_VALUE"
	MOTOR_DIRECTION_DOWN = 0
	MOTOR_DIRECTION_UP = 1
	SHOOTING_EVENT = "SHOOTING_EVENT"
	CALIBRATE = "CALIBRATE"
	PERFORM = "PERFORM"

class Switch_Poller(threading.Thread):
    def __init__(
            self,
            names.LIMIT_SWITCH_TOP_gpio,
            names.LIMIT_SWITCH_BOTTOM_gpio,
            event_callback
        ):
        threading.Thread.__init__(self)
        self.names.LIMIT_SWITCH_TOP_gpio = names.LIMIT_SWITCH_TOP_gpio
        self.names.LIMIT_SWITCH_BOTTOM_gpio = names.LIMIT_SWITCH_BOTTOM_gpio
        self.event_callback = event_callback
        GPIO.setup(names.LIMIT_SWITCH_TOP_gpio, GPIO.IN, GPIO.PUD_DOWN)
        GPIO.setup(names.LIMIT_SWITCH_BOTTOM_gpio, GPIO.IN, GPIO.PUD_DOWN)
        self.start()

    def run(self):
        names.LIMIT_SWITCH_TOP_last_value = GPIO.input(names.LIMIT_SWITCH_TOP_gpio)
        names.LIMIT_SWITCH_BOTTOM_last_value = GPIO.input(names.LIMIT_SWITCH_BOTTOM_gpio)
        self.event_callback(names.LIMIT_SWITCH_TOP, names.LIMIT_SWITCH_TOP_last_value)
        self.event_callback(names.LIMIT_SWITCH_BOTTOM, names.LIMIT_SWITCH_BOTTOM_last_value)
        while True:
            names.LIMIT_SWITCH_TOP_value = GPIO.input(names.LIMIT_SWITCH_TOP_gpio)
            names.LIMIT_SWITCH_BOTTOM_value = GPIO.input(names.LIMIT_SWITCH_BOTTOM_gpio)
            if names.LIMIT_SWITCH_TOP_value != names.LIMIT_SWITCH_TOP_last_value:
                self.event_callback(names.LIMIT_SWITCH_TOP, names.LIMIT_SWITCH_TOP_value)
                names.LIMIT_SWITCH_TOP_last_value = names.LIMIT_SWITCH_TOP_value
            if names.LIMIT_SWITCH_BOTTOM_value != names.LIMIT_SWITCH_BOTTOM_last_value:
                self.event_callback(names.LIMIT_SWITCH_BOTTOM, names.LIMIT_SWITCH_BOTTOM_value)
                names.LIMIT_SWITCH_BOTTOM_last_value = names.LIMIT_SWITCH_BOTTOM_value
            time.sleep(limit_switch_polling_delay_interval)

class Query_names.SHOOTING_EVENTs(threading.Thread):
    def __init__(
            self,
            event_callback
        ):
        threading.Thread.__init__(self)
        self.event_callback = event_callback
        self.start()

    def run(self):
        time.sleep(3600)


class Motor_Control(threading.Thread):
    def __init__(
            self,
            motor_direction_gpio, 
            motor_pulse_gpio,
            event_callback
        ):
        threading.Thread.__init__(self)
        self.motor_direction_gpio = motor_direction_gpio 
        self.motor_pulse_gpio = motor_pulse_gpio
        self.direction = 0 # 0==up?
        self.speed = 0
        self.event_callback = event_callback
        self.message_queue = queue.Queue()
        self.pulse_counter = 0
        self.start()

    def message_receiver(self):
        self.message_queue.put(command_name)

    def run(self):
        while True:
            try:
                command_name = self.message_queue.get(False)
                match command_name:
                    case names.MOTOR_DECEND_QUICKLY:
                        self.direction = names.MOTOR_DIRECTION_DOWN
                        self.speed = 200.0
                    case names.MOTOR_ASCEND_QUICKLY:
                        self.direction = names.MOTOR_DIRECTION_UP 
                        self.speed = 200.0
                    case names.MOTOR_ASCEND_SLOWLY:
                        self.direction = names.MOTOR_DIRECTION_UP 
                        self.speed = 20.0
                    case names.MOTOR_STOP:
                        self.speed = 0.0
                    case names.MOTOR_COUNTER_RESET:
                        self.pulse_counter = 0
            except queue.empty:
                pass
                
            GPIO.output(self.motor_direction_gpio, self.direction)
            if self.speed == 0.0:
                time.sleep(1)
            if self.speed == 20.0:
                for pulse in range(40):
                    GPIO.output(self.motor_pulse_gpio, 0)
                    time.sleep(1.0/self.speed)
                    GPIO.output(self.motor_pulse_gpio, 1)
                    time.sleep(1.0/self.speed)
            if self.speed == 200.0:
                for pulse in range(400):
                    GPIO.output(self.motor_pulse_gpio, 0)
                    time.sleep(1.0/self.speed)
                    GPIO.output(self.motor_pulse_gpio, 1)
                    time.sleep(1.0/self.speed)
            self.pulse_counter += self.speed if self.direction == names.MOTOR_DIRECTION_DOWN  else 0-self.speed
            self.event_callback(names.MOTOR_COUNTER_VALUE, self.pulse_counter)


class Main(threading.Thread):
    def __init__(
            self,
            event_callback
        ):
        self.message_queue = queue.Queue()
        threading.Thread.__init__(self)
        self.mode = names.CALIBRATE # or names.PERFORM
        self.names.MOTOR_COUNTER_VALUE = 0
        self.names.LIMIT_SWITCH_BOTTOM_reached = False
        self.names.LIMIT_SWITCH_TOP_reached = False
        self.names.MOTOR_COUNTER_VALUE_max_measured = -1
        self.switch_poller = Switch_Poller(
            names.LIMIT_SWITCH_TOP_gpio, 
            names.LIMIT_SWITCH_BOTTOM_gpio, 
            self.message_receiver
        )
        self.query_names.SHOOTING_EVENTs = Query_names.SHOOTING_EVENTs(
            self.message_receiver
        )
        self.motor_control = Motor_Control(
            motor_direction_gpio, 
            motor_pulse_gpio,
            self.message_receiver
        )
        self.start()

    def message_receiver(self, source_name, value):
        self.message_queue.put((source_name, value))

    def run(self):
        while True:
            source_name, value = self.message_queue.get(True)
            """
            The calibration process:
                0. if top limit switch is closed and bottom switch has not been reached, descend
                0. if bottom limit switch is closed 
                1. transport decends to the bottom limit switch
                2. motor stops
                3. motor counter is reset
                4. transport ascends 
                5. 
            """
            if self.mode == names.CALIBRATE:
                match command_name:
                    case names.LIMIT_SWITCH_TOP:
                        if value == 1: # top reached
                            if self.names.LIMIT_SWITCH_BOTTOM_reached == False and self.names.LIMIT_SWITCH_TOP_reached == False:
                                # this state implies that transport was at the top when calibration began
                                self.motor_control.message_receiver(names.MOTOR_DECEND_QUICKLY)
                            if self.names.LIMIT_SWITCH_BOTTOM_reached == True and self.names.LIMIT_SWITCH_TOP_reached == False:
                                # this state implies that the transport has traversed from the bottom to top
                                self.motor_control.message_receiver(names.MOTOR_STOP)
                                self.names.LIMIT_SWITCH_TOP_reached = True
                                self.names.MOTOR_COUNTER_VALUE_max_measured = self.names.MOTOR_COUNTER_VALUE

                            if self.names.LIMIT_SWITCH_BOTTOM_reached == False and self.names.LIMIT_SWITCH_TOP_reached == True:
                                # this state implies 
                                # is there anything to do?
                                pass
                            if self.names.LIMIT_SWITCH_BOTTOM_reached == True and self.names.LIMIT_SWITCH_TOP_reached == True:
                                # this state implies 
                                # is there anything to do?
                                pass
                        else: # top limit switch opens
                            # is there anything to do?
                            pass

                    case names.LIMIT_SWITCH_BOTTOM:
                        if value == 1: # bottom reached
                            if self.names.LIMIT_SWITCH_BOTTOM_reached == False and self.names.LIMIT_SWITCH_TOP_reached == False:
                                # this state implies
                                pass
                            if self.names.LIMIT_SWITCH_BOTTOM_reached == True and self.names.LIMIT_SWITCH_TOP_reached == False:
                                # this state implies
                                pass
                            if self.names.LIMIT_SWITCH_BOTTOM_reached == False and self.names.LIMIT_SWITCH_TOP_reached == True:
                                # this state implies 
                                pass
                            if self.names.LIMIT_SWITCH_BOTTOM_reached == True and self.names.LIMIT_SWITCH_TOP_reached == True:
                                # this state implies 
                                pass
                        else: # top limit switch opens
                            # is there anything to do?
                            pass




                    case names.SHOOTING_EVENT:
                        pass
                    case names.MOTOR_COUNTER_VALUE:
                        pass
            if self.mode == names.PERFORM:
                match command_name:
                    case names.LIMIT_SWITCH_TOP:
                        pass
                    case names.LIMIT_SWITCH_BOTTOM:
                        pass
                    case names.SHOOTING_EVENT:
                        pass
                    case names.MOTOR_COUNTER_VALUE:
                        pass

main = Main()
