#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""

Copyright (c) 2021 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.

"""

__author__ = "Phithakkit Phasuk"
__email__ = "phphasuk@cisco.com"
__version__ = "0.1.0"
__copyright__ = "Copyright (c) 2021 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.1"



from netmiko import Netmiko
from utils import csv_to_dict
from jinja2 import Environment, FileSystemLoader
from config import INVENTORY_FILE, TEMPLATE_FILE, APPLICATION_LOG_FILE
import logging

#devices = { 'host': '10.88.174.137',
#            'username': 'admin',
#            'password': 'cisco!123',
#            'device_type': 'cisco_xe',
#            'session_log': 'session_log.txt'
#            }

logging.basicConfig(
                    filename=APPLICATION_LOG_FILE,
                    level=logging.DEBUG,
                    format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                    )
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)s: %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)
logging.info('starting the program.')

devices = csv_to_dict(INVENTORY_FILE)
logging.info('Loading inventory done.')

j2_env = Environment(loader=FileSystemLoader('.'))
config_template = j2_env.get_template(TEMPLATE_FILE)
logging.info('Loading configuration template done.')

for id, device_info in devices.items():
    device = {}
    device['host'] = device_info['host']
    device['username'] = device_info['username']
    device['password'] = device_info['password']
    device['device_type'] = device_info['device_type']
    device['session_log'] = device_info['session_log']
    try:
        ssh_conn = Netmiko(**device)
        logging.info(f'{device["host"]}: connected')
        output = ssh_conn.send_command('hw-module session 0/3 clear')
        output = ssh_conn.send_command('hw-module session 0/3', expect_string='Terminal ready', strip_prompt=False)
        output = ssh_conn.send_command_timing('', delay_factor=1)
        output = ssh_conn.find_prompt()
        while output != '(Cisco Controller) >':
            if output == 'User:':
                output = ssh_conn.send_command(device_info['em_username'], expect_string='Password:', strip_prompt=False)
                output = ssh_conn.send_command_timing(device_info['em_password'], delay_factor=1)
            else:
                output = ssh_conn.send_command_timing('\x1A', delay_factor=1)
                output = ssh_conn.send_command_timing('', delay_factor=1)
        output = ssh_conn.disable_paging(command='config paging disable')
        logging.info(f'{device["host"]}: mobility express module connected')

        device_param = {}
        for item in device_info:
            if item not in ['host', 'username', 'password', 'device_type', 'session_log', 'em_username', 'em_password']:
                device_param[item] = device_info[item]
        device_config = config_template.render(device_param)
        device_config_lines = device_config.splitlines()


        logging.info(f'{device["host"]}: start parsing the configuration')
        # Need to put more conditions to test the response prompt
        for device_config_line in device_config_lines:
            logging.debug(f'{device["host"]}: config = {device_config_line}')
            output = ssh_conn.send_command(device_config_line, expect_string='\(Cisco Controller\)', strip_prompt=False)
        logging.info(f'{device["host"]}: configuration complete')


        output = ssh_conn.disable_paging(command='config paging enable')
        output = ssh_conn.send_command('save config', expect_string='y/n', strip_prompt=False)
        output = ssh_conn.send_command('y', expect_string='Saved', strip_prompt=False)
        output = ssh_conn.find_prompt()
        while output != 'User:':
            output = ssh_conn.send_command_timing('\x1A', delay_factor=1)
            output = ssh_conn.send_command('logout', expect_string='User:', strip_prompt=False)
            output = ssh_conn.find_prompt()
        output = ssh_conn.send_command_timing('\x01\x11', delay_factor=1)
        output = ssh_conn.find_prompt()
        ssh_conn.disconnect()
        logging.info(f'{device["host"]}: disconnected')
        logging.info(f'{device["host"]}: configuration done')
    
    except Exception as err:
        logging.error(f'{device["host"]}: configuration failed with error = {err}')
        continue
