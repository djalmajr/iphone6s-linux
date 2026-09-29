#!/bin/sh
set -eu

# Read sysfs only. Sensor presence does not establish safe charging.
sysfs_root=${1:-/sys}
printf 'charging_validation=unverified\n'
supply_count=0
for device in "$sysfs_root"/class/power_supply/*; do
    [ -d "$device" ] || continue
    supply_count=$((supply_count + 1))
    printf 'power_supply=%s\n' "${device##*/}"
    for field in type status online capacity voltage_now current_now temp; do
        if [ -f "$device/$field" ] && [ -r "$device/$field" ]; then
            value=$(cat "$device/$field" 2>/dev/null) || value=unavailable
            [ -n "$value" ] || value=unavailable
        else
            value=unavailable
        fi
        printf '%s=%s\n' "$field" "$value"
    done
done
[ "$supply_count" -gt 0 ] || printf 'power_supply=unavailable\n'

thermal_count=0
for zone in "$sysfs_root"/class/thermal/thermal_zone*; do
    [ -d "$zone" ] || continue
    thermal_count=$((thermal_count + 1))
    printf 'thermal_zone=%s\n' "${zone##*/}"
    for field in type temp; do
        if [ -f "$zone/$field" ] && [ -r "$zone/$field" ]; then
            value=$(cat "$zone/$field" 2>/dev/null) || value=unavailable
            [ -n "$value" ] || value=unavailable
        else
            value=unavailable
        fi
        printf '%s=%s\n' "$field" "$value"
    done
done
[ "$thermal_count" -gt 0 ] || printf 'thermal_zone=unavailable\n'
