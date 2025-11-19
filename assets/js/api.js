// API Communication Functions

// Cache key for device data
const DEVICE_CACHE_KEY = 'smart_home_devices_cache';
const DEVICE_CACHE_TIMESTAMP_KEY = 'smart_home_devices_cache_timestamp';
const CACHE_MAX_AGE = 5 * 60 * 1000; // 5 minutes

// Load cached device data
function loadCachedDevices() {
    try {
        const cached = localStorage.getItem(DEVICE_CACHE_KEY);
        const timestamp = localStorage.getItem(DEVICE_CACHE_TIMESTAMP_KEY);
        
        if (cached && timestamp) {
            const age = Date.now() - parseInt(timestamp);
            if (age < CACHE_MAX_AGE) {
                return JSON.parse(cached);
            }
        }
    } catch (e) {
        console.warn('Error loading cached devices:', e);
    }
    return null;
}

// Save device data to cache
function saveDevicesToCache(devices) {
    try {
        localStorage.setItem(DEVICE_CACHE_KEY, JSON.stringify(devices));
        localStorage.setItem(DEVICE_CACHE_TIMESTAMP_KEY, Date.now().toString());
    } catch (e) {
        console.warn('Error saving devices to cache:', e);
    }
}

async function loadDevices(showLoading = false) {
    const errorContainer = document.getElementById('error-container');
    const loading = document.getElementById('loading');
    const content = document.getElementById('content');

    // Try to load from cache first for instant display
    const cachedDevices = loadCachedDevices();
    if (cachedDevices && !showLoading) {
        // Render cached data immediately
        currentDevicesData = cachedDevices;
        if (typeof renderAllDevices === 'function') {
            renderAllDevices(cachedDevices);
        }
        if (typeof renderAutomationCards === 'function') {
            renderAutomationCards();
        }
        // Show content immediately
        loading.style.display = 'none';
        content.style.display = 'block';
    } else if (showLoading) {
        // Only show loading screen on initial load
        errorContainer.innerHTML = '';
        loading.style.display = 'block';
        content.style.display = 'none';
    }

    try {
        const response = await fetch('/api/devices');
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to load devices');
        }

        // Combine all devices and render in one grid
        const allDevices = [];
        
        // Add Tapo devices with type label
        (data.tapo || []).forEach(device => {
            allDevices.push({...device, deviceType: 'tapo'});
        });
        
        // Add Meross devices with type label
        (data.meross || []).forEach(device => {
            allDevices.push({...device, deviceType: 'meross'});
        });
        
        // Add Arlec devices with type label
        (data.arlec || []).forEach(device => {
            allDevices.push({...device, deviceType: 'arlec'});
        });
        
        // Add Matter devices with type label
        (data.matter || []).forEach(device => {
            allDevices.push({...device, deviceType: 'matter'});
        });
        
        // Store device data for timeseries collection
        currentDevicesData = allDevices;

        // Save to cache for next time
        saveDevicesToCache(allDevices);

        // Render all devices in one grid (update with fresh data)
        if (typeof renderAllDevices === 'function') {
            renderAllDevices(allDevices);
        }

        // Render automation cards
        if (typeof renderAutomationCards === 'function') {
            renderAutomationCards();
        }

        if (showLoading) {
            loading.style.display = 'none';
            content.style.display = 'block';
        }

        if (typeof updateLastUpdated === 'function') {
            updateLastUpdated();
        }

        return data;

    } catch (error) {
        console.error('Error loading devices:', error);
        // If we have cached data, keep showing it even on error
        if (!cachedDevices && showLoading) {
            errorContainer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
            loading.style.display = 'none';
        }
        throw error;
    }
}

// Make function available globally
window.loadDevices = loadDevices;

