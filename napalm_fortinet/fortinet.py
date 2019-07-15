# -*- coding: utf-8 -*-
# Copyright 2016 Dravetech AB. All rights reserved.
#
# The contents of this file are licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

""" Napalm driver for Fortinet.
Read https://napalm.readthedocs.io for more information.  """

from netmiko import __version__ as netmiko_version
from netmiko import ConnectHandler, FileTransfer, InLineTransfer
import socket
from napalm.base import NetworkDriver
from napalm.base.exceptions import ( 
    ConnectionClosedException,
    SessionLockedException,
    MergeConfigException,
    ReplaceConfigException,
    CommandErrorException,
)

import logging

logger = logging.getLogger(__name__)

class FortinetDriver(NetworkDriver):
    """Napalm driver for Fortinet."""

    def __init__(self, hostname, username, password, timeout=60,
            optional_args=None):
        """Constructor."""
        self.device = None
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout

        if optional_args is None:
            optional_args = {}

        # proxy part
        self.proxy_host = optional_args.get('proxy_host', None)
        self.proxy_username = optional_args.get('proxy_username', None)
        self.proxy_password = optional_args.get('proxy_password', None)
        self.proxy_port = optional_args.get('proxy_port', None)
       

        # Check for proxy parameters and generate ssh config file
        if self.proxy_host:
            if self.proxy_port and self.proxy_username: 
                print("Generate SSH proxy config file for hopping station: {}"
                        .format(self.proxy_host))
                self.ssh_proxy_file = self._generate_ssh_proxy_file()
            else:
                raise ValueError("All proxy options must be specified ")
        else:
            self.ssh_proxy_file = None

        # Netmiko possible arguments
        netmiko_argument_map = {
            'ip': None,
            'username': None,
            'password': None,
            'port': None,
            'secret': '',
            'verbose': False,
            'keepalive': 30,
            'global_delay_factor': 3,
            'use_keys': False,
            'key_file': None,
            'ssh_strict': False,
            'system_host_keys': False,
            'alt_host_keys': False,
            'alt_key_file': '',
            'ssh_config_file': None,
        }
         

        fields = netmiko_version.split('.')
        fields = [int(x) for x in fields]
        maj_ver, min_ver, bug_fix = fields
        if maj_ver >= 2:
            netmiko_argument_map['allow_agent'] = False
        elif maj_ver == 1 and min_ver >= 1:
            netmiko_argument_map['allow_agent'] = False

        # Build dict of any optional Netmiko args
        self.netmiko_optional_args = {}
        for k, v in netmiko_argument_map.items():
            try:
                self.netmiko_optional_args[k] = optional_args[k]
            except KeyError:
                pass
        if self.ssh_proxy_file:
            self.netmiko_optional_args['ssh_config_file'] = self.ssh_proxy_file

    
    def _generate_ssh_proxy_file(self):
        filename = '/var/tmp/ssh_proxy_'+ self.hostname
        fh = open(filename, 'w')
        fh.write('Host '+ self.hostname + '\n')
        fh.write('HostName '+ self.hostname + '\n')
        fh.write('User '+ self.proxy_username +'\n')
        fh.write('Port 22'+'\n')
        fh.write('StrictHostKeyChecking no\n')
        fh.write('ProxyCommand ssh '
                + self.proxy_username  +'@'+ self.proxy_host+' nc %h %p')
        fh.close()
        return filename


    def open(self):
        """ Open a connection to the device."""
        self.device = ConnectHandler(
                device_type = 'fortinet',
                host = self.hostname,
                username = self.username,
                password = self.password,
                **self.netmiko_optional_args)

    def close(self):
        """ Close the connection to the device."""
        self.device.disconnect()


    def cli(self, commands):
        """ Will execute a list of commands and return the output in a
        dictionary format.  """
        cli_output = dict()
        if type(commands) is not list:
            raise TypeError('Please enter a valid list of commands!')
        
        for command in commands:
            output = self._send_command(command)
            if 'Command fail. Return code 1' in output:
                raise ValueError(
                    'Unable to execute command "{}"'.format(command))
            cli_output.setdefault(command, {})
            cli_output[command] = output
        return cli_output

    def _send_command(self, command):
        """ Wrapper for self.device.send.command().  If command is a list will
        iterate through commands until valid command.  """
        try:
            if isinstance(command, list):
                for cmd in command:
                    output = self.device.send_command_timing(cmd)
                    if 'Command fail. Return code 1' not in output:
                        break
            else:
                output = self.device.send_command_timing(command)
            return output
        except (socket.error, EOFError) as e:
            raise ConnectionClosedException(str(e))
