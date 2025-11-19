// Timeseries Data Collection and Helper Functions

// In-memory timeseries storage (no persistence - cleared on page refresh)
// No localStorage caching - data starts fresh on each page load
let inMemoryTimeseriesData = {};
const MAX_CACHE_POINTS = 2880; // 24 hours * 60 minutes * 2 (30-second intervals)

// No-op: Server restart check not needed since we don't persist data
async function checkServerRestartAndClearCache() {
    // No-op - no cache to clear
}

// Load timeseries data from in-memory storage (always empty on page load)
function loadTimeseriesFromCache() {
    return inMemoryTimeseriesData;
}

// Save timeseries data to in-memory storage only (no persistence)
function saveTimeseriesToCache(timeseriesData) {
    // Limit cache size per device
    const limitedData = {};
    for (const [deviceId, deviceData] of Object.entries(timeseriesData)) {
        const data = deviceData.data || [];
        // Keep only the most recent MAX_CACHE_POINTS
        const limitedPoints = data.slice(-MAX_CACHE_POINTS);
        limitedData[deviceId] = {
            name: deviceData.name,
            data: limitedPoints
        };
    }
    inMemoryTimeseriesData = limitedData;
}

// Add data point to in-memory cache only (no persistence)
function addToTimeseriesCache(deviceId, deviceName, power, timestamp) {
    if (!inMemoryTimeseriesData[deviceId]) {
        inMemoryTimeseriesData[deviceId] = {
            name: deviceName,
            data: []
        };
    }
    
    inMemoryTimeseriesData[deviceId].name = deviceName; // Update name in case it changed
    inMemoryTimeseriesData[deviceId].data.push({
        timestamp: timestamp,
        power: power
    });
    
    // Limit size per device
    if (inMemoryTimeseriesData[deviceId].data.length > MAX_CACHE_POINTS) {
        inMemoryTimeseriesData[deviceId].data = inMemoryTimeseriesData[deviceId].data.slice(-MAX_CACHE_POINTS);
    }
}

// Helper function to format timestamp label based on interval
function formatTimestampLabel(date, intervalSeconds) {
    if (intervalSeconds <= 300) {
        // Short intervals (30s-5m): Show time with seconds
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    } else if (intervalSeconds <= 3600) {
        // Medium intervals (30m-1h): Show time without seconds
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    } else {
        // Long intervals (2h-24h): Show date and time
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    }
}

// Helper function to determine label interval (in 30-second steps)
function getLabelInterval(intervalSeconds) {
    if (intervalSeconds <= 300) {
        // 30s-5m: Show every 1-2 minutes (2-4 labels)
        return 2; // Every 2 × 30s = 1 minute
    } else if (intervalSeconds <= 1800) {
        // 30m: Show every 5 minutes
        return 10; // Every 10 × 30s = 5 minutes
    } else if (intervalSeconds <= 3600) {
        // 1h: Show every 5 minutes
        return 10; // Every 10 × 30s = 5 minutes
    } else if (intervalSeconds <= 7200) {
        // 2h: Show every 15 minutes
        return 30; // Every 30 × 30s = 15 minutes
    } else if (intervalSeconds <= 43200) {
        // 12h: Show every 30 minutes
        return 60; // Every 60 × 30s = 30 minutes
    } else {
        // 24h: Show every hour
        return 120; // Every 120 × 30s = 60 minutes
    }
}

// Helper function to determine max ticks limit
function getMaxTicksLimit(intervalSeconds) {
    if (intervalSeconds <= 300) {
        return 10; // 30s-5m: Max 10 labels
    } else if (intervalSeconds <= 1800) {
        return 12; // 30m: Max 12 labels (every 5 min = 6 labels)
    } else if (intervalSeconds <= 3600) {
        return 15; // 1h: Max 15 labels (every 5 min = 12 labels)
    } else if (intervalSeconds <= 7200) {
        return 10; // 2h: Max 10 labels (every 15 min = 8 labels)
    } else if (intervalSeconds <= 43200) {
        return 25; // 12h: Max 25 labels (every 30 min = 24 labels)
    } else {
        return 25; // 24h: Max 25 labels (every hour = 24 labels)
    }
}

// deviceColors is defined in charts.js

