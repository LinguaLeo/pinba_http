#!/usr/bin/env python

from cgi import parse_qs
from socket import socket, gethostname, AF_INET, SOCK_DGRAM
from sys import argv
from pprint import pprint

import re
import pinba_pb2

# You should set PINBA_HOST, PINBA_PORT values for uwsgi configuration 
# Also you can set PINBA_DEBUG for debugging

DEFAULT_PINBA_HOST = '127.0.0.1'
DEFAULT_PINBA_PORT = 30002
TIMER_MAX = 10*60

udpsock = socket(AF_INET, SOCK_DGRAM)
hostname = gethostname()

class InvalidTimer(Exception):
    pass

def pinba(server_name, tracker, timer, tags, pinba_host, pinba_port):
    """
    Send a message to Pinba.

    :param server_name: HTTP server name
    :param tracker:     tracker name
    :param timer:       timer value in seconds
    :param tags:        dictionary of tags
    :param pinba_host:  pinba host
    :param pinba_port:  pinba port
    """    
    if timer < 0 or timer > TIMER_MAX:
        raise InvalidTimer()

    msg = pinba_pb2.Request()
    msg.hostname = hostname
    msg.server_name = server_name
    msg.script_name = tracker
    msg.request_count = 1
    msg.document_size = 0
    msg.memory_peak = 0
    msg.request_time = timer
    msg.ru_utime = 0.0
    msg.ru_stime = 0.0
    msg.status = 200

    if tags:
        # Add a single timer
        msg.timer_hit_count.append(1)
        msg.timer_value.append(timer)

        # Encode associated tags
        tag_count = 0
        dictionary = [] # contains mapping of tags name or value => uniq id
        for name, values in tags.items():
            if name not in dictionary:
                dictionary.append(name)
            for value in values:
                value = str(value)
                if value not in dictionary:
                    dictionary.append(value)
                msg.timer_tag_name.append(dictionary.index(name))
                msg.timer_tag_value.append(dictionary.index(value))
                tag_count += 1

        # Number of tags
        msg.timer_tag_count.append(tag_count)

        # Global tags dictionary
        msg.dictionary.extend(dictionary);

    # Send message to Pinba server
    udpsock.sendto(msg.SerializeToString(), (pinba_host, pinba_port))

def get_option(environ, name, default):
    """
    Returns a value by name from "environ" parameter.
    
    :param environ: any dictionary
    :param name:    a search key
    :param default: value for undefined key
    """
    if (name in environ) and (environ[name] != ''):
        return environ[name]
    return default

def print_debug(values):
    """
    Print values to stdout.
    """
    print('Debug values')
    for key, value in values.items():
        print(key + ':')
        pprint(value)

def generic(prefix, environ):
    """
    Generic Pinba handler.

    The timer is in `t` and other parameters are considered to be
    additional tags. The tracker name is the end of the path.
    """
    tracker = environ['PATH_INFO'][len(prefix):]
    tags = parse_qs(environ['QUERY_STRING'])
    try:
        timer = float(tags.pop('t')[0])
    except KeyError:
        timer = 0.0

    pinba_host = get_option(environ, 'PINBA_HOST', DEFAULT_PINBA_HOST)
    pinba_port = int(get_option(environ, 'PINBA_PORT', DEFAULT_PINBA_PORT))
    
    if ('PINBA_DEBUG' in environ) and (environ['PINBA_DEBUG'] == '1'):
        print_debug({
            'pinba_host': pinba_host,
            'pinba_port': pinba_port,
            'server_name': environ['HTTP_HOST'],
            'tracket': tracker,
            'timer': timer,
            'tags': tags
        })
        
    pinba(environ['HTTP_HOST'], tracker, timer, tags, pinba_host, pinba_port)

# Simple routing
handlers = {
    '/track/': generic
}   

def app(environ, start_response):
    for h in handlers:
        if environ['PATH_INFO'].startswith(h):
            try:
                handlers[h](h, environ)
            except InvalidTimer:
                start_response('400 Invalid Timer', [('Content-Length', '0')])
                return ['']
            start_response('200 OK', [('Content-Length', '0')])
            return ['']
    start_response('404 Not Found', [('Content-Length', '0')])
    return ['']
