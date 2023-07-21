"""
create reverse ssh tunnel
create http interface
"""

import queue
import threading
import ssl
import smtplib
import time
import RPi.GPIO as GPIO
#from email_password import email_password
#from email.message import EmailMessage

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

limit_switch_top_gpio = 8
limit_switch_bottom_gpio = 10
limit_switch_polling_delay_interval = 0.02 
motor_direction_gpio = 24
motor_pulse_gpio = 23

motor_slow_speed = 500
motor_fast_speed = 5000

motor_counter_value_max_safety = 10000000

class Commands:
    LIMIT_SWITCH_TOP = "limit_switch_top_gpio"
    LIMIT_SWITCH_BOTTOM = "limit_switch_bottom_gpio"
    MOTOR_DESCEND_QUICKLY = "descend_quickly"
    MOTOR_ASCEND_QUICKLY = "ascend_quickly"
    MOTOR_ASCEND_SLOWLY = "ascend_slowly"
    MOTOR_STOP = "motor_stop"
    MOTOR_COUNTER_RESET = "motor_counter_reset"
    MOTOR_COUNTER_VALUE = "motor_counter_value"
    MOTOR_DIRECTION_DOWN = 0
    MOTOR_DIRECTION_UP = 1
    SHOOTING_EVENT = "shooting_event"
    CALIBRATE = "calibrate"
    PERFORM = "perform"

class Switch_Poller(threading.Thread):
    def __init__(
            self,
            limit_switch_top_gpio,
            limit_switch_bottom_gpio,
            event_callback
        ):
        threading.Thread.__init__(self)
        self.limit_switch_top_gpio = limit_switch_top_gpio
        self.limit_switch_bottom_gpio = limit_switch_bottom_gpio
        self.event_callback = event_callback
        GPIO.setup(limit_switch_top_gpio, GPIO.IN, GPIO.PUD_DOWN)
        GPIO.setup(limit_switch_bottom_gpio, GPIO.IN, GPIO.PUD_DOWN)
        self.start()

    def run(self):
        limit_switch_top_last_value = GPIO.input(limit_switch_top_gpio)
        limit_switch_bottom_last_value = GPIO.input(limit_switch_bottom_gpio)
        self.event_callback(Commands.LIMIT_SWITCH_TOP, limit_switch_top_last_value)
        self.event_callback(Commands.LIMIT_SWITCH_BOTTOM, limit_switch_bottom_last_value)
        while True:
            limit_switch_top_value = GPIO.input(limit_switch_top_gpio)
            limit_switch_bottom_value = GPIO.input(limit_switch_bottom_gpio)
            if limit_switch_top_value != limit_switch_top_last_value:
                self.event_callback(Commands.LIMIT_SWITCH_TOP, limit_switch_top_value)
                limit_switch_top_last_value = limit_switch_top_value
            if limit_switch_bottom_value != limit_switch_bottom_last_value:
                self.event_callback(Commands.LIMIT_SWITCH_BOTTOM, limit_switch_bottom_value)
                limit_switch_bottom_last_value = limit_switch_bottom_value
            time.sleep(limit_switch_polling_delay_interval)

class Query_Shooting_Events(threading.Thread):
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
        GPIO.setup(motor_direction_gpio, GPIO.OUT)
        GPIO.setup(motor_pulse_gpio, GPIO.OUT)
        self.direction = 0 # 0==up?
        self.speed = 0
        self.event_callback = event_callback
        self.message_queue = queue.Queue()
        self.pulse_counter = 0
        self.start()

    def message_receiver(self,command_name):
        self.message_queue.put(command_name)

    def run(self):
        while True:
            try:
                command_name = self.message_queue.get(False)
                match command_name:
                    case Commands.MOTOR_DESCEND_QUICKLY:
                        self.direction = Commands.MOTOR_DIRECTION_DOWN
                        self.speed = motor_fast_speed
                    case Commands.MOTOR_ASCEND_QUICKLY:
                        self.direction = Commands.MOTOR_DIRECTION_UP 
                        self.speed = motor_fast_speed
                    case Commands.MOTOR_ASCEND_SLOWLY:
                        self.direction = Commands.MOTOR_DIRECTION_UP 
                        self.speed = motor_slow_speed
                    case Commands.MOTOR_STOP:
                        self.speed = 0.0
                    case Commands.MOTOR_COUNTER_RESET:
                        self.pulse_counter = 0
            except queue.Empty:
                pass
                
            GPIO.output(self.motor_direction_gpio, self.direction)
            if self.speed == 0.0:
                time.sleep(1)
            if self.speed == motor_slow_speed:
                for pulse in range(motor_slow_speed * 2):
                    GPIO.output(self.motor_pulse_gpio, 0)
                    time.sleep(1.0/self.speed)
                    GPIO.output(self.motor_pulse_gpio, 1)
                    time.sleep(1.0/self.speed)
            if self.speed == motor_fast_speed:
                for pulse in range(motor_fast_speed * 2):
                    GPIO.output(self.motor_pulse_gpio, 0)
                    time.sleep(1.0/self.speed)
                    GPIO.output(self.motor_pulse_gpio, 1)
                    time.sleep(1.0/self.speed)
            self.pulse_counter += self.speed if self.direction == Commands.MOTOR_DIRECTION_DOWN  else 0-self.speed
            self.event_callback(Commands.MOTOR_COUNTER_VALUE, self.pulse_counter)

