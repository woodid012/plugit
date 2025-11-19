// Automation Management

// Load automation states from localStorage
function loadAutomationStates() {
    try {
        const stored = localStorage.getItem(AUTOMATION_STATE_KEY);
        if (stored) {
            automationStates = JSON.parse(stored);
        }
    } catch (e) {
        console.error('Error loading automation states:', e);
        automationStates = {};
    }
}

// Save automation states to localStorage
function saveAutomationStates() {
    try {
        localStorage.setItem(AUTOMATION_STATE_KEY, JSON.stringify(automationStates));
    } catch (e) {
        console.error('Error saving automation states:', e);
    }
}

// Get or initialize automation state for a device
function getAutomationState(deviceId) {
    if (!automationStates[deviceId]) {
        automationStates[deviceId] = {
            enabled: false,
            restartTime: appSettings.defaultStartTime || '12:00',
            deviceOnSince: null,
            turnedOffAt: null,
            powerThresholdMet: false,
            powerThresholdMetAt: null,
            lastMessage: ''
        };
    }
    return automationStates[deviceId];
}

// Toggle automation for a device
function toggleAutomation(deviceId, enabled) {
    const state = getAutomationState(deviceId);
    state.enabled = enabled;
    state.deviceOnSince = null;
    state.turnedOffAt = null;
    state.powerThresholdMet = false;
    state.powerThresholdMetAt = null;
    state.lastMessage = '';
    saveAutomationStates();
    renderAutomationCards();
}

// Show save button when time is changed
function onTimeInputChange(deviceId) {
    const timeInput = document.getElementById(`time-input-${deviceId}`);
    const saveBtn = document.getElementById(`save-btn-${deviceId}`);
    const originalTime = timeInput.getAttribute('data-original-time');
    
    if (timeInput && saveBtn) {
        if (timeInput.value !== originalTime) {
            saveBtn.style.display = 'block';
        } else {
            saveBtn.style.display = 'none';
        }
    }
}

// Save restart time for a device
function saveRestartTime(deviceId) {
    const timeInput = document.getElementById(`time-input-${deviceId}`);
    const saveBtn = document.getElementById(`save-btn-${deviceId}`);
    
    if (!timeInput) return;
    
    const time = timeInput.value;
    const state = getAutomationState(deviceId);
    state.restartTime = time;
    saveAutomationStates();
    
    // Update the original time attribute
    timeInput.setAttribute('data-original-time', time);
    
    // Hide save button
    if (saveBtn) {
        saveBtn.style.display = 'none';
    }
    
    // Update the status text
    const container = document.getElementById('automations-grid');
    if (container) {
        const cards = container.querySelectorAll('.automation-card');
        cards.forEach(card => {
            const cardTimeInput = card.querySelector(`#time-input-${deviceId}`);
            if (cardTimeInput) {
                const statusDiv = card.querySelector('.automation-status');
                if (statusDiv) {
                    const automationDuration = appSettings.automationDuration || 30;
                    const minPowerThreshold = appSettings.minPowerThreshold || 5;
                    
                    if (state.enabled) {
                        if (state.turnedOffAt) {
                            statusDiv.textContent = `Standby until ${state.restartTime}`;
                        } else if (!state.lastMessage) {
                            statusDiv.textContent = `Monitoring - Will turn off after ${automationDuration}s with power > ${minPowerThreshold}W, restart at ${state.restartTime}`;
                        }
                        // Keep lastMessage if it exists
                    } else {
                        statusDiv.textContent = `Will turn device on at ${state.restartTime}, then off after ${automationDuration}s with power > ${minPowerThreshold}W`;
                    }
                }
            }
        });
    }
}

