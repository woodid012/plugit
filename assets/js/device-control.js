// Device Control Functions

// Track pending status updates (deviceId -> { timeoutId, action, timestamp })
const pendingStatusUpdates = {};

function getDeviceKey(deviceId, deviceType) {
    return `${deviceType}_${deviceId}`;
}

function renderAllDevices(devices) {
    const container = document.getElementById('all-devices');
    const group = document.querySelector('.device-group');

    if (devices.length === 0) {
        container.innerHTML = '<div class="no-devices">No devices found</div>';
        return;
    }

    group.style.display = 'block';
    container.innerHTML = devices.map(device => {
        // Build energy info string if available
        let energyInfo = '';
        if (device.power !== undefined) {
            energyInfo = `<br><strong>⚡ Power:</strong> ${device.power.toFixed(1)} W`;
            if (device.current !== undefined) {
                energyInfo += `<br><strong>🔌 Current:</strong> ${device.current.toFixed(2)} A`;
            }
            if (device.voltage !== undefined) {
                energyInfo += `<br><strong>⚙️ Voltage:</strong> ${device.voltage.toFixed(1)} V`;
            }
        }
        
        // Determine device type badge
        const deviceType = device.deviceType || 'tapo';
        const typeBadgeClass = `device-type-${deviceType}`;
        const typeLabel = deviceType.toUpperCase();
        
        // Determine control function based on device type
        let onControl = '';
        let offControl = '';
        let toggleControl = '';
        
        if (deviceType === 'tapo') {
            onControl = `controlTapo('${device.id}', 'on')`;
            offControl = `controlTapo('${device.id}', 'off')`;
        } else if (deviceType === 'meross') {
            onControl = `controlMeross('${device.uuid}', 'on')`;
            offControl = `controlMeross('${device.uuid}', 'off')`;
            toggleControl = `controlMeross('${device.uuid}', 'toggle')`;
        } else if (deviceType === 'arlec') {
            onControl = `controlArlec('${device.uuid}', 'on')`;
            offControl = `controlArlec('${device.uuid}', 'off')`;
            toggleControl = `controlArlec('${device.uuid}', 'toggle')`;
        } else if (deviceType === 'matter') {
            const deviceId = device.id || device.uuid;
            onControl = `controlMatter('${deviceId}', 'on')`;
            offControl = `controlMatter('${deviceId}', 'off')`;
            toggleControl = `controlMatter('${deviceId}', 'toggle')`;
        }
        
        return `
        <div class="device-card ${device.online ? 'online' : 'offline'}">
            <div style="margin-bottom: 10px;">
                <span class="device-type-badge ${typeBadgeClass}">${typeLabel}</span>
            </div>
            <div class="device-header">
                <div class="device-name">${device.name}</div>
                <span class="status-badge ${
                    !device.online ? 'status-offline' :
                    device.status === 'on' ? 'status-on' : 'status-off'
                }">
                    ${!device.online ? 'Offline' : device.status.toUpperCase()}
                </span>
            </div>
            <div class="device-info">
                ${device.type}${energyInfo}
            </div>
            <div class="device-controls">
                <button class="control-btn btn-on ${device.online && device.status === 'on' ? 'btn-greyed' : ''}"
                        onclick="${onControl}"
                        ${!device.online || device.status === 'on' ? 'disabled' : ''}>
                    ON
                </button>
                <button class="control-btn btn-off ${device.online && device.status === 'off' ? 'btn-greyed' : ''}"
                        onclick="${offControl}"
                        ${!device.online || device.status === 'off' ? 'disabled' : ''}>
                    OFF
                </button>
            </div>
        </div>
    `;
    }).join('');
}

// Optimistically update device status in the UI before server confirms
function updateDeviceStatusOptimistically(deviceId, action, deviceType) {
    // Find the device in currentDevicesData
    const device = currentDevicesData.find(d => {
        if (deviceType === 'tapo') {
            return d.id === deviceId;
        } else if (deviceType === 'matter') {
            return (d.id === deviceId) || (d.uuid === deviceId);
        } else {
            return d.uuid === deviceId;
        }
    });
    
    if (device) {
        // Update the status optimistically
        if (action === 'on') {
            device.status = 'on';
        } else if (action === 'off') {
            device.status = 'off';
        } else if (action === 'toggle') {
            device.status = device.status === 'on' ? 'off' : 'on';
        }
        
        // Immediately re-render the cards with updated status
        renderAllDevices(currentDevicesData);
    }
}