// Function to normalize timestamp to nearest 30-second bucket (00 or 30 seconds)
function normalizeTimestampTo30Sec(timestamp) {
    const date = new Date(timestamp);
    const seconds = date.getSeconds();

    // Round to nearest 30-second interval
    if (seconds < 15) {
        date.setSeconds(0);
    } else if (seconds < 45) {
        date.setSeconds(30);
    } else {
        date.setSeconds(0);
        date.setMinutes(date.getMinutes() + 1);
    }
    date.setMilliseconds(0);
    return date.toISOString();
}

// Function to initialize timeseries data from initial device power values
function initializeTimeseriesFromDevices(devicesData) {
    try {
        const timestamp = normalizeTimestampTo30Sec(new Date().toISOString());
        let devicesAdded = 0;
        
        // Combine all devices
        const allDevices = [];
        if (devicesData.tapo) {
            devicesData.tapo.forEach(device => allDevices.push({...device, deviceType: 'tapo'}));
        }
        if (devicesData.meross) {
            devicesData.meross.forEach(device => allDevices.push({...device, deviceType: 'meross'}));
        }
        if (devicesData.arlec) {
            devicesData.arlec.forEach(device => allDevices.push({...device, deviceType: 'arlec'}));
        }
        if (devicesData.matter) {
            devicesData.matter.forEach(device => allDevices.push({...device, deviceType: 'matter'}));
        }
        
        // Extract power data from devices and store in cache
        allDevices.forEach(device => {
            const deviceId = device.id || device.uuid;
            if (!deviceId) return;
            
            const power = device.power !== undefined ? device.power : (device.online && device.status === 'on' ? 0 : null);
            
            if (power !== null && power !== undefined) {
                addToTimeseriesCache(deviceId, device.name, round(power, 2), timestamp);
                devicesAdded++;
            }
        });
        
        if (devicesAdded > 0) {
            console.log(`[Timeseries] Initialized data for ${devicesAdded} device(s) at ${timestamp}`);
            return true;
        }
        return false;
    } catch (error) {
        console.error('Error initializing timeseries data:', error);
        return false;
    }
}

// Function to collect timeseries data from card values and store in browser cache
async function collectTimeseriesFromCards() {
    if (!currentDevicesData || currentDevicesData.length === 0) {
        return;
    }
    
    try {
        const timestamp = normalizeTimestampTo30Sec(new Date().toISOString());
        let devicesAdded = 0;
        
        // Extract power data from current device cards and store in cache
        currentDevicesData.forEach(device => {
            const deviceId = device.id || device.uuid;
            if (!deviceId) return;
            
            const power = device.power !== undefined ? device.power : (device.online && device.status === 'on' ? 0 : null);
            
            if (power !== null && power !== undefined) {
                addToTimeseriesCache(deviceId, device.name, round(power, 2), timestamp);
                devicesAdded++;
            }
        });
        
        if (devicesAdded > 0) {
            console.log(`[Timeseries] Cached data for ${devicesAdded} device(s) at ${timestamp}`);
            // Reload chart with new data
            loadTimeseriesData();
        }
    } catch (error) {
        console.error('Error collecting timeseries data:', error);
    }
}

// Helper function to round numbers
function round(value, decimals) {
    return Math.round(value * Math.pow(10, decimals)) / Math.pow(10, decimals);
}

