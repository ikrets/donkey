#!/usr/bin/env python
"""
The PCA9685 class is taken from the Donkeycar repo.
https://github.com/autorope/donkeycar/
"""

import rospy
from pwm_joy_teleop.msg import DonkeyDrive

class PCA9685:
    """
    PWM motor controler using PCA9685 boards.
    This is used for most RC Cars
    """
    def __init__(self, channel, frequency=60):
        import Adafruit_PCA9685
        # Initialise the PCA9685 using the default address (0x40).
        self.pwm = Adafruit_PCA9685.PCA9685()
        self.pwm.set_pwm_freq(frequency)
        self.channel = channel

    def set_pulse(self, pulse):
        try:
            self.pwm.set_pwm(self.channel, 0, pulse)
        except OSError as err:
            print("Unexpected issue setting PWM (check wires to motor board): {0}".format(err))

    def run(self, pulse):
        self.set_pulse(pulse)


if __name__ == "__main__":
    rospy.init_node("actuator")

    start_positive_throttle = 381
    max_positive_throttle = 384

    start_negative_throttle = 345
    max_negative_throttle = 339

    zero_throttle = 360

    left_steering = 570
    zero_steering = 460
    right_steering = 370

    steering = PCA9685(0)
    throttle = PCA9685(1)
    throttle.set_pulse(zero_throttle)

    last_update_time = rospy.Time.now()

    def drive_callback(donkey_drive):
	global last_update_time

	if abs(donkey_drive.steering) > 1 or abs(donkey_drive.throttle) > 1:
	    rospy.logerr("Wrong actuation received! Steering: %f, throttle: %f",
		donkey_drive.steering, donkey_drive.throttle)
	    return

	if donkey_drive.header.stamp - rospy.Time.now() > rospy.Duration(0.5):
	    rospy.loginfo("Throwing out actuation: %f seconds old",
		(donkey_drive.header.stamp - rospy.Time.now()).to_sec())
	    return

	last_update_time = rospy.Time.now()
	    
	if donkey_drive.throttle > 0:
	    throttle_command = start_positive_throttle + (max_positive_throttle - start_positive_throttle) * donkey_drive.throttle
	elif donkey_drive.throttle < 0:
	    throttle_command = start_negative_throttle + (start_negative_throttle - max_negative_throttle) * donkey_drive.throttle
	else:
	    throttle_command = zero_throttle

	donkey_drive.steering *= -1

	if donkey_drive.steering > 0:
	    steering_command = zero_steering + (left_steering - zero_steering) * donkey_drive.steering
	elif donkey_drive.steering < 0:
	    steering_command = zero_steering + (right_steering - zero_steering) * abs(donkey_drive.steering)
	else:
	    steering_command = zero_steering

	if max_negative_throttle > throttle_command or throttle_command > max_positive_throttle:
	    rospy.logerr("Wrong throttle value: %f!", throttle_command)
	    return

	if right_steering > steering_command or steering_command > left_steering:
	    rospy.logerr("Wrong steering value: %f!", steering_command)

	rospy.loginfo("Steering: %f, throttle: %f", steering_command, throttle_command)
	steering.set_pulse(int(steering_command))
	throttle.set_pulse(int(throttle_command))

    def timer_event(event):
	global last_update_time

	time_without_control = rospy.Time.now() - last_update_time

	if time_without_control > rospy.Duration(1):
	    steering.set_pulse(int(zero_steering))
	    throttle.set_pulse(int(zero_throttle))
	    rospy.loginfo("No command for %f, stopping!", time_without_control.to_sec())
    
    subscriber = rospy.Subscriber("donkey_drive", DonkeyDrive, drive_callback)
    timer = rospy.Timer(rospy.Duration(0.5), timer_event)

    rospy.spin()
