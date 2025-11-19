// Configuration and Constants

// Settings management
const SETTINGS_KEY = 'smart_home_settings';
const DEFAULT_SETTINGS = {
    defaultCostPerKwh: 0.15,
    automationDuration: 30,
    minPowerThreshold: 5,
    defaultStartTime: '12:00',
    region: 'VIC1'
};

// Automation management
const AUTOMATION_STATE_KEY = 'smart_home_automations';

// Global state variables (will be initialized in main.js)
let autoRefreshInterval;
let isInitialLoad = true;
let timeseriesCollectionInterval = null;
let currentDevicesData = []; // Store current device data for timeseries collection
let appSettings; // Will be initialized from loadSettings()
let automationStates = {}; // deviceId -> { enabled, restartTime, deviceOnSince, turnedOffAt, powerThresholdMet }
let automationCheckInterval = null;