// Calculate costs from cached timeseries data
function calculateCostsFromCache(powerChartData, intervalSeconds) {
    if (!powerChartData || !powerChartData.timestamps || !powerChartData.totalPower) {
        return [];
    }
    
    const costs = [];
    const pricePerKwh = appSettings.defaultCostPerKwh || 0.15;
    const forecastStartIndex = powerChartData.forecastStartIndex || powerChartData.timestamps.length;
    
    powerChartData.timestamps.forEach((ts, idx) => {
        const totalPower = powerChartData.totalPower[idx] || 0;
        
        // Calculate energy for this 30-second interval
        // Energy (kWh) = Power (W) × Time (hours) / 1000
        // 30 seconds = 0.5 minutes = 0.5/60 hours
        const energyKwh = (totalPower * 0.5) / (60.0 * 1000);
        
        // Calculate cost for this interval
        const cost = energyKwh * pricePerKwh;
        
        // Round to nearest 5-minute mark for aggregation
        const timestamp = new Date(ts);
        const minutes = timestamp.getMinutes();
        const roundedMinutes = Math.floor(minutes / 5) * 5;
        const roundedTime = new Date(timestamp);
        roundedTime.setMinutes(roundedMinutes, 0, 0);
        
        costs.push({
            timestamp: roundedTime.toISOString(),
            energy_kwh: round(energyKwh, 4),
            price: pricePerKwh,
            cost: round(cost, 4)
        });
    });
    
    // Aggregate to 5-minute intervals
    const aggregatedCosts = {};
    costs.forEach(point => {
        const key = point.timestamp;
        if (!aggregatedCosts[key]) {
            aggregatedCosts[key] = {
                timestamp: key,
                energy_kwh: 0,
                price: point.price,
                cost: 0
            };
        }
        aggregatedCosts[key].energy_kwh += point.energy_kwh;
        aggregatedCosts[key].cost += point.cost;
    });
    
    // Convert to array and sort
    return Object.values(aggregatedCosts)
        .map(item => ({
            timestamp: item.timestamp,
            energy_kwh: round(item.energy_kwh, 4),
            price: item.price,
            cost: round(item.cost, 4)
        }))
        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
}

// Function to calculate milliseconds until next 30-second mark (:00 or :30)
function getMsUntilNext30Second() {
    const now = new Date();
    const seconds = now.getSeconds();
    const milliseconds = now.getMilliseconds();
    
    // Calculate seconds until next 30-second mark
    let secondsUntilNext;
    if (seconds < 30) {
        secondsUntilNext = 30 - seconds;
    } else {
        secondsUntilNext = 60 - seconds;
    }
    
    // Convert to milliseconds and subtract current milliseconds
    return (secondsUntilNext * 1000) - milliseconds;
}

// Start timeseries collection synchronized to clock (:00 and :30 seconds)
function startTimeseriesCollection() {
    // Clear any existing interval
    if (timeseriesCollectionInterval) {
        clearInterval(timeseriesCollectionInterval);
    }
    
    // Calculate time until next 30-second mark
    const msUntilNext = getMsUntilNext30Second();
    
    // Wait until the next 30-second mark, then start collecting every 30 seconds
    setTimeout(() => {
        // Collect immediately
        collectTimeseriesFromCards();
        
        // Then collect every 30 seconds
        timeseriesCollectionInterval = setInterval(() => {
            collectTimeseriesFromCards();
        }, 30000);
    }, msUntilNext);
}

// Export timeseries data to CSV
async function exportTimeseriesToCSV() {
    try {
        // Load from browser cache
        const timeseries = loadTimeseriesFromCache();

        if (!timeseries || Object.keys(timeseries).length === 0) {
            alert('No timeseries data available to export');
            return;
        }

        // Prepare CSV data
        // Format: Timestamp, Device Name, Power (W)
        let csvContent = 'Timestamp,Device Name,Power (W)\n';

        // Collect all data points with device names
        const allDataPoints = [];
        for (const [uuid, deviceData] of Object.entries(timeseries)) {
            const deviceName = deviceData.name || 'Unknown Device';
            deviceData.data.forEach(point => {
                allDataPoints.push({
                    timestamp: point.timestamp,
                    deviceName: deviceName,
                    power: point.power !== null && point.power !== undefined ? point.power : 0
                });
            });
        }

        // Sort by timestamp
        allDataPoints.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        // Add rows to CSV
        allDataPoints.forEach(point => {
            // Format timestamp for CSV (ISO format is fine, but we can make it more readable)
            const date = new Date(point.timestamp);
            const formattedTimestamp = date.toISOString().replace('T', ' ').substring(0, 19);
            // Escape device name if it contains commas or quotes
            const escapedName = point.deviceName.includes(',') || point.deviceName.includes('"')
                ? `"${point.deviceName.replace(/"/g, '""')}"`
                : point.deviceName;
            csvContent += `${formattedTimestamp},${escapedName},${point.power}\n`;
        });

        // Create blob and download
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        
        // Generate filename with current date/time
        const now = new Date();
        const filename = `timeseries_export_${now.toISOString().replace(/[:.]/g, '-').substring(0, 19)}.csv`;
        
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } catch (error) {
        console.error('Error exporting to CSV:', error);
        alert('Error exporting data to CSV: ' + error.message);
    }
}

