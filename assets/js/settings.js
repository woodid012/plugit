// Settings Management

// Load settings from localStorage
function loadSettings() {
    try {
        const stored = localStorage.getItem(SETTINGS_KEY);
        if (stored) {
            return JSON.parse(stored);
        }
    } catch (e) {
        console.error('Error loading settings:', e);
    }
    return {...DEFAULT_SETTINGS};
}

// Save settings to localStorage
function saveSettingsToStorage(settings) {
    try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    } catch (e) {
        console.error('Error saving settings:', e);
    }
}

// Settings modal functions
function openSettings() {
    const modal = document.getElementById('settingsModal');
    const settings = loadSettings();
    
    document.getElementById('defaultCostPerKwh').value = settings.defaultCostPerKwh;
    document.getElementById('automationDuration').value = settings.automationDuration;
    document.getElementById('minPowerThreshold').value = settings.minPowerThreshold;
    document.getElementById('defaultStartTime').value = settings.defaultStartTime;
    document.getElementById('region').value = settings.region || 'VIC1';
    
    modal.classList.add('show');
}

function closeSettings() {
    const modal = document.getElementById('settingsModal');
    modal.classList.remove('show');
}

function saveSettings(event) {
    event.preventDefault();
    
    const oldRegion = appSettings?.region || 'VIC1';
    
    const newSettings = {
        defaultCostPerKwh: parseFloat(document.getElementById('defaultCostPerKwh').value),
        automationDuration: parseInt(document.getElementById('automationDuration').value),
        minPowerThreshold: parseFloat(document.getElementById('minPowerThreshold').value),
        defaultStartTime: document.getElementById('defaultStartTime').value,
        region: document.getElementById('region').value
    };
    
    saveSettingsToStorage(newSettings);
    appSettings = newSettings;
    
    closeSettings();
    
    // Reload charts to reflect new settings
    if (typeof powerChartTimestamps !== 'undefined' && powerChartTimestamps && powerChartTimestamps.length > 0) {
        // Reload all charts if region changed (cost chart uses price data, price chart needs region)
        if (oldRegion !== newSettings.region) {
            if (typeof loadCostData === 'function') {
                loadCostData();
            }
            if (typeof loadPriceData === 'function') {
                loadPriceData();
            }
            if (typeof loadStandalonePriceChart === 'function') {
                loadStandalonePriceChart();
            }
        } else {
            // Region didn't change, just reload cost data if needed
            if (typeof loadCostData === 'function') {
                loadCostData();
            }
        }
    }
    
    console.log('[Settings] Settings saved:', newSettings);
}

// Close modal when clicking outside
window.addEventListener('click', (event) => {
    const modal = document.getElementById('settingsModal');
    if (event.target === modal) {
        closeSettings();
    }
});

// Make functions available globally for inline handlers
window.openSettings = openSettings;
window.closeSettings = closeSettings;
window.saveSettings = saveSettings;

