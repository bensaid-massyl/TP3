#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# High-level MQTT management module
#
# [mar.20] F.Thiebolt   added support to multiple topics to subscribe to
# [jan.20] F.Thiebolt   adapted for the weather agent app.
# [nov.19] F.Thiebolt   add on_log messages
# [sep.17] F.Thiebolt   extending support for MQTT errors
# [apr.17] F.Thiebolt   started to add support for MQTT errors
# [May.16] T.Bueno      initial release
#



# #############################################################################
#
# Import zone
#
import os
import sys
import time
import json
from threading import Thread, Event
import paho.mqtt.client as mqtt_client
from random import randint

MQTT_SERVER="192.168.0.210"
MQTT_PORT=1883
# Full MQTT_topic = MQTT_BASE + MQTT_TYPE
MQTT_BASE_TOPIC = "1R1/014"
MQTT_TYPE_TOPIC = "temperature"
MQTT_PUB = "/".join([MQTT_BASE_TOPIC, MQTT_TYPE_TOPIC])

# First subscription to same topic (for tests)
MQTT_SUB = MQTT_PUB
# ... then subscribe to <topic>/command to receive orders
#MQTT_SUB = "/".join([MQTT_PUB, "command"])

MQTT_QOS=0 # (default) no ACK from server
#MQTT_QOS=1 # server will ack every message

MQTT_USER="123456"
MQTT_PASSWD="123456"

