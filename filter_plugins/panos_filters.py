#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Palo Alto Custom Filters
Jinja2 filters for version comparison, data formatting, and utilities
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import re
from datetime import datetime


def parse_panos_version(version_string):
    """
    Parse PAN-OS version string into components
    
    Example: '10.2.9-h1' -> {'major': 10, 'minor': 2, 'patch': 9, 'hotfix': 1}
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


def panos_version_compare(version1, version2):
    """
    Compare two PAN-OS versions
    
    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
    
    Usage in Jinja2:
        {{ current_version | panos_version_compare(target_version) }}
    """
    v1 = parse_panos_version(version1)
    v2 = parse_panos_version(version2)
    
    if not v1 or not v2:
        return None
    
    for key in ['major', 'minor', 'patch', 'hotfix']:
        if v1[key] < v2[key]:
            return -1
        elif v1[key] > v2[key]:
            return 1
    
    return 0


def panos_version_gte(version1, version2):
    """
    Check if version1 >= version2
    
    Usage:
        {% if current_version | panos_version_gte('10.1.0') %}
    """
    result = panos_version_compare(version1, version2)
    return result is not None and result >= 0


def panos_version_lte(version1, version2):
    """Check if version1 <= version2"""
    result = panos_version_compare(version1, version2)
    return result is not None and result <= 0


def panos_version_gt(version1, version2):
    """Check if version1 > version2"""
    result = panos_version_compare(version1, version2)
    return result is not None and result > 0


def panos_version_lt(version1, version2):
    """Check if version1 < version2"""
    result = panos_version_compare(version1, version2)
    return result is not None and result < 0


def panos_version_eq(version1, version2):
    """Check if version1 == version2"""
    result = panos_version_compare(version1, version2)
    return result is not None and result == 0


def panos_major_minor(version):
    """
    Extract major.minor from version string
    
    Example: '10.2.9-h1' -> '10.2'
    """
    parsed = parse_panos_version(version)
    if not parsed:
        return None
    return f"{parsed['major']}.{parsed['minor']}"


def panos_is_hotfix(version):
    """
    Check if version is a hotfix release
    
    Example: '10.2.9-h1' -> True, '10.2.9' -> False
    """
    parsed = parse_panos_version(version)
    if not parsed:
        return False
    return parsed['hotfix'] > 0


def panos_normalize_version(version):
    """
    Normalize version string for consistent comparison
    
    Example: '10.2.9' -> '10.2.9-h0'
    """
    parsed = parse_panos_version(version)
    if not parsed:
        return version
    
    base = f"{parsed['major']}.{parsed['minor']}.{parsed['patch']}"
    if parsed['hotfix'] > 0:
        return f"{base}-h{parsed['hotfix']}"
    return base


def ha_state_is_active(ha_state):
    """
    Check if HA state indicates active role
    
    Usage:
        {% if ha_info.state | ha_state_is_active %}
    """
    if not ha_state:
        return False
    return str(ha_state).lower() in ['active', 'active-primary', 'primary']


def ha_state_is_passive(ha_state):
    """Check if HA state indicates passive role"""
    if not ha_state:
        return False
    return str(ha_state).lower() in ['passive', 'active-secondary', 'secondary']


def ha_state_is_standalone(ha_state):
    """Check if device is standalone (no HA)"""
    if not ha_state:
        return True
    return str(ha_state).lower() in ['standalone', 'disabled', '']


def format_bytes(bytes_value, precision=2):
    """
    Format bytes to human readable string
    
    Example: 1073741824 -> '1.00 GB'
    """
    try:
        bytes_value = float(bytes_value)
    except (TypeError, ValueError):
        return str(bytes_value)
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(bytes_value) < 1024.0:
            return f"{bytes_value:.{precision}f} {unit}"
        bytes_value /= 1024.0
    
    return f"{bytes_value:.{precision}f} PB"


def format_uptime(uptime_string):
    """
    Parse and format uptime string
    
    Example: '123 days, 4:56:78' -> {'days': 123, 'hours': 4, 'minutes': 56}
    """
    if not uptime_string:
        return {'days': 0, 'hours': 0, 'minutes': 0, 'raw': ''}
    
    # Try to parse common formats
    days = 0
    hours = 0
    minutes = 0
    
    # Pattern: "X days, HH:MM:SS"
    match = re.match(r'(\d+)\s*days?,?\s*(\d+):(\d+):(\d+)', str(uptime_string))
    if match:
        days = int(match.group(1))
        hours = int(match.group(2))
        minutes = int(match.group(3))
    else:
        # Pattern: "HH:MM:SS"
        match = re.match(r'(\d+):(\d+):(\d+)', str(uptime_string))
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
    
    return {
        'days': days,
        'hours': hours,
        'minutes': minutes,
        'total_minutes': (days * 24 * 60) + (hours * 60) + minutes,
        'raw': uptime_string
    }


def uptime_minutes(uptime_string):
    """Get total uptime in minutes"""
    parsed = format_uptime(uptime_string)
    return parsed['total_minutes']


def sanitize_filename(name):
    """
    Sanitize string for use as filename
    
    Example: 'firewall-01.example.com' -> 'firewall-01_example_com'
    """
    if not name:
        return "unknown"
    
    sanitized = re.sub(r'[^\w\-]', '_', str(name))
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized[:63].strip('_')


def timestamp_now(fmt="%Y%m%d_%H%M%S"):
    """
    Get current timestamp string
    
    Usage:
        {{ '' | timestamp_now }}
        {{ '%Y-%m-%d' | timestamp_now }}
    """
    return datetime.utcnow().strftime(fmt if fmt else "%Y%m%d_%H%M%S")


def backup_filename(hostname, backup_type="config", extension="xml"):
    """
    Generate standardized backup filename
    
    Usage:
        {{ device_hostname | backup_filename('config') }}
    """
    safe_name = sanitize_filename(hostname)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{safe_name}_{backup_type}_{timestamp}.{extension}"


def extract_job_id(api_response):
    """
    Extract job ID from API response
    
    Usage:
        {{ download_result | extract_job_id }}
    """
    if not api_response:
        return None
    
    # Try common paths
    data = api_response.get('data', {})
    
    # Direct job ID
    if 'job' in data:
        job = data['job']
        if isinstance(job, dict):
            return job.get('id') or job.get('@attributes', {}).get('id')
        return job
    
    # Result contains job
    if 'result' in data:
        result = data['result']
        if isinstance(result, dict):
            return result.get('job')
    
    return None


def is_job_complete(job_status):
    """
    Check if job status indicates completion
    
    Usage:
        {% if job_result | is_job_complete %}
    """
    if not job_status:
        return False
    
    status = str(job_status).upper()
    return status in ['FIN', 'COMPLETED', 'OK', 'DONE']


def is_job_success(job_result):
    """
    Check if job result indicates success
    
    Usage:
        {% if job_result | is_job_success %}
    """
    if not job_result:
        return False
    
    result = str(job_result).upper()
    return result in ['OK', 'SUCCESS', 'COMPLETED']


def dict_to_xml_cmd(cmd_dict, root_tag='show'):
    """
    Convert dictionary to XML command string
    
    Usage:
        {{ {'s': {'info': {}}} | dict_to_xml_cmd('show') }}
        -> '<show><s><info></info></s></show>'
    """
    def build_xml(data, parent_tag=None):
        if isinstance(data, dict):
            parts = []
            for key, value in data.items():
                inner = build_xml(value)
                parts.append(f"<{key}>{inner}</{key}>")
            return ''.join(parts)
        elif isinstance(data, list):
            return ''.join(build_xml(item) for item in data)
        elif data is None:
            return ''
        else:
            return str(data)
    
    inner = build_xml(cmd_dict)
    return f"<{root_tag}>{inner}</{root_tag}>"


def percent_to_float(percent_string):
    """
    Convert percentage string to float
    
    Example: '85%' -> 85.0, '85.5 %' -> 85.5
    """
    if isinstance(percent_string, (int, float)):
        return float(percent_string)
    
    if not percent_string:
        return 0.0
    
    match = re.search(r'([\d.]+)\s*%?', str(percent_string))
    if match:
        return float(match.group(1))
    
    return 0.0


def threshold_check(value, threshold, comparison='lt'):
    """
    Check value against threshold
    
    Usage:
        {{ cpu_percent | threshold_check(80, 'lt') }}  # True if cpu < 80
    """
    try:
        value = float(value)
        threshold = float(threshold)
    except (TypeError, ValueError):
        return False
    
    comparisons = {
        'lt': value < threshold,
        'le': value <= threshold,
        'gt': value > threshold,
        'ge': value >= threshold,
        'eq': value == threshold,
        'ne': value != threshold
    }
    
    return comparisons.get(comparison, False)


class FilterModule:
    """Ansible filter plugin for Palo Alto operations"""
    
    def filters(self):
        return {
            # Version filters
            'panos_version_compare': panos_version_compare,
            'panos_version_gte': panos_version_gte,
            'panos_version_lte': panos_version_lte,
            'panos_version_gt': panos_version_gt,
            'panos_version_lt': panos_version_lt,
            'panos_version_eq': panos_version_eq,
            'panos_major_minor': panos_major_minor,
            'panos_is_hotfix': panos_is_hotfix,
            'panos_normalize_version': panos_normalize_version,
            'parse_panos_version': parse_panos_version,
            
            # HA filters
            'ha_state_is_active': ha_state_is_active,
            'ha_state_is_passive': ha_state_is_passive,
            'ha_state_is_standalone': ha_state_is_standalone,
            
            # Formatting filters
            'format_bytes': format_bytes,
            'format_uptime': format_uptime,
            'uptime_minutes': uptime_minutes,
            'sanitize_filename': sanitize_filename,
            'timestamp_now': timestamp_now,
            'backup_filename': backup_filename,
            
            # Job filters
            'extract_job_id': extract_job_id,
            'is_job_complete': is_job_complete,
            'is_job_success': is_job_success,
            
            # Utility filters
            'dict_to_xml_cmd': dict_to_xml_cmd,
            'percent_to_float': percent_to_float,
            'threshold_check': threshold_check
        }