class Notifications(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.message_queue = queue.Queue()
        self.email_sender = "autoprayer23@gmail.com"
        self.email_receiver = "arigebhardt82@gmail.com"
        self.subject = "Automating Their Prayers Error Report"
        self.context = ssl.create_default_context()
        self.start()

    def send(self, body):
        em = EmailMessage()
        em["From"] = self.email_sender
        em["To"] = self.email_receiver
        em["Subject"] = self.subject
        em.set_content(body)
        self.message_queue.put(em)

    def run(self):
        while True:
            em = self.message_queue.get(True, None)
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=self.context) as smtp:
                smtp.login(self.email_sender, email_password)
                smtp.sendmail(self.email_sender, self.email_receiver, em.as_string())

class Main(threading.Thread):
    def __init__(
            self
        ):
        self.message_queue = queue.Queue()
        threading.Thread.__init__(self)
        self.mode = Commands.CALIBRATE # or PERFORM
        self.motor_counter_value = 0
        self.limit_switch_bottom_reached = False
        self.limit_switch_top_reached = False
        self.motor_counter_value_max_measured = -1
        self.switch_poller = Switch_Poller(
            limit_switch_top_gpio, 
            limit_switch_bottom_gpio, 
            self.message_receiver
        )
        self.query_shooting_events = Query_Shooting_Events(
            self.message_receiver
        )
        self.motor_control = Motor_Control(
            motor_direction_gpio, 
            motor_pulse_gpio,
            self.message_receiver
        )
        self.start()

    def message_receiver(self, command_name, value):
        print(command_name, value)
        self.message_queue.put((command_name, value))

    def run(self):
        while True:
            command_name, value = self.message_queue.get(True)
            """
            The calibration process:
                0. if top limit switch is closed and bottom switch has not been reached, descend
                1. if bottom limit switch is closed 
                2. transport descends to the bottom limit switch
                3. motor stops
                4. motor counter is reset
                5. transport ascends 
            """
            if self.mode == Commands.CALIBRATE:
                match command_name:
                    case Commands.LIMIT_SWITCH_TOP:
                        if value == 1: # top reached
                            if self.limit_switch_bottom_reached == False and self.limit_switch_top_reached == False:
                                # this state implies that transport was at the top when calibration began
                                self.motor_control.message_receiver(Commands.MOTOR_DESCEND_QUICKLY)
                            if self.limit_switch_bottom_reached == True and self.limit_switch_top_reached == False:
                                # this state implies that the transport has traversed from the bottom to top
                                self.motor_control.message_receiver(Commands.MOTOR_STOP)
                                self.limit_switch_top_reached = True
                                self.motor_counter_value_max_measured = self.motor_counter_value

                            if self.limit_switch_bottom_reached == False and self.limit_switch_top_reached == True:
                                # this state implies 
                                # is there anything to do?
                                pass
                            if self.limit_switch_bottom_reached == True and self.limit_switch_top_reached == True:
                                # this state implies 
                                # is there anything to do?
                                pass
                        else: # top limit switch opens
                            # is there anything to do?
                            pass

                    case Commands.LIMIT_SWITCH_BOTTOM:
                        if value == 1: # bottom reached
                            if self.limit_switch_bottom_reached == False and self.limit_switch_top_reached == False:
                                # this state implies
                                pass
                            if self.limit_switch_bottom_reached == True and self.limit_switch_top_reached == False:
                                # this state implies
                                pass
                            if self.limit_switch_bottom_reached == False and self.limit_switch_top_reached == True:
                                # this state implies 
                                pass
                            if self.limit_switch_bottom_reached == True and self.limit_switch_top_reached == True:
                                # this state implies 
                                pass
                        else: # top limit switch opens
                            # is there anything to do?
                            pass

                    case Commands.SHOOTING_EVENT:
                        pass
                    case Commands.MOTOR_COUNTER_VALUE:
                        pass
            if self.mode == Commands.PERFORM:
                match command_name:
                    case Commands.LIMIT_SWITCH_TOP:
                        self.motor_control.message_receiver(Commands.MOTOR_STOP)
                    case Commands.LIMIT_SWITCH_BOTTOM:
                        self.motor_control.message_receiver(Commands.MOTOR_ASCEND_SLOWLY)
                    case Commands.SHOOTING_EVENT:
                        self.motor_control.message_receiver(Commands.MOTOR_DESCEND_QUICKLY)
                    case Commands.MOTOR_COUNTER_VALUE:
                        pass

main = Main()


# tests
def issue_motor_command(command):
    main.motor_control.message_receiver(command)

#issue_motor_command(Commands.MOTOR_ASCEND_SLOWLY)
