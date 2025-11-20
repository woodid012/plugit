"""
30-Second Interval Buffer for Device Usage Data
Stores 30-second interval data and aggregates into 5-minute averages
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
import pytz

AEST = pytz.timezone('Australia/Sydney')

# Global buffer to store 30-second interval data
# Structure: {device_id: [{'timestamp': ..., 'power': ..., 'status': ..., ...}, ...]}
_interval_buffer: Dict[str, List[Dict[str, Any]]] = defaultdict(list)


def round_to_30_seconds(timestamp: datetime) -> datetime:
    """Round timestamp to nearest 30-second interval"""
    seconds = timestamp.second
    rounded_seconds = (seconds // 30) * 30
    return timestamp.replace(second=rounded_seconds, microsecond=0)


def round_to_5_minutes_end(timestamp: datetime) -> datetime:
    """
    Round timestamp to the END of the 5-minute interval
    e.g., 10:00:00-10:04:59 -> 10:05:00
    e.g., 10:05:00-10:09:59 -> 10:10:00
    """
    minutes = timestamp.minute
    seconds = timestamp.second
    
    # If we're exactly at a 5-minute mark with 0 seconds, that's already the end
    if minutes % 5 == 0 and seconds == 0:
        return timestamp.replace(second=0, microsecond=0)
    
    # Calculate next 5-minute mark
    rounded_minutes = ((minutes // 5) + 1) * 5
    
    # Handle hour rollover
    if rounded_minutes >= 60:
        rounded_minutes = 0
        rounded_hour = timestamp.hour + 1
        if rounded_hour >= 24:
            rounded_hour = 0
            # Handle day rollover (simplified - doesn't handle month/year boundaries)
            rounded_day = timestamp.day + 1
            try:
                return timestamp.replace(day=rounded_day, hour=rounded_hour, minute=rounded_minutes, second=0, microsecond=0)
            except ValueError:
                # Day doesn't exist (e.g., Feb 30), handle gracefully
                from datetime import timedelta
                return (timestamp + timedelta(days=1)).replace(hour=rounded_hour, minute=rounded_minutes, second=0, microsecond=0)
        return timestamp.replace(hour=rounded_hour, minute=rounded_minutes, second=0, microsecond=0)
    
    return timestamp.replace(minute=rounded_minutes, second=0, microsecond=0)


def add_30_second_interval(device_id: str, device_data: Dict[str, Any]) -> None:
    """
    Add a 30-second interval data point to the buffer
    
    Args:
        device_id: Device identifier
        device_data: Device data with timestamp, power, status, etc.
    """
    timestamp = datetime.now(AEST)
    rounded_timestamp = round_to_30_seconds(timestamp)
    
    interval_data = {
        'timestamp': rounded_timestamp.isoformat(),
        'power': device_data.get('power'),
        'voltage': device_data.get('voltage'),
        'current': device_data.get('current'),
        'status': device_data.get('status', 'unknown'),
        'online': device_data.get('online', False)
    }
    
    _interval_buffer[device_id].append(interval_data)
    
    # Keep only last 10 intervals (5 minutes worth)
    if len(_interval_buffer[device_id]) > 10:
        _interval_buffer[device_id] = _interval_buffer[device_id][-10:]


def aggregate_5_minute_intervals() -> List[Dict[str, Any]]:
    """
    Aggregate all buffered 30-second intervals into 5-minute averages
    Returns aggregated records ready for MongoDB storage
    
    Returns:
        List of aggregated device usage records
    """
    aggregated_records = []
    current_time = datetime.now(AEST)
    
    # Calculate the end timestamp for the current 5-minute period
    # e.g., if current time is 10:03:45, period_end = 10:05:00
    period_end = round_to_5_minutes_end(current_time)
    
    # Calculate period start (5 minutes before period_end)
    period_start = period_end - timedelta(minutes=5)
    
    for device_id, intervals in _interval_buffer.items():
        if not intervals:
            continue
        
        # Filter intervals within the current 5-minute period
        period_intervals = []
        for interval in intervals:
            interval_ts = datetime.fromisoformat(interval['timestamp'].replace('Z', '+00:00'))
            if interval_ts.tzinfo is None:
                interval_ts = AEST.localize(interval_ts)
            else:
                interval_ts = interval_ts.astimezone(AEST)
            
            # Include intervals from the period (period_start to period_end)
            if period_start <= interval_ts < period_end:
                period_intervals.append(interval)
        
        if not period_intervals:
            continue
        
        # Aggregate data
        power_values = [i['power'] for i in period_intervals if i.get('power') is not None]
        voltage_values = [i['voltage'] for i in period_intervals if i.get('voltage') is not None]
        current_values = [i['current'] for i in period_intervals if i.get('current') is not None]
        statuses = [i['status'] for i in period_intervals]
        online_statuses = [i.get('online', False) for i in period_intervals]
        
        # Calculate averages
        avg_power = sum(power_values) / len(power_values) if power_values else None
        avg_voltage = sum(voltage_values) / len(voltage_values) if voltage_values else None
        avg_current = sum(current_values) / len(current_values) if current_values else None
        
        # Determine final status (most common status in the period, or last status)
        final_status = statuses[-1] if statuses else 'unknown'
        final_online = any(online_statuses)  # Device is online if it was online at any point
        
        # Detect status changes
        status_changed = False
        status_change_type = None
        
        # Check if status changed during the period
        unique_statuses = list(set([s for s in statuses if s in ['on', 'off']]))
        if len(unique_statuses) > 1:
            status_changed = True
            # Determine change type
            first_status = None
            last_status = None
            for s in statuses:
                if s in ['on', 'off']:
                    if first_status is None:
                        first_status = s
                    last_status = s
            
            if first_status and last_status and first_status != last_status:
                if first_status == 'on' and last_status == 'off':
                    status_change_type = 'on_to_off'
                elif first_status == 'off' and last_status == 'on':
                    status_change_type = 'off_to_on'
        
        # Get device metadata from first interval (we'll need to pass this separately)
        # For now, we'll create a basic record structure
        aggregated_record = {
            'device_id': device_id,
            'timestamp': period_end.isoformat(),  # Report at END of interval
            'power': round(avg_power, 2) if avg_power is not None else None,
            'voltage': round(avg_voltage, 1) if avg_voltage is not None else None,
            'current': round(avg_current, 2) if avg_current is not None else None,
            'status': final_status,
            'online': final_online,
            'status_changed': status_changed,
            'status_change_type': status_change_type,
            'interval_count': len(period_intervals),
            'collected_at': current_time.isoformat()
        }
        
        aggregated_records.append(aggregated_record)
    
    # Clear processed intervals from buffer (keep only intervals after period_end)
    for device_id in list(_interval_buffer.keys()):
        remaining_intervals = []
        for interval in _interval_buffer[device_id]:
            interval_ts = datetime.fromisoformat(interval['timestamp'].replace('Z', '+00:00'))
            if interval_ts.tzinfo is None:
                interval_ts = AEST.localize(interval_ts)
            else:
                interval_ts = interval_ts.astimezone(AEST)
            
            # Keep intervals that are after the period_end (for next period)
            if interval_ts >= period_end:
                remaining_intervals.append(interval)
        
        if remaining_intervals:
            _interval_buffer[device_id] = remaining_intervals
        else:
            # Remove device from buffer if no remaining intervals
            del _interval_buffer[device_id]
    
    return aggregated_records


def clear_buffer() -> None:
    """Clear all buffered intervals"""
    _interval_buffer.clear()


def get_buffer_status() -> Dict[str, int]:
    """Get status of the buffer (number of intervals per device)"""
    return {device_id: len(intervals) for device_id, intervals in _interval_buffer.items()}