// Render automation cards
function renderAutomationCards() {
    const container = document.getElementById('automations-grid');
    if (!container) {
        console.warn('Automations container not found');
        return;
    }
    
    if (!currentDevicesData || currentDevicesData.length === 0) {
        container.innerHTML = '<div class="no-devices">No devices available for automation</div>';
        return;
    }

    container.innerHTML = currentDevicesData.map(device => {
        const deviceId = device.id || device.uuid;
        const state = getAutomationState(deviceId);

        const automationDuration = appSettings.automationDuration || 30;
        const minPowerThreshold = appSettings.minPowerThreshold || 5;
        
        let statusText = '';
        let statusClass = '';

        if (state.enabled) {
            if (state.lastMessage) {
                statusText = state.lastMessage;
                statusClass = 'active';
            } else if (state.turnedOffAt) {
                statusText = `Standby until ${state.restartTime}`;
                statusClass = 'active';
            } else {
                statusText = `Monitoring - Will turn off after ${automationDuration}s with power > ${minPowerThreshold}W, restart at ${state.restartTime}`;
                statusClass = 'active';
            }
        } else {
            statusText = `Will turn device on at ${state.restartTime}, then off after ${automationDuration}s with power > ${minPowerThreshold}W`;
            statusClass = '';
        }

        return `
            <div class="automation-card">
                <div class="automation-header">
                    <div class="automation-title">${device.name}</div>
                    <label class="automation-toggle">
                        <input type="checkbox"
                               ${state.enabled ? 'checked' : ''}
                               onchange="toggleAutomation('${deviceId}', this.checked)">
                        <span class="automation-slider"></span>
                    </label>
                </div>
                <div class="automation-status ${statusClass}">
                    ${statusText}
                </div>
                <div class="automation-settings visible">
                    <div class="automation-time-picker">
                        <label>Restart at:</label>
                        <input type="time"
                               id="time-input-${deviceId}"
                               value="${state.restartTime}"
                               data-original-time="${state.restartTime}"
                               onchange="onTimeInputChange('${deviceId}')">
                        <button class="save-time-btn"
                                onclick="saveRestartTime('${deviceId}')"
                                id="save-btn-${deviceId}"
                                style="display: none;">
                            Save
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Check automations and perform actions
async function checkAutomations() {
    if (!currentDevicesData || currentDevicesData.length === 0) return;

    const now = new Date();
    const currentTime = now.getHours() * 60 + now.getMinutes(); // minutes since midnight

    for (const device of currentDevicesData) {
        const deviceId = device.id || device.uuid;
        const state = getAutomationState(deviceId);

        if (!state.enabled) continue;

        const isDeviceOn = device.online && device.status === 'on';

        // Check if it's time to restart the device
        if (state.turnedOffAt) {
            const [hours, minutes] = state.restartTime.split(':').map(Number);
            const restartTime = hours * 60 + minutes;

            if (currentTime >= restartTime && currentTime < restartTime + 1) {
                // Time to restart - turn device back on
                console.log(`[Automation] Restarting ${device.name} at ${state.restartTime}`);

                try {
                    // Store the turn-off time before clearing it
                    const turnedOffAt = state.turnedOffAt;
                    const turnedOffTime = turnedOffAt ? new Date(turnedOffAt).toLocaleTimeString() : 'Unknown';
                    const turnedOnTime = now.toLocaleTimeString();

                    // Turn device on based on type
                    if (device.deviceType === 'tapo') {
                        await controlTapo(deviceId, 'on');
                    } else if (device.deviceType === 'meross') {
                        await controlMeross(deviceId, 'on');
                    } else if (device.deviceType === 'arlec') {
                        await controlArlec(deviceId, 'on');
                    } else if (device.deviceType === 'matter') {
                        await controlMatter(deviceId, 'on');
                    }

                    // Toggle automation off and set message with both times
                    state.enabled = false;
                    state.turnedOffAt = null;
                    state.deviceOnSince = null;
                    state.lastMessage = `Turned off at ${turnedOffTime}, turned back on at ${turnedOnTime}. Automation disabled.`;
                    saveAutomationStates();
                    renderAutomationCards(); // Update UI to show automation is off
                } catch (error) {
                    console.error(`[Automation] Error restarting ${device.name}:`, error);
                }
            }
        }
        // Check if device has been on for the configured duration AND meets power threshold
        else if (isDeviceOn) {
            const automationDuration = appSettings.automationDuration || 30;
            const minPowerThreshold = appSettings.minPowerThreshold || 5;
            const devicePower = device.power !== undefined && device.power !== null ? device.power : 0;

            if (!state.deviceOnSince) {
                // Device just turned on - start tracking
                state.deviceOnSince = Date.now();
                state.powerThresholdMet = false;
                saveAutomationStates();
            } else {
                const secondsOn = (Date.now() - state.deviceOnSince) / 1000;

                // Check if power threshold is met
                if (devicePower > minPowerThreshold) {
                    if (!state.powerThresholdMet) {
                        // Power threshold just met - mark it
                        state.powerThresholdMet = true;
                        state.powerThresholdMetAt = Date.now();
                        saveAutomationStates();
                    }
                } else {
                    // Power dropped below threshold - reset
                    if (state.powerThresholdMet) {
                        state.powerThresholdMet = false;
                        state.powerThresholdMetAt = null;
                        saveAutomationStates();
                    }
                }

                // Check if device has been on for the duration AND power threshold has been met for the duration
                const powerThresholdMetDuration = state.powerThresholdMet && state.powerThresholdMetAt
                    ? (Date.now() - state.powerThresholdMetAt) / 1000
                    : 0;

                if (secondsOn >= automationDuration && powerThresholdMetDuration >= automationDuration) {
                    // Turn device off
                    const turnOffTime = now.toLocaleTimeString();
                    console.log(`[Automation] Turning off ${device.name} after ${automationDuration}s with power > ${minPowerThreshold}W`);

                    try {
                        // Turn device off based on type
                        if (device.deviceType === 'tapo') {
                            await controlTapo(deviceId, 'off');
                        } else if (device.deviceType === 'meross') {
                            await controlMeross(deviceId, 'off');
                        } else if (device.deviceType === 'arlec') {
                            await controlArlec(deviceId, 'off');
                        } else if (device.deviceType === 'matter') {
                            await controlMatter(deviceId, 'off');
                        }

                        state.deviceOnSince = null;
                        state.powerThresholdMet = false;
                        state.powerThresholdMetAt = null;
                        state.turnedOffAt = Date.now();
                        state.lastMessage = `Turned off at ${turnOffTime}, turning back on at ${state.restartTime}`;
                        saveAutomationStates();
                    } catch (error) {
                        console.error(`[Automation] Error turning off ${device.name}:`, error);
                    }
                }
            }
        } else {
            // Device is off - reset tracking
            if (state.deviceOnSince && !state.turnedOffAt) {
                state.deviceOnSince = null;
                state.powerThresholdMet = false;
                state.powerThresholdMetAt = null;
                saveAutomationStates();
            }
        }
    }

    // Update UI
    renderAutomationCards();
}

// Start automation monitoring
function startAutomationMonitoring() {
    if (automationCheckInterval) {
        clearInterval(automationCheckInterval);
    }

    // Check every 1 second for responsive automation
    automationCheckInterval = setInterval(checkAutomations, 1000);
}

// Make functions available globally for inline handlers
window.loadAutomationStates = loadAutomationStates;
window.toggleAutomation = toggleAutomation;
window.onTimeInputChange = onTimeInputChange;
window.saveRestartTime = saveRestartTime;
window.renderAutomationCards = renderAutomationCards;
window.startAutomationMonitoring = startAutomationMonitoring;

