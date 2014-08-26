#!/usr/bin/env python

from cgi import parse_qs
from socket import socket, gethostname, AF_INET, SOCK_DGRAM
from sys import argv
from pprint import pprint

import re
import pinba_pb2

VERSION = 1.1

# For work we need set PINBA_HOST,PINBA_PORT value in file uswgi_params,this file located in folder nginx 
# Additional parameter PINBA_DEBUG_MODE set in uswgi_params


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

def generic(prefix, environ):
    """
    Generic Pinba handler.

    The timer is in `t` and other parameters are considered to be
    additional tags. The tracker name is the end of the path.
    """
    tracker = environ["PATH_INFO"][len(prefix):]
    tags = parse_qs(environ['QUERY_STRING'])
    try:
        timer = float(tags.pop('t')[0])
    except KeyError:
        timer = 0.0

    if ('PINBA_HOST' in environ) and (environ['PINBA_HOST'] != ''):
      pinba_host = environ['PINBA_HOST']
    else:
      pinba_host = DEFAULT_PINBA_HOST
    pprint(environ)
    if ('PINBA_PORT' in environ) and (environ['PINBA_PORT'] != ''):
      pinba_port = environ['PINBA_PORT']
    else:
      pinba_port = DEFAULT_PINBA_PORT
   
    if ('PINBA_DEBUG_MODE' in environ) and (environ['PINBA_DEBUG_MODE'] == '1'):
       print('Params :');
       print('PINBA_HOST:')
       pprint(pinba_host);
       print('PINBAPORT:');
       pprint(pinba_port);
       print('server_name:');
       pprint(environ['HTTP_HOST']);
       print('tracker:');
       pprint(tracker);
       print('timer:');
       pprint(timer);
       print('tags:');
       pprint(tags);
    pinba(environ['HTTP_HOST'], tracker, timer, tags, pinba_host, pinba_port)

# Simple routing
handlers = {
    "/track/": generic
}
#  res = ''
#  for key in array:
#     res = res + key + str(array[key]) + ','
#  return res   

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