# #############################################################################
#
# Class
#
class CommunicationModule(Thread):

    # class attributes ( __class__.<attr_name> )

    # objects attributes
    _connection     = None  # mqtt client
    _connected      = False
    _mqtt_user      = None
    _mqtt_passwd    = None
    _mqtt_topics    = None  # list of topics to subscribe to
    _unitID         = None
    _addons         = None  # additional parameters


    #
    # object initialization
    def __init__(self, mqtt_topics, *args, **kwargs ):
        super().__init__()
        print("initializing comm module")
        self._mqtt_topics   = mqtt_topics
        self._addons        = kwargs

        # check for _shutdown event
        self._shutdownEvent = self._addons.get('_shutdownEvent')
        if( self._shutdownEvent is None ):
            print("unspecified global shutdown ... thus locally specified ...")
            self._shutdownEvent = Event()

        # check for unitID
        if( "unitID" in self._addons and self._addons.get('unitID') is not None ):
            self._unitID = self._addons.get('unitID')

        # setup MQTT connection
        self._connection = mqtt_client.Client()
        self._connection.on_connect = self._on_connect
        self._connection.on_disconnect = self._on_disconnect
        self._connection.on_publish = self._on_publish
        self._connection.on_message = self._on_message
        self._connection.on_subscribe = self._on_subscribe
        self._connection.on_unsubscribe = self._on_unsubscribe

        self._connection.reconnect_delay_set( min_delay=100)
        self._connection.username_pw_set( MQTT_USER, MQTT_PASSWD )

        self._connected = False
        print("initialization done")


    #
    # called by Threading.start()
    def run( self ):
        # load module
        print("module loading")
        self.load()

        # start connection
        print("start MQTT connection to '%s:%d' ..." % (MQTT_SERVER,MQTT_PORT))
        self._connection.connect( host=MQTT_SERVER, port=MQTT_PORT, keepalive=1)

        # launch
        try:
            while not self._shutdownEvent.is_set():

                if self._connection.loop(timeout=2.0) != mqtt_client.MQTT_ERR_SUCCESS:
                    print("loop failed, sleeping a bit before retrying")
                    time.sleep(2)

            print("shutdown activated ...")

        except Exception as ex:
            print("module crashed: " + str(ex))

        # shutdown module
        print("module stopping")
        self.quit()

        # disconnect ...
        self._connection.disconnect()

        # end of thread
        print("Thread end ...")


    ''' are we connected ? '''
    def is_connected( self ):
        return self._connected


    ''' prepares and sends a payload in a MQTT message '''
    def send_message(self, topic, payload):
        if not self.is_connected():
            print("tried to publish a message while not connected ...")
            return

        if 'unitID' not in payload:
            payload['unitID'] = self._unitID

        if( payload['unitID'] is None ):
            print("tried to publish a message while not having a unitID ... aborting")
            return

        res, mid = self._connection.publish(topic, json.dumps(payload))

        if res != mqtt_client.MQTT_ERR_SUCCESS:
            print("on message published to topic " + topic)


    ''' handles pre-validated MQTT messages, to be implemented by subclasses '''
    def handle_message(self, topic, payload):
        pass


    ''' load method, to initialize modules before running, to be implemented by subclasses '''
    def load(self):
        pass


    ''' quit method, to shutdown modules before exiting, to be implemented by subclasses '''
    def quit(self):
        pass


    # -------------------------------------------------------------------------
    # Low-level functions
    # - _on_connect()
    # - _on_disconnect()
    # - _on_publish()
    # - _on_subscribe()
    # - _on_unsubscribe()
    # - _on_message()
    # - _on_log()
    # - _status()
    #


    ''' paho callback for connection '''
    def _on_connect(self, client, userdata, flags, rc):

        if rc != mqtt_client.MQTT_ERR_SUCCESS:
            print("unable to connect to broker '%s:%d': " % (self._addons['mqtt_server'],self._addons['mqtt_port']) + mqtt_client.error_string(rc))
            return

        print("connected to broker :)")
        self._connected = True

        # subscribe to topics list
        try:
            for topic in self._mqtt_topics:
                print("subscribing to " + str(topic))
                self._connection.subscribe( topic )   # QoS=0 default

        except Exception as ex:
            print("exception while subscribing to topic '%s' :" % str(topic) + str(ex))


    ''' paho callback for disconnection '''
    def _on_disconnect(self, client, userdata, rc):

        print("disconnected from MQTT broker with rc: " + mqtt_client.error_string(rc))
        self._connected = False
        if rc == mqtt_client.MQTT_ERR_SUCCESS:
            # means that disconnect has been requested (i.e not an unexpected event)
            return

        # unexpected disconnect ... we'll retry till death ...
        _time2sleep = randint( 0, 2 )
        while( rc != mqtt_client.MQTT_ERR_SUCCESS and self._shutdownEvent.is_set() is not True):
            if (_time2sleep > 300):     # max. 5mn between two retrials
                _time2sleep = 300
            print("Unexpected disconnection ... sleeping %d seconds before retrying" % _time2sleep)
            time.sleep(_time2sleep)
            print("... trying to reconnect ...")
            try:
                rc = self._connection.reconnect()
            except Exception as ex:
                print("caught exception while mqtt reconnect: " + str(ex) )
                rc = -1
            _time2sleep = _time2sleep*2


    ''' paho callback for published message '''
    def _on_publish(self, client, userdata, mid):
        print("mid: " + str(mid)+ " published!")


    ''' paho callback for message reception '''
    def _on_message(self, client, userdata, msg):

        #print("receiving a msg on topic '%s' ..." % str(msg.topic) )
        try:
            # loading and verifying payload
            payload = json.loads(msg.payload.decode('utf-8'))
            #validictory.validate(payload, self.COMMAND_SCHEMA)
        except Exception as ex:
            print("exception handling json payload from topic '%s': " % str(msg.topic) + str(ex))
            return

        # is it a message for us ??
        if( self._unitID is not None and payload['dest'] != "all" and payload['dest'] != str(self.unitID) ):
            print("msg received on topic '%s' features destID='%s' != self._unitID='%s'" % (str(msg.topic),payload['dest'],self.unitID) )
            return

        self.handle_message( msg.topic, payload )


    ''' paho callback for topic subscriptions '''
    def _on_subscribe(self, client, userdata, mid, granted_qos):
        print("Subscribed: " + str(mid) + " " + str(granted_qos))
        self._connected = True


    ''' paho callback for topic unsubscriptions '''
    def _on_unsubscribe(self, client, userdata, mid):
        pass


