#!/usr/bin/env python

import rospy
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Int32
from styx_msgs.msg import Lane, Waypoint
from scipy.spatial import KDTree

import math
import numpy as np

'''
This node will publish waypoints from the car's current position to some `x` distance ahead.
As mentioned in the doc, you should ideally first implement a version which does not care
about traffic lights or obstacles.
Once you have created dbw_node, you will update this node to use the status of traffic lights too.
Please note that our simulator also provides the exact location of traffic lights and their
current status in `/vehicle/traffic_lights` message. You can use this message to build this node
as well as to verify your TL classifier.
TODO (for Yousuf and Aaron): Stopline location for each traffic light.
'''

LOOKAHEAD_WPS = 45  # Number of waypoints we will publish. You can change this number
MAX_DECEL = 1.0
MPS2MPH = 2.236936
SAFETY_FACTOR = 0.90

class WaypointUpdater(object):
    def __init__(self):
        rospy.init_node('waypoint_updater')

        rospy.Subscriber('/current_pose', PoseStamped, self.pose_cb)
        rospy.Subscriber('/base_waypoints', Lane, self.waypoints_cb)
        rospy.Subscriber('/traffic_waypoint', Int32, self.traffic_cb)
        # TODO: Add a subscriber for /traffic_waypoint and /obstacle_waypoint below

        self.final_waypoints_pub = rospy.Publisher(
            'final_waypoints', Lane, queue_size=1)

        # TODO: Add other member variables you need below
        self.pose = None
        self.base_waypoints = None
        self.waypoints_2d = None
        self.waypoint_tree = None
        self.stopline_wp_idx = -1

        self.loop()

    def loop(self):
        rate = rospy.Rate(10)  # reduced from 50Hz to 10Hz
        while not rospy.is_shutdown():
            if self.pose and self.base_waypoints:
                # Get closest waypoint
                closest_waypoint_idx = self.get_closest_waypoint_idx()
                self.publish_waypoints(closest_waypoint_idx)
            rate.sleep()

    def get_closest_waypoint_idx(self):
        # Get the coordinates of our car
        x = self.pose.pose.position.x
        y = self.pose.pose.position.y
        # Get the index of the closest point
        closest_idx = self.waypoint_tree.query([x, y], 1)[1]

        # Check if closest is ahead or behind vehicle
        closest_coord = self.waypoints_2d[closest_idx]
        prev_coord = self.waypoints_2d[closest_idx - 1]

        # Equation for hyperplane through closest_coords
        cl_vect = np.array(closest_coord)
        prev_vect = np.array(prev_coord)
        pos_vect = np.array([x, y])

        val = np.dot(cl_vect - prev_vect, pos_vect - cl_vect)
        if val > 0:  # Our car is in front of the closest waypoint
            closest_idx = (closest_idx + 1) % len(self.waypoints_2d)

        return closest_idx

    def publish_waypoints(self, closest_idx):
        lane = Lane()  # Create a new Lane object
        lane.header = self.base_waypoints.header

        # Consider deceleration conditions
        if self.stopline_wp_idx == -1 or (self.stopline_wp_idx >= closest_idx + LOOKAHEAD_WPS):
            lane.waypoints = self.base_waypoints.waypoints[closest_idx:closest_idx + LOOKAHEAD_WPS]
        else:
            lane.waypoints = self.decelerate_waypoints(
                lane.waypoints, closest_idx)

        self.final_waypoints_pub.publish(lane)

    def pose_cb(self, msg):
        self.pose = msg

    def waypoints_cb(self, waypoints):
        # TODO: Implement
        # Get the basic waypoints from waypoint loader.This action only need to be done once
        self.base_waypoints = waypoints

        # Got 2d waypoints from 3d waypoints
        if not self.waypoints_2d:
            self.waypoints_2d = [[waypoint.pose.pose.position.x,
                                  waypoint.pose.pose.position.y] for waypoint in waypoints.waypoints]
            self.waypoint_tree = KDTree(self.waypoints_2d)

    def traffic_cb(self, msg):
        # TODO: Callback for /traffic_waypoint message. Implement
        self.stopline_wp_idx = msg.data

    def obstacle_cb(self, msg):
        # TODO: Callback for /obstacle_waypoint message. We will implement it later
        pass

    def get_waypoint_velocity(self, waypoint):
        return waypoint.twist.twist.linear.x

    def set_waypoint_velocity(self, waypoints, waypoint, velocity):
        waypoints[waypoint].twist.twist.linear.x = velocity+20

    def distance(self, waypoints, wp1, wp2):
        dist = 0

        def dl(a, b): return math.sqrt(
            (a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2)
        for i in range(wp1, wp2+1):
            dist += dl(waypoints[wp1].pose.pose.position,
                       waypoints[i].pose.pose.position)
            wp1 = i
        return dist

    def decelerate_waypoints(self, waypoints, closest_idx):
        result = []
        for i, wp in enumerate(waypoints):
            new_point = Waypoint()
            new_point.pose = wp.pose

            # Two waypints back from line so the front of
            stop_idx = max(self.stopline_wp_idx - closest_idx - 2, 0)
            # the car stops at the line
            dist = self.distance(waypoints, i, stop_idx)
            vel = math.sqrt(2 * MAX_DECEL * SAFETY_FACTOR * dist)
            if vel < 1.0:
                vel = 0.0

            new_point.twist.twist.linear.x = min(vel, wp.twist.twist.linear.x)
            result.append(new_point)

        return result


if __name__ == '__main__':
    try:
        WaypointUpdater()
    except rospy.ROSInterruptException:
        rospy.logerr('Could not start waypoint updater node.')