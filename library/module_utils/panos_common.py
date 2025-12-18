#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Palo Alto Common Utilities
Shared functions for logging, error handling, and common operations
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime


class PanosException(Exception):
    """Custom exception for Palo Alto operations"""
    
    def __init__(self, message, error_code=None, details=None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self):
        return {
            'message': self.message,
            'error_code': self.error_code,
            'details': self.details
        }


class PanosLogger:
    """Simple logger for Palo Alto operations"""
    
    def __init__(self, module_name, verbosity=1):
        self.module_name = module_name
        self.verbosity = verbosity
        self.logs = []
    
    def _log(self, level, message):
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level,
            'module': self.module_name,
            'message': message
        }
        self.logs.append(entry)
        return entry
    
    def debug(self, message):
        if self.verbosity >= 3:
            return self._log('DEBUG', message)
    
    def info(self, message):
        if self.verbosity >= 1:
            return self._log('INFO', message)
    
    def warning(self, message):
        return self._log('WARNING', message)
    
    def error(self, message):
        return self._log('ERROR', message)
    
    def get_logs(self):
        return self.logs


def parse_panos_version(version_string):
    """
    Parse PAN-OS version string into components
    
    Args:
        version_string: Version like '10.2.9' or '11.1.3-h1'
    
    Returns:
        dict with major, minor, patch, hotfix components
    """
    if not version_string:
        return None
    
    pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-h(\d+))?(?:-c(\d+))?$'
    match = re.match(pattern, str(version_string).strip())
    
    if not match:
        return None
    
    return {
        'major': int(match.group(1)),
        'minor': int(match.group(2)),
        'patch': int(match.group(3)),
        'hotfix': int(match.group(4)) if match.group(4) else 0,
        'candidate': int(match.group(5)) if match.group(5) else 0,
        'raw': version_string.strip()
    }


def compare_versions(version1, version2):
    """
    Compare two PAN-OS versions
    
    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
    """
    v1 = parse_panos_version(version1)
    v2 = parse_panos_version(version2)
    
    if not v1 or not v2:
        raise PanosException(
            "Invalid version format",
            error_code="INVALID_VERSION",
            details={'version1': version1, 'version2': version2}
        )
    
    for key in ['major', 'minor', 'patch', 'hotfix']:
        if v1[key] < v2[key]:
            return -1
        elif v1[key] > v2[key]:
            return 1
    
    return 0


def is_upgrade_path_valid(current_version, target_version, version_matrix):
    """
    Check if upgrade path is valid according to version matrix
    
    Args:
        current_version: Current PAN-OS version
        target_version: Target PAN-OS version
        version_matrix: Dict of valid upgrade paths
    
    Returns:
        tuple: (is_valid, required_intermediate_versions)
    """
    current = parse_panos_version(current_version)
    target = parse_panos_version(target_version)
    
    if not current or not target:
        return False, []
    
    # Same version check
    if compare_versions(current_version, target_version) == 0:
        return True, []
    
    # Downgrade check
    if compare_versions(current_version, target_version) > 0:
        return False, []
    
    # Check version matrix for valid paths
    current_major_minor = f"{current['major']}.{current['minor']}"
    target_major_minor = f"{target['major']}.{target['minor']}"
    
    if current_major_minor in version_matrix:
        valid_targets = version_matrix[current_major_minor].get('direct_upgrade_to', [])
        if target_major_minor in valid_targets:
            return True, []
        
        # Check for required intermediate versions
        intermediate = version_matrix[current_major_minor].get('intermediate_required', {})
        if target_major_minor in intermediate:
            return True, intermediate[target_major_minor]
    
    return False, []


def parse_xml_response(xml_string):
    """
    Parse XML response from PAN-OS API
    
    Args:
        xml_string: Raw XML response string
    
    Returns:
        dict with status and parsed data
    """
    try:
        root = ET.fromstring(xml_string)
        
        status = root.get('status', 'unknown')
        code = root.get('code')
        
        result = {
            'status': status,
            'code': code,
            'success': status == 'success',
            'data': {},
            'message': None
        }
        
        # Extract message if present
        msg_elem = root.find('.//msg')
        if msg_elem is not None:
            if msg_elem.text:
                result['message'] = msg_elem.text
            else:
                # Check for line elements
                lines = msg_elem.findall('.//line')
                if lines:
                    result['message'] = '\n'.join(
                        line.text for line in lines if line.text
                    )
        
        # Extract result data
        result_elem = root.find('.//result')
        if result_elem is not None:
            result['data'] = xml_element_to_dict(result_elem)
        
        return result
        
    except ET.ParseError as e:
        raise PanosException(
            f"Failed to parse XML response: {str(e)}",
            error_code="XML_PARSE_ERROR",
            details={'raw_response': xml_string[:500]}
        )


def xml_element_to_dict(element):
    """
    Convert XML element to dictionary recursively
    """
    result = {}
    
    # Add attributes
    if element.attrib:
        result['@attributes'] = dict(element.attrib)
    
    # Process children
    children = list(element)
    if children:
        child_dict = {}
        for child in children:
            child_data = xml_element_to_dict(child)
            
            if child.tag in child_dict:
                # Convert to list if multiple same-named children
                if not isinstance(child_dict[child.tag], list):
                    child_dict[child.tag] = [child_dict[child.tag]]
                child_dict[child.tag].append(child_data)
            else:
                child_dict[child.tag] = child_data
        
        result.update(child_dict)
    
    # Add text content
    if element.text and element.text.strip():
        if result:
            result['#text'] = element.text.strip()
        else:
            return element.text.strip()
    
    return result if result else None


def wait_for_job(api_client, job_id, timeout=1800, poll_interval=30, logger=None):
    """
    Wait for a PAN-OS job to complete
    
    Args:
        api_client: PanosApiClient instance
        job_id: Job ID to monitor
        timeout: Maximum wait time in seconds
        poll_interval: Time between status checks
        logger: Optional PanosLogger instance
    
    Returns:
        dict with job result
    """
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        
        if elapsed > timeout:
            raise PanosException(
                f"Job {job_id} timed out after {timeout} seconds",
                error_code="JOB_TIMEOUT",
                details={'job_id': job_id, 'elapsed': elapsed}
            )
        
        # Get job status
        response = api_client.get_job_status(job_id)
        
        if logger:
            logger.debug(f"Job {job_id} status: {response}")
        
        status = response.get('data', {}).get('job', {})
        job_status = status.get('status', 'UNKNOWN')
        job_result = status.get('result', 'UNKNOWN')
        progress = status.get('progress', '0')
        
        if logger:
            logger.info(f"Job {job_id}: {job_status} - {progress}% complete")
        
        if job_status == 'FIN':
            return {
                'success': job_result == 'OK',
                'result': job_result,
                'details': status,
                'elapsed': elapsed
            }
        
        time.sleep(poll_interval)


def sanitize_hostname(hostname):
    """
    Sanitize hostname for use in filenames and API calls
    """
    if not hostname:
        return "unknown"
    
    # Remove or replace invalid characters
    sanitized = re.sub(r'[^\w\-\.]', '_', str(hostname))
    return sanitized[:63]  # Limit length


def format_timestamp(fmt="%Y%m%d_%H%M%S"):
    """
    Get formatted timestamp string
    """
    return datetime.utcnow().strftime(fmt)


def build_backup_filename(hostname, backup_type="config"):
    """
    Build standardized backup filename
    
    Args:
        hostname: Device hostname
        backup_type: Type of backup (config, state, tech_support)
    
    Returns:
        Formatted filename string
    """
    safe_hostname = sanitize_hostname(hostname)
    timestamp = format_timestamp()
    return f"{safe_hostname}_{backup_type}_{timestamp}.xml"


def validate_ip_or_hostname(value):
    """
    Validate that value is a valid IP address or hostname
    """
    if not value:
        return False
    
    # IP address pattern
    ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    
    # Hostname pattern
    hostname_pattern = r'^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$'
    
    return bool(re.match(ip_pattern, value) or re.match(hostname_pattern, value))


def extract_ha_info(ha_response):
    """
    Extract HA information from API response
    
    Args:
        ha_response: Parsed API response for HA state
    
    Returns:
        dict with HA status information
    """
    data = ha_response.get('data', {})
    
    # Navigate to HA state info
    group = data.get('group', {})
    local_info = group.get('local-info', {})
    peer_info = group.get('peer-info', {})
    
    return {
        'enabled': bool(group),
        'mode': local_info.get('mode', 'standalone'),
        'state': local_info.get('state', 'unknown'),
        'peer_state': peer_info.get('state', 'unknown'),
        'running_sync': local_info.get('running-sync', 'unknown'),
        'running_sync_enabled': local_info.get('running-sync-enabled', 'no'),
        'preemptive': local_info.get('preemptive', 'no'),
        'priority': local_info.get('priority', '0'),
        'peer_address': peer_info.get('mgmt-ip', ''),
        'raw': data
    }
