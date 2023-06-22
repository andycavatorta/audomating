
import queue
import threading
import time
import RPi.GPIO as GPIO


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

limit_switch_top_gpio = 8
limit_switch_bottom_gpio = 10
limit_switch_polling_delay_interval = 0.02 
motor_direction_gpio = 4
motor_pulse_gpio = 4

motor_counter_value_max_safety = 1000000

LIMIT_SWITCH_TOP = "limit_switch_top_gpio"
LIMIT_SWITCH_BOTTOM = "limit_switch_bottom_gpio"
MOTOR_DECEND_QUICKLY = "decend_quickly"
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
		self.event_callback(LIMIT_SWITCH_TOP, limit_switch_top_last_value)
		self.event_callback(LIMIT_SWITCH_BOTTOM, limit_switch_bottom_last_value)
    	while True:
			limit_switch_top_value = GPIO.input(limit_switch_top_gpio)
			limit_switch_bottom_value = GPIO.input(limit_switch_bottom_gpio)
			if limit_switch_top_value != limit_switch_top_last_value:
				self.event_callback(LIMIT_SWITCH_TOP, limit_switch_top_value)
				limit_switch_top_last_value = limit_switch_top_value
			if limit_switch_bottom_value != limit_switch_bottom_last_value:
				self.event_callback(LIMIT_SWITCH_BOTTOM, limit_switch_bottom_value)
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
				    case MOTOR_DECEND_QUICKLY:
						self.direction = MOTOR_DIRECTION_DOWN
						self.speed = 200.0
				    case MOTOR_ASCEND_QUICKLY:
						self.direction = MOTOR_DIRECTION_UP 
						self.speed = 200.0
				    case MOTOR_ASCEND_SLOWLY:
						self.direction = MOTOR_DIRECTION_UP 
						self.speed = 20.0
				    case MOTOR_STOP:
						self.speed = 0.0
					case MOTOR_COUNTER_RESET:
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
			self.pulse_counter += self.speed if self.direction == MOTOR_DIRECTION_DOWN  else 0-self.speed
			self.event_callback(MOTOR_COUNTER_VALUE, self.pulse_counter)


class Main(threading.Thread):
    def __init__(
            self,
			event_callback
        ):
        self.message_queue = queue.Queue()
        threading.Thread.__init__(self)
        self.mode = CALIBRATE # or PERFORM
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
			motor_pulse_gpio
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
            if self.mode == CALIBRATE:
	            match command_name:
				    case LIMIT_SWITCH_TOP:
				    	if value == 1: # top reached
				    		if self.limit_switch_bottom_reached == False and self.limit_switch_top_reached == False:
				    			# this state implies that transport was at the top when calibration began
				    			self.motor_control.message_receiver(MOTOR_DECEND_QUICKLY)
				    		if self.limit_switch_bottom_reached == True and self.limit_switch_top_reached == False:
				    			# this state implies that the transport has traversed from the bottom to top
				    			self.motor_control.message_receiver(MOTOR_STOP)
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

				    case LIMIT_SWITCH_BOTTOM:
				    	if value == 1: # bottom reached
				    		if self.limit_switch_bottom_reached == False and self.limit_switch_top_reached == False:
				    			# this state implies

				    		if self.limit_switch_bottom_reached == True and self.limit_switch_top_reached == False:
				    			# this state implies

				    		if self.limit_switch_bottom_reached == False and self.limit_switch_top_reached == True:
				    			# this state implies 
				    			pass
				    		if self.limit_switch_bottom_reached == True and self.limit_switch_top_reached == True:
				    			# this state implies 
				    			pass
				        else: # top limit switch opens
			        		# is there anything to do?
			        		pass




				    case SHOOTING_EVENT:
				        pass
				    case MOTOR_COUNTER_VALUE:
				        pass
            if self.mode == PERFORM:
	            match command_name:
				    case LIMIT_SWITCH_TOP:
				        pass
				    case LIMIT_SWITCH_BOTTOM:
				        pass
				    case SHOOTING_EVENT:
				        pass
				    case MOTOR_COUNTER_VALUE:
				        pass

main = Main()
