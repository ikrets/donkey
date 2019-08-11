#!/usr/bin/env python

# This node is a brigde between ROS and a Python 3 
# script that is inferencing on the Edge TPU.

# Edge TPU Python API is Python 3 only and ROS is
# Python 2 only.

import cv2

import rospy
from PIL import Image
import numpy as np
from io import BytesIO
from sensor_msgs.msg import CompressedImage
from donkey_actuator.msg import DonkeyDrive
from potential_field_steering import compute_path_on_fly, compute_polynom
import zmq

import sys
# TODO fast hacked for now
sys.path.append('/home/ubuntu/rosdonkey/src/dataset_utils')
from transform import make_undistort_birdeye

if __name__ == "__main__":
    undistort_birdeyeview = make_undistort_birdeye(
        input_shape=(320, 240),
        target_shape=(32, 48))

    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect('tcp://127.0.0.1:19090')

    rospy.init_node("lane_inference_bridge")
    rospy.get_param('port', 19090)

    decoded_img = np.empty((240, 320, 3), dtype=np.uint8)
    transformed_img = np.empty((32, 48, 3), dtype=np.uint8)
    def callback(img):
        decoded_img = cv2.imdecode(np.fromstring(img.data, np.uint8), 1)
        # The camera has a weird white line on the right edge.
        decoded_img[:, -2:, :] = 0
        undistort_birdeyeview(decoded_img, dst=transformed_img)

	socket.send(transformed_img.tobytes())
	img_bytes = socket.recv()

        img = np.frombuffer(img_bytes, dtype=np.bool).reshape((32, 48))

        path = compute_path_on_fly(img)
        polynom = compute_polynom(path)
        angle = polynom[1]

        drive = DonkeyDrive()
        drive.source = 'simple_steering'
        drive.use_constant_throttle = True
        drive.steering = np.clip(angle / (np.pi / 4), -1, 1)
        drive_publisher.publish(drive)

        vis = path[:, :, np.newaxis] * np.array([0, 0, 255], dtype=np.uint8)[np.newaxis, np.newaxis, :]
        vis += img[:, :, np.newaxis] * np.array([0, 255, 0], dtype=np.uint8)[np.newaxis, np.newaxis, :]

        poly_x = np.arange(32)
        poly_y = np.polyval(polynom, poly_x).astype(np.uint8)
        inside = (poly_y >= 0) & (poly_y < 48)

        vis[poly_x[inside], poly_y[inside], :] = np.array([255, 0, 0], dtype=np.uint8)

        with BytesIO() as fp:
            Image.fromarray(vis).save(fp, format='PNG')

            img_msg = CompressedImage()
            img_msg.format = 'png'
            img_msg.data = fp.getvalue()
            publisher.publish(img_msg)

    subscriber = rospy.Subscriber("/raspicam_node/image/compressed", 
	CompressedImage, callback, queue_size=1)
    publisher = rospy.Publisher('/lane_segmentation/image/compressed', CompressedImage)
    drive_publisher = rospy.Publisher('/donkey_drive', DonkeyDrive)

    rospy.spin()