async function controlTapo(deviceId, action) {
    const deviceKey = getDeviceKey(deviceId, 'tapo');
    
    // Clear any existing timeout for this device
    if (pendingStatusUpdates[deviceKey]) {
        clearTimeout(pendingStatusUpdates[deviceKey].timeoutId);
    }
    
    // Optimistically update the UI immediately
    updateDeviceStatusOptimistically(deviceId, action, 'tapo');
    
    try {
        const response = await fetch(`/api/tapo/${deviceId}/${action}`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            // Set timeout to refresh after 10 seconds
            const timeoutId = setTimeout(() => {
                loadDevices(false);
                delete pendingStatusUpdates[deviceKey];
            }, 10000);
            
            // Track this pending update
            pendingStatusUpdates[deviceKey] = {
                timeoutId: timeoutId,
                action: action,
                timestamp: Date.now()
            };
        } else {
            // Revert optimistic update on error
            loadDevices(false);
            delete pendingStatusUpdates[deviceKey];
            alert(`Error: ${data.error}`);
        }
    } catch (error) {
        // Revert optimistic update on error
        loadDevices(false);
        delete pendingStatusUpdates[deviceKey];
        console.error('Error controlling Tapo device:', error);
        alert(`Error: ${error.message}`);
    }
}

async function controlMeross(uuid, action) {
    const deviceKey = getDeviceKey(uuid, 'meross');
    
    // Clear any existing timeout for this device
    if (pendingStatusUpdates[deviceKey]) {
        clearTimeout(pendingStatusUpdates[deviceKey].timeoutId);
    }
    
    // Optimistically update the UI immediately
    updateDeviceStatusOptimistically(uuid, action, 'meross');
    
    try {
        const response = await fetch(`/api/meross/${uuid}/${action}`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            // Set timeout to refresh after 10 seconds
            const timeoutId = setTimeout(() => {
                loadDevices(false);
                delete pendingStatusUpdates[deviceKey];
            }, 10000);
            
            // Track this pending update
            pendingStatusUpdates[deviceKey] = {
                timeoutId: timeoutId,
                action: action,
                timestamp: Date.now()
            };
        } else {
            // Revert optimistic update on error
            loadDevices(false);
            delete pendingStatusUpdates[deviceKey];
            alert(`Error: ${data.error}`);
        }
    } catch (error) {
        // Revert optimistic update on error
        loadDevices(false);
        delete pendingStatusUpdates[deviceKey];
        console.error('Error controlling Meross device:', error);
        alert(`Error: ${error.message}`);
    }
}

async function controlArlec(uuid, action) {
    const deviceKey = getDeviceKey(uuid, 'arlec');
    
    // Clear any existing timeout for this device
    if (pendingStatusUpdates[deviceKey]) {
        clearTimeout(pendingStatusUpdates[deviceKey].timeoutId);
    }
    
    // Optimistically update the UI immediately
    updateDeviceStatusOptimistically(uuid, action, 'arlec');
    
    try {
        const response = await fetch(`/api/arlec/${uuid}/${action}`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            // Set timeout to refresh after 10 seconds
            const timeoutId = setTimeout(() => {
                loadDevices(false);
                delete pendingStatusUpdates[deviceKey];
            }, 10000);
            
            // Track this pending update
            pendingStatusUpdates[deviceKey] = {
                timeoutId: timeoutId,
                action: action,
                timestamp: Date.now()
            };
        } else {
            // Revert optimistic update on error
            loadDevices(false);
            delete pendingStatusUpdates[deviceKey];
            alert(`Error: ${data.error}`);
        }
    } catch (error) {
        // Revert optimistic update on error
        loadDevices(false);
        delete pendingStatusUpdates[deviceKey];
        console.error('Error controlling Arlec device:', error);
        alert(`Error: ${error.message}`);
    }
}

async function controlMatter(deviceId, action) {
    const deviceKey = getDeviceKey(deviceId, 'matter');
    
    // Clear any existing timeout for this device
    if (pendingStatusUpdates[deviceKey]) {
        clearTimeout(pendingStatusUpdates[deviceKey].timeoutId);
    }
    
    // Optimistically update the UI immediately
    updateDeviceStatusOptimistically(deviceId, action, 'matter');
    
    try {
        const response = await fetch(`/api/matter/${deviceId}/${action}`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            // Set timeout to refresh after 10 seconds
            const timeoutId = setTimeout(() => {
                loadDevices(false);
                delete pendingStatusUpdates[deviceKey];
            }, 10000);
            
            // Track this pending update
            pendingStatusUpdates[deviceKey] = {
                timeoutId: timeoutId,
                action: action,
                timestamp: Date.now()
            };
        } else {
            // Revert optimistic update on error
            loadDevices(false);
            delete pendingStatusUpdates[deviceKey];
            alert(`Error: ${data.error}`);
        }
    } catch (error) {
        // Revert optimistic update on error
        loadDevices(false);
        delete pendingStatusUpdates[deviceKey];
        console.error('Error controlling Matter device:', error);
        alert(`Error: ${error.message}`);
    }
}

function updateLastUpdated() {
    const lastUpdated = document.getElementById('last-updated');
    const now = new Date();
    lastUpdated.textContent = `Last updated: ${now.toLocaleTimeString()}`;
}

// Make functions available globally for inline handlers
window.renderAllDevices = renderAllDevices;
window.controlTapo = controlTapo;
window.controlMeross = controlMeross;
window.controlArlec = controlArlec;
window.controlMatter = controlMatter;
window.updateLastUpdated = updateLastUpdated;

