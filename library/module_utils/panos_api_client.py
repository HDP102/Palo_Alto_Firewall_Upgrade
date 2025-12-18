#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Palo Alto REST API Client
Wrapper for Panorama REST API operations
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import json
import ssl
import urllib.request
import urllib.parse
import urllib.error
from xml.etree import ElementTree as ET

try:
    from ansible.module_utils.panos_common import (
        PanosException,
        PanosLogger,
        parse_xml_response
    )
except ImportError:
    from panos_common import (
        PanosException,
        PanosLogger,
        parse_xml_response
    )


class PanosApiClient:
    """
    REST API client for Palo Alto Panorama
    
    Handles authentication, API calls, and response parsing
    for device management through Panorama.
    """
    
    def __init__(self, host, username=None, password=None, api_key=None,
                 validate_certs=True, timeout=120, port=443, logger=None):
        """
        Initialize API client
        
        Args:
            host: Panorama hostname or IP
            username: API username (if not using api_key)
            password: API password (if not using api_key)
            api_key: Pre-generated API key (alternative to user/pass)
            validate_certs: Whether to validate SSL certificates
            timeout: API request timeout in seconds
            port: HTTPS port (default 443)
            logger: Optional PanosLogger instance
        """
        self.host = host
        self.username = username
        self.password = password
        self.api_key = api_key
        self.validate_certs = validate_certs
        self.timeout = timeout
        self.port = port
        self.logger = logger or PanosLogger('api_client')
        
        self.base_url = f"https://{host}:{port}"
        self._ssl_context = self._create_ssl_context()
    
    def _create_ssl_context(self):
        """Create SSL context based on certificate validation setting"""
        context = ssl.create_default_context()
        if not self.validate_certs:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context
    
    def _get_api_key(self):
        """Get or generate API key"""
        if self.api_key:
            return self.api_key
        
        if not self.username or not self.password:
            raise PanosException(
                "Either api_key or username/password must be provided",
                error_code="AUTH_MISSING"
            )
        
        # Generate API key from credentials
        params = {
            'type': 'keygen',
            'user': self.username,
            'password': self.password
        }
        
        url = f"{self.base_url}/api/?{urllib.parse.urlencode(params)}"
        
        try:
            request = urllib.request.Request(url)
            response = urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=self._ssl_context
            )
            
            xml_response = response.read().decode('utf-8')
            parsed = parse_xml_response(xml_response)
            
            if not parsed['success']:
                raise PanosException(
                    f"Failed to generate API key: {parsed.get('message', 'Unknown error')}",
                    error_code="KEYGEN_FAILED"
                )
            
            # Extract key from response
            key = parsed.get('data', {}).get('key')
            if not key:
                raise PanosException(
                    "API key not found in response",
                    error_code="KEYGEN_NO_KEY"
                )
            
            self.api_key = key
            self.logger.info("API key generated successfully")
            return key
            
        except urllib.error.URLError as e:
            raise PanosException(
                f"Connection failed: {str(e)}",
                error_code="CONNECTION_ERROR",
                details={'host': self.host}
            )
    
    def _make_request(self, params, method='GET', data=None):
        """
        Make API request to Panorama
        
        Args:
            params: URL parameters dict
            method: HTTP method
            data: POST data if applicable
        
        Returns:
            Parsed response dict
        """
        api_key = self._get_api_key()
        params['key'] = api_key
        
        url = f"{self.base_url}/api/?{urllib.parse.urlencode(params)}"
        
        self.logger.debug(f"API request: {params.get('type')} - {params.get('cmd', params.get('action', 'N/A'))}")
        
        try:
            request = urllib.request.Request(url, method=method)
            
            if data:
                request.data = data.encode('utf-8')
                request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            response = urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=self._ssl_context
            )
            
            xml_response = response.read().decode('utf-8')
            parsed = parse_xml_response(xml_response)
            
            self.logger.debug(f"API response status: {parsed['status']}")
            
            return parsed
            
        except urllib.error.HTTPError as e:
            raise PanosException(
                f"HTTP error {e.code}: {e.reason}",
                error_code="HTTP_ERROR",
                details={'code': e.code, 'reason': e.reason}
            )
        except urllib.error.URLError as e:
            raise PanosException(
                f"Connection error: {str(e)}",
                error_code="CONNECTION_ERROR",
                details={'host': self.host}
            )
    
    def op_command(self, cmd, target=None):
        """
        Execute operational command
        
        Args:
            cmd: XML command string
            target: Target device serial (for Panorama-managed devices)
        
        Returns:
            Parsed response
        """
        params = {
            'type': 'op',
            'cmd': cmd
        }
        
        if target:
            params['target'] = target
        
        return self._make_request(params)
    
    def get_system_info(self, target=None):
        """Get system information from device"""
        cmd = "<show><system><info></info></system></show>"
        return self.op_command(cmd, target)
    
    def get_ha_state(self, target=None):
        """Get HA state information"""
        cmd = "<show><high-availability><state></state></high-availability></show>"
        return self.op_command(cmd, target)
    
    def get_software_info(self, target=None):
        """Get installed and available software versions"""
        cmd = "<show><system><software><versions></versions></software></system></show>"
        return self.op_command(cmd, target)
    
    def check_software(self, target=None):
        """Check for available software updates"""
        cmd = "<request><system><software><check></check></software></system></request>"
        return self.op_command(cmd, target)
    
    def download_software(self, version, target=None, sync=False):
        """
        Download PAN-OS software version
        
        Args:
            version: Software version to download
            target: Target device serial
            sync: Whether to wait for completion
        
        Returns:
            Job ID or completion status
        """
        sync_str = "yes" if sync else "no"
        cmd = f"<request><system><software><download><sync>{sync_str}</sync><version>{version}</version></download></software></system></request>"
        return self.op_command(cmd, target)
    
    def install_software(self, version, target=None):
        """
        Install PAN-OS software version
        
        Args:
            version: Software version to install
            target: Target device serial
        
        Returns:
            Job ID for installation
        """
        cmd = f"<request><system><software><install><version>{version}</version></install></software></system></request>"
        return self.op_command(cmd, target)
    
    def reboot_device(self, target=None):
        """Reboot the device"""
        cmd = "<request><restart><system></system></restart></request>"
        return self.op_command(cmd, target)
    
    def get_job_status(self, job_id, target=None):
        """Get status of a job"""
        cmd = f"<show><jobs><id>{job_id}</id></jobs></show>"
        return self.op_command(cmd, target)
    
    def get_all_jobs(self, target=None):
        """Get all jobs"""
        cmd = "<show><jobs><all></all></jobs></show>"
        return self.op_command(cmd, target)
    
    def export_config(self, target=None, category="running-config"):
        """
        Export device configuration
        
        Args:
            target: Target device serial
            category: Config type (running-config, candidate-config)
        
        Returns:
            Configuration XML
        """
        params = {
            'type': 'export',
            'category': category
        }
        
        if target:
            params['target'] = target
        
        return self._make_request(params)
    
    def export_device_state(self, target=None):
        """Export full device state"""
        params = {
            'type': 'export',
            'category': 'device-state'
        }
        
        if target:
            params['target'] = target
        
        return self._make_request(params)
    
    def get_panorama_managed_devices(self):
        """Get list of devices managed by Panorama"""
        cmd = "<show><devices><all></all></devices></show>"
        return self.op_command(cmd)
    
    def get_device_by_name(self, device_name):
        """
        Get device info by hostname
        
        Args:
            device_name: Device hostname
        
        Returns:
            Device info dict with serial number
        """
        response = self.get_panorama_managed_devices()
        
        if not response['success']:
            raise PanosException(
                "Failed to retrieve managed devices",
                error_code="DEVICE_LOOKUP_FAILED",
                details={'response': response}
            )
        
        devices = response.get('data', {}).get('devices', {}).get('entry', [])
        
        # Handle single device case
        if isinstance(devices, dict):
            devices = [devices]
        
        for device in devices:
            hostname = device.get('hostname', '')
            if hostname.lower() == device_name.lower():
                return {
                    'hostname': hostname,
                    'serial': device.get('@attributes', {}).get('name', device.get('serial', '')),
                    'ip_address': device.get('ip-address', ''),
                    'model': device.get('model', ''),
                    'sw_version': device.get('sw-version', ''),
                    'connected': device.get('connected', 'no'),
                    'ha_state': device.get('ha', {}).get('state', 'standalone'),
                    'ha_peer_serial': device.get('ha', {}).get('peer', {}).get('serial', ''),
                    'raw': device
                }
        
        raise PanosException(
            f"Device '{device_name}' not found in Panorama",
            error_code="DEVICE_NOT_FOUND",
            details={'device_name': device_name}
        )
    
    def get_device_by_serial(self, serial):
        """
        Get device info by serial number
        
        Args:
            serial: Device serial number
        
        Returns:
            Device info dict
        """
        response = self.get_panorama_managed_devices()
        
        if not response['success']:
            raise PanosException(
                "Failed to retrieve managed devices",
                error_code="DEVICE_LOOKUP_FAILED"
            )
        
        devices = response.get('data', {}).get('devices', {}).get('entry', [])
        
        if isinstance(devices, dict):
            devices = [devices]
        
        for device in devices:
            device_serial = device.get('@attributes', {}).get('name', device.get('serial', ''))
            if device_serial == serial:
                return {
                    'hostname': device.get('hostname', ''),
                    'serial': device_serial,
                    'ip_address': device.get('ip-address', ''),
                    'model': device.get('model', ''),
                    'sw_version': device.get('sw-version', ''),
                    'connected': device.get('connected', 'no'),
                    'ha_state': device.get('ha', {}).get('state', 'standalone'),
                    'ha_peer_serial': device.get('ha', {}).get('peer', {}).get('serial', ''),
                    'raw': device
                }
        
        raise PanosException(
            f"Device with serial '{serial}' not found",
            error_code="DEVICE_NOT_FOUND",
            details={'serial': serial}
        )
    
    def suspend_ha(self, target=None):
        """Suspend HA on device"""
        cmd = "<request><high-availability><state><suspend></suspend></state></high-availability></request>"
        return self.op_command(cmd, target)
    
    def resume_ha(self, target=None):
        """Resume HA on device"""
        cmd = "<request><high-availability><state><functional></functional></state></high-availability></request>"
        return self.op_command(cmd, target)
    
    def sync_ha(self, target=None):
        """Force HA sync to peer"""
        cmd = "<request><high-availability><sync-to-remote><running-config></running-config></sync-to-remote></high-availability></request>"
        return self.op_command(cmd, target)
    
    def get_resource_utilization(self, target=None):
        """Get CPU, memory, disk utilization"""
        cmd = "<show><system><resources></resources></system></show>"
        return self.op_command(cmd, target)
    
    def get_session_count(self, target=None):
        """Get active session count"""
        cmd = "<show><session><info></info></session></show>"
        return self.op_command(cmd, target)
    
    def test_connectivity(self, target=None):
        """
        Test connectivity to device
        
        Returns:
            dict with connectivity status
        """
        try:
            response = self.get_system_info(target)
            
            if response['success']:
                system = response.get('data', {}).get('system', {})
                return {
                    'connected': True,
                    'hostname': system.get('hostname', ''),
                    'model': system.get('model', ''),
                    'serial': system.get('serial', ''),
                    'sw_version': system.get('sw-version', ''),
                    'uptime': system.get('uptime', '')
                }
            else:
                return {
                    'connected': False,
                    'error': response.get('message', 'Unknown error')
                }
                
        except PanosException as e:
            return {
                'connected': False,
                'error': str(e),
                'error_code': e.error_code
            }
