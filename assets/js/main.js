// Main Initialization and Event Handlers

// Initialize settings from localStorage
appSettings = loadSettings();

// Update last updated timestamp
function updateLastUpdated() {
    const lastUpdated = document.getElementById('last-updated');
    const now = new Date();
    lastUpdated.textContent = `Last updated: ${now.toLocaleTimeString()}`;
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

// Load devices on page load
window.addEventListener('load', async () => {
    // Check if server restarted and clear cache if needed (MUST be first)
    await checkServerRestartAndClearCache();

    // Load automation states from localStorage
    loadAutomationStates();

    // Try to load cached devices first for instant display
    const cachedDevices = loadCachedDevices();
    if (cachedDevices) {
        // Render cached devices immediately
        const allDevices = cachedDevices;
        currentDevicesData = allDevices;
        
        // Render all devices
        renderAllDevices(allDevices);
        
        // Render automation cards
        renderAutomationCards();
        
        // Hide loading, show content immediately
        document.getElementById('loading').style.display = 'none';
        document.getElementById('content').style.display = 'block';
        updateLastUpdated();
    }

    // Load fresh data from server
    // Load devices first, then pass the data to timeseries to avoid duplicate fetch
    const devicesResponse = await fetch('/api/devices');
    const devicesData = await devicesResponse.json();

    if (devicesData.success) {
        // Combine all devices and render
        const allDevices = [];

        (devicesData.tapo || []).forEach(device => {
            allDevices.push({...device, deviceType: 'tapo'});
        });

        (devicesData.meross || []).forEach(device => {
            allDevices.push({...device, deviceType: 'meross'});
        });

        (devicesData.arlec || []).forEach(device => {
            allDevices.push({...device, deviceType: 'arlec'});
        });

        // Store device data for timeseries collection
        currentDevicesData = allDevices;

        // Save to cache for next time
        saveDevicesToCache(allDevices);

        // Render all devices (update with fresh data)
        renderAllDevices(allDevices);

        // Render automation cards
        renderAutomationCards();

        // Hide loading, show content (if not already shown)
        if (document.getElementById('loading').style.display !== 'none') {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('content').style.display = 'block';
        }
        updateLastUpdated();

        // Initialize timeseries data from initial device power values
        initializeTimeseriesFromDevices(devicesData);
        
        // Load timeseries charts with the device data we already have
        loadTimeseriesData(devicesData);
    } else {
        // Error handling
        document.getElementById('error-container').innerHTML =
            `<div class="error">Error: ${devicesData.error || 'Failed to load devices'}</div>`;
        document.getElementById('loading').style.display = 'none';
    }

    // Start timeseries collection from card values (synchronized to clock)
    startTimeseriesCollection();

    // Start automation monitoring
    startAutomationMonitoring();

    // Auto-refresh every 30 seconds (smooth updates, no loading screen)
    autoRefreshInterval = setInterval(() => {
        loadDevices(false);
    }, 30000);
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    if (timeseriesCollectionInterval) {
        clearInterval(timeseriesCollectionInterval);
    }
});

