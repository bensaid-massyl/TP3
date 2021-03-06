#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Sample code to publish RPi's CPU temperature to a MQTT broker
#    --> publish RPI CPU's temperature sensor
#    <-- subscribe to RPI CPU's temperature sensor
#
# Thiebolt  aug.19  updated
# Francois  apr.16  initial release
#



# #############################################################################
#
# Import zone
#
import errno
import os
import signal
import syslog
import sys

import time

import threading
import json

import random

import logging

# MQTT related imports
import paho.mqtt.client as mqtt

'''
# To extend python librayrt search path
_path2add='./libutils'
if (os.path.exists(_path2add) and not os.path.abspath(_path2add) in sys.path):
    sys.path.append(os.path.abspath(_path2add))
# Raspberry Pi related imports
from rpi_utils import *
'''
from libutils.rpi_utils import getCPUtemperature,getmac



# #############################################################################
#
# Global Variables
#
# MQTT_SERVER="192.168.0.210"
MQTT_SERVER="192.168.0.210"
MQTT_PORT=1883
# Full MQTT_topic = MQTT_BASE + MQTT_TYPE
MQTT_BASE_TOPIC = "1R1/014"
MQTT_TYPE_TOPIC = "shutter"
MQTT_PUB = "/".join([MQTT_BASE_TOPIC, MQTT_TYPE_TOPIC])
MQTT_SUB = "/".join([MQTT_PUB, "command"])

# First subscription to same topic (for tests)
#MQTT_SUB = MQTT_PUB
# ... then subscribe to <topic>/command to receive orders

MQTT_QOS=0 # (default) no ACK from server
#MQTT_QOS=1 # server will ack every message

MQTT_USER="azerty"
MQTT_PASSWD="azerty"

# Measurement related
# seconds between each measure.
measure_interleave = 5

client      = None
timer       = None
log         = None
__shutdown  = False



# #############################################################################
#
# Functions
#


#
# Function ctrlc_handler
def ctrlc_handler(signum, frame):
    global __shutdown
    log.info("<CTRL + C> action detected ...");
    __shutdown = True
    # Stop monitoring
    stopMonitoring()


#
# Function stoping the monitoring
def stopMonitoring():
    global client
    global timer
    log.info("[Shutdown] stop timer and MQTT operations ...");
    timer.cancel()
    timer.join()
    del timer
    client.unsubscribe(MQTT_SUB)
    client.disconnect()
    client.loop_stop()
    del client

#
# threading.timer helper function
def do_every (interval, worker_func, iterations = 0):
    global timer
    # launch new timer
    if ( iterations != 1):
        timer = threading.Timer (
                        interval,
                        do_every, [interval, worker_func, 0 if iterations == 0 else iterations-1])
        timer.start();
    # launch worker function
    worker_func();


# --- MQTT related functions --------------------------------------------------
# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    log.info("Connected with result code : %d" % rc)

    if( rc == 0 ):
        log.info("subscribing to topic: %s" % MQTT_SUB)
        # Subscribe to topic
        print('CLIENT SUBCRIBED TO :'+MQTT_SUB)
        client.subscribe(MQTT_SUB);


# The callback for a received message from the server.
def on_message_old(client, userdata, msg):
    ''' process incoming message.
        WARNING: threaded environment! '''
    payload = json.loads(msg.payload.decode('utf-8'))
    print("Received message '" + json.dumps(payload) + "' on topic '" + msg.topic + "' with QoS " + str(msg.qos))

    # First test: subscribe to your own publish topic
    # ... then remove later
    print("Temperature is %s deg. %s" % (payload['value'],payload['value_units']))

    # TO BE CONTINUED
    print("TODO: process incoming message!")

def on_message(self, client, userdata, msg):
    ''' paho callback for message reception '''
    #log.debug("receiving a msg on topic '%s' ..." % str(msg.topic) )
    try:
        # loading and verifying payload
        payload = json.loads(msg)
        #validictory.validate(payload, self.COMMAND_SCHEMA)
    except Exception as ex:
        log.error("exception handling json payload from topic '%s': " % str(msg.topic) + str(ex))
        return
    # is it a message for us ??
    log.debug("msg received on topic '%s' features destID='%s' != self._unitID='%s'" % (str(msg.topic),payload['dest'],self.unitID))
    self.handle_message( msg.topic, payload )

def handle_message(topic, payload):
    print('TOPIC:'+topic+',PAYLOAD='+payload)




# The callback to tell that the message has been sent (QoS0) or has gone
# through all of the handshake (QoS1 and 2)
def on_publish(client, userdata, mid):
    print("mid: " + str(mid)+ " published!")

def on_subscribe(mosq, obj, mid, granted_qos):
    print("Subscribed: " + str(mid) + " " + str(granted_qos))

def on_log(mosq, obj, level, string):
    print(string)


# --- neOCampus related functions ---------------------------------------------
# Acquire sensors and publish
def publishSensors():
    # get CPU temperature (string)
    ## get CPU temperature (string)
    #CPU_temp = getCPUtemperature()
    ## add some randomisation to the temperature (float)
    #_fcputemp = float(CPU_temp) + random.uniform(-10,10)
    ## reconvert to string with quantization
    #CPU_temp = "{:.2f}".format(_fcputemp)
    #print("RPi temperature = " + CPU_temp)
    ## generate json payload
    #jsonFrame = {}
    #jsonFrame['unitID'] = str(getmac())
    #jsonFrame['value'] = json.loads(CPU_temp)
    #jsonFrame['value_units'] = 'celsius'
    #client.publish(MQTT_PUB, json.dumps(jsonFrame), MQTT_QOS)
    ## ... and publish it!
    print('publishing...\n')

# #############################################################################
#
# MAIN
#

def main():

    # Global variables
    global client, timer, log

    #
    log.info("\n###\nSample application to publish RPI's temperature to [%s]\non server %s:%d" % (MQTT_PUB,str(MQTT_SERVER),MQTT_PORT))
    log.info("(note: some randomization added to the temperature)")
    log.info("###")

    # Trap CTRL+C (kill -2)
    signal.signal(signal.SIGINT, ctrlc_handler)

    # MQTT setup
    client = mqtt.Client()
    client.username_pw_set(username="azerty",password="azerty")
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_publish = on_publish
    client.on_subscribe = on_subscribe
    if len(MQTT_USER)!=0 and len(MQTT_PASSWD)!=0:
        client.username_pw_set(MQTT_USER,MQTT_PASSWD); # set username / password

    # Start MQTT operations
    client.connect(MQTT_SERVER, MQTT_PORT, 60)
    client.loop_start()

    # Launch Acquisition & publish sensors till shutdown
    do_every(measure_interleave, publishSensors);

    # waiting for all threads to finish
    if( timer is not None ):
        timer.join()


# Execution or import
if __name__ == "__main__":

    # Logging setup
    logging.basicConfig(format="[%(asctime)s][%(module)s:%(funcName)s:%(lineno)d][%(levelname)s] %(message)s", stream=sys.stdout)
    log = logging.getLogger()

    print("\n[DBG] DEBUG mode activated ... ")
    log.setLevel(logging.DEBUG)
    #log.setLevel(logging.INFO)

    # Start executing
    main()


# The END - Jim Morrison 1943 - 1971
#sys.exit(0)

