// Chart Management and Rendering Functions

// Chart management
let powerChart = null;
let costChart = null;
let priceChart = null;
let standalonePriceChart = null;
let powerChartTimestamps = []; // Store power chart timestamps for cost chart alignment
let powerChartLabels = []; // Store power chart labels for cost chart alignment
let powerChartForecastStartIndex = 0; // Store forecast start index
let powerChartData = null; // Store power chart data for cost calculation

// Generate distinct colors for each device
const deviceColors = [
    'rgba(102, 126, 234, 0.8)',  // Purple
    'rgba(245, 87, 108, 0.8)',   // Pink
    'rgba(76, 175, 80, 0.8)',    // Green
    'rgba(255, 193, 7, 0.8)',    // Yellow
    'rgba(33, 150, 243, 0.8)',   // Blue
    'rgba(255, 87, 34, 0.8)',    // Orange
];

async function loadTimeseriesData(providedDevicesData = null) {
    try {
        // Show loading state for chart immediately
        const chartSection = document.getElementById('chart-section');
        if (chartSection && chartSection.style.display !== 'none') {
            const chartWrapper = document.querySelector('.chart-wrapper');
            if (chartWrapper && !chartWrapper.querySelector('.loading-chart')) {
                const loadingDiv = document.createElement('div');
                loadingDiv.className = 'loading-chart';
                loadingDiv.style.cssText = 'text-align: center; padding: 20px; color: #666;';
                loadingDiv.textContent = 'Loading chart data...';
                chartWrapper.appendChild(loadingDiv);
            }
        }
        
        // Load from browser cache instead of server
        const cachedTimeseries = loadTimeseriesFromCache();
        
        // Get device info if not provided
        let devicesData = providedDevicesData;
        if (!devicesData) {
            const devicesResp = await fetch('/api/devices');
            devicesData = await devicesResp.json();
        }
        
        // Format cached data to match expected structure
        const data = {
            success: true,
            timeseries: cachedTimeseries
        };

        // Remove loading indicator
        const loadingDiv = document.querySelector('.loading-chart');
        if (loadingDiv) {
            loadingDiv.remove();
        }

        if (!data.success) {
            console.error('Failed to load timeseries data:', data.error);
            return;
        }

        const timeseries = data.timeseries;

        // Create a mapping of device UUIDs/IDs to current device names from cards
        const deviceNameMap = {};

        // Map Tapo devices (use device_id as key)
        if (devicesData.tapo) {
            devicesData.tapo.forEach(device => {
                if (device.id) {
                    deviceNameMap[device.id] = device.name;
                }
            });
        }

        // Map Meross devices (use uuid as key)
        if (devicesData.meross) {
            devicesData.meross.forEach(device => {
                if (device.uuid) {
                    deviceNameMap[device.uuid] = device.name;
                }
            });
        }

        // Map Arlec devices (use uuid as key)
        if (devicesData.arlec) {
            devicesData.arlec.forEach(device => {
                if (device.uuid) {
                    deviceNameMap[device.uuid] = device.name;
                }
            });
        }

        // Check if we have any data
        if (Object.keys(timeseries).length === 0) {
            document.getElementById('chart-section').style.display = 'none';
            return;
        }

        // Show chart section
        document.getElementById('chart-section').style.display = 'block';

        // Prepare chart data
        const deviceUuids = Object.keys(timeseries);
        const bucketedTimestamps = new Set();

        // Normalize and collect all timestamps into 30-second buckets
        deviceUuids.forEach(uuid => {
            timeseries[uuid].data.forEach(point => {
                const normalizedTs = normalizeTimestampTo30Sec(point.timestamp);
                bucketedTimestamps.add(normalizedTs);
            });
        });

        // Sort timestamps
        const sortedTimestamps = Array.from(bucketedTimestamps).sort();

        // Calculate forecast: average of last 30 minutes per device
        // If power drops to below 5% of previous average (last 3 periods), use that lower amount
        // Exclude devices that have been off for 3 periods (90 seconds)
        const forecastAverages = {};
        const devicesToExcludeFromForecast = new Set();
        const now = new Date();
        const thirtyMinutesAgo = new Date(now.getTime() - 30 * 60 * 1000);

        deviceUuids.forEach(uuid => {
            const deviceData = timeseries[uuid];
            
            // Get the last 4 data points (most recent first)
            const sortedData = [...deviceData.data].sort((a, b) => 
                new Date(b.timestamp) - new Date(a.timestamp)
            );
            const last4Points = sortedData.slice(0, 4);
            
            // If device has 3 or more data points and all last 3 are 0 (off), exclude from forecast
            if (last4Points.length >= 3) {
                const last3Points = last4Points.slice(0, 3);
                const allOff = last3Points.every(point => point.power === 0 || point.power === null);
                if (allOff) {
                    devicesToExcludeFromForecast.add(uuid);
                    forecastAverages[uuid] = null; // Mark as excluded
                    return; // Skip forecast calculation for this device
                }
            }
            
            // Check if power increased: if last 4 periods average > 5% of previous average, maintain new higher average
            if (last4Points.length >= 4 && sortedData.length >= 8) {
                // Get the 4 periods before the last 4 (previous average baseline)
                const previous4Points = sortedData.slice(4, 8);
                const previousAverage = previous4Points.length > 0
                    ? previous4Points.reduce((sum, p) => sum + (p.power || 0), 0) / previous4Points.length
                    : 0;
                
                // Calculate average of last 4 periods (recent average)
                const averageOfLast4 = last4Points.reduce((sum, p) => sum + (p.power || 0), 0) / 4;
                
                // If last 4 periods average is more than 5% above the previous average, maintain the new higher average
                if (previousAverage > 0 && averageOfLast4 > (previousAverage * 1.05)) {
                    // Use the average of the last 4 periods to maintain the new higher level
                    forecastAverages[uuid] = averageOfLast4;
                    return; // Use the new higher average for forecast, ignoring previous lower values
                }
            }
            
            // Get data points from last 30 minutes
            const recentData = deviceData.data.filter(point => {
                const pointTime = new Date(point.timestamp);
                return pointTime >= thirtyMinutesAgo;
            });

            if (recentData.length > 0) {
                // Simple average (no weighting)
                const sum = recentData.reduce((acc, point) => acc + point.power, 0);
                forecastAverages[uuid] = sum / recentData.length;
            } else {
                // If no recent data, use overall average
                const allPowers = deviceData.data.map(p => p.power).filter(p => p > 0);
                forecastAverages[uuid] = allPowers.length > 0 
                    ? allPowers.reduce((a, b) => a + b, 0) / allPowers.length 
                    : 0;
            }
        });

        // Generate forecast timestamps (next 30 minutes, 60 points at 30-second intervals)
        const forecastTimestamps = [];
        const lastTimestamp = sortedTimestamps.length > 0 
            ? new Date(sortedTimestamps[sortedTimestamps.length - 1])
            : now;
        
        for (let i = 1; i <= 60; i++) {
            const forecastTime = new Date(lastTimestamp.getTime() + i * 30 * 1000);
            forecastTimestamps.push(normalizeTimestampTo30Sec(forecastTime.toISOString()));
        }

        // Combine historical and forecast timestamps
        const allTimestamps = [...sortedTimestamps, ...forecastTimestamps].sort();
        const forecastStartIndex = sortedTimestamps.length;

        // Pre-build data maps for all devices (reuse for chart and cost calculation)
        const deviceDataMapsForChart = {};
        deviceUuids.forEach((uuid) => {
            const deviceData = timeseries[uuid];
            const dataMap = {};

            // Create a map of normalized timestamp -> power for historical data
            deviceData.data.forEach(point => {
                const normalizedTs = normalizeTimestampTo30Sec(point.timestamp);
                // If multiple data points fall in the same bucket, use the latest one
                if (!dataMap[normalizedTs] || point.timestamp > dataMap[normalizedTs].originalTs) {
                    dataMap[normalizedTs] = {
                        power: point.power,
                        originalTs: point.timestamp
                    };
                }
            });
            
            deviceDataMapsForChart[uuid] = dataMap;
        });

        // Create individual series for each device
        const datasets = [];
        
        // Create a dataset for each device's actual (historical) data
        deviceUuids.forEach((uuid, deviceIndex) => {
            const deviceName = deviceNameMap[uuid] || `Device ${deviceIndex + 1}`;
            const deviceColor = deviceColors[deviceIndex % deviceColors.length];
            
            // Calculate actual data for this device
            const deviceActualData = allTimestamps.map((ts, idx) => {
                if (idx < forecastStartIndex) {
                    // Historical data for this device
                    const dataMap = deviceDataMapsForChart[uuid];
                    if (dataMap[ts]) {
                        return dataMap[ts].power || 0;
                    }
                    return 0;
                } else {
                    // Null for forecast period
                    return null;
                }
            });

            // Actual dataset (bars for historical period only)
            datasets.push({
                label: deviceName,
                data: deviceActualData,
                backgroundColor: deviceColor,
                borderColor: deviceColor.replace('0.8', '1'),
                borderWidth: 1,
                order: 1
            });
        });

        // Create a forecast dataset for each device
        deviceUuids.forEach((uuid, deviceIndex) => {
            const deviceName = deviceNameMap[uuid] || `Device ${deviceIndex + 1}`;
            const deviceColor = deviceColors[deviceIndex % deviceColors.length];
            
            // Calculate forecast data for this device
            const deviceForecastData = allTimestamps.map((ts, idx) => {
                if (idx >= forecastStartIndex) {
                    // Forecast data for this device
                    // Exclude if device has been off for 3 periods
                    if (!devicesToExcludeFromForecast.has(uuid)) {
                        return forecastAverages[uuid] || 0;
                    }
                    return null;
                } else {
                    // Null for historical period
                    return null;
                }
            });

            // Forecast dataset (dashed line for forecast period only)
            datasets.push({
                type: 'line',
                label: deviceName + ' (Forecast)',
                data: deviceForecastData,
                backgroundColor: deviceColor.replace('0.8', '0.2'),
                borderColor: deviceColor.replace('0.8', '0.7'),
                borderWidth: 2,
                borderDash: [8, 4],
                fill: false,
                tension: 0,
                order: 2,
                pointRadius: 0,
                pointHoverRadius: 0,
                spanGaps: false
            });
        });

        // Format timestamps for display (default to 30-minute view)
        const defaultInterval = 1800; // 30 minutes
        const labelInterval = getLabelInterval(defaultInterval);
        const labels = allTimestamps.map((ts, idx) => {
            const date = new Date(ts);
            const isForecast = idx >= forecastStartIndex;

            // Only show label at specified intervals
            // Check if this index is at a label interval boundary
            const shouldShowLabel = (idx % labelInterval === 0);

            if (!shouldShowLabel) {
                return ''; // Empty string for labels we don't want to show
            }

            const label = formatTimestampLabel(date, defaultInterval);

            // Mark forecast timestamps
            return isForecast ? label + ' (F)' : label;
        });

        // Store timestamps and labels for cost chart to use
        powerChartTimestamps = allTimestamps;
        powerChartLabels = labels;
        powerChartForecastStartIndex = forecastStartIndex;
        
        // Store power chart data for cost calculation (reuse data maps from chart)
        // Calculate total power at each timestamp (sum of all devices)
        const totalPowerAtTimestamp = allTimestamps.map((ts, idx) => {
            let totalPower = 0;
            deviceUuids.forEach((uuid) => {
                const dataMap = deviceDataMapsForChart[uuid];
                
                // Get power value for this timestamp
                if (idx < forecastStartIndex) {
                    // Historical data
                    if (dataMap[ts]) {
                        totalPower += dataMap[ts].power || 0;
                    }
                } else {
                    // Forecast data
                    if (!devicesToExcludeFromForecast.has(uuid)) {
                        totalPower += forecastAverages[uuid] || 0;
                    }
                }
            });
            return totalPower;
        });
        
        powerChartData = {
            timestamps: allTimestamps,
            totalPower: totalPowerAtTimestamp,
            forecastStartIndex: forecastStartIndex
        };

        // Create or update chart (destroy and recreate for interval changes)
        if (powerChart) {
            powerChart.destroy();
        }

        // Create chart
        {
            const ctx = document.getElementById('powerChart').getContext('2d');
            // Store labels in closure for ticks callback
            const chartLabels = labels;
            powerChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: {
                                boxWidth: 12,
                                padding: 10
                            },
                            onClick: function(e, legendItem, legend) {
                                // Standard legend click behavior
                                const index = legendItem.datasetIndex;
                                if (index >= 0) {
                                    const chart = legend.chart;
                                    const meta = chart.getDatasetMeta(index);
                                    meta.hidden = meta.hidden === null ? !chart.data.datasets[index].hidden : null;
                                    chart.update();
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    const value = context.parsed.y;
                                    if (value === null || value === undefined) {
                                        return label + 'N/A';
                                    }
                                    label += value.toFixed(1) + ' W';
                                    return label;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Time (30-second intervals) - (F) = Forecast'
                            },
                            stacked: true,
                            grid: {
                                display: true,
                                color: function(context) {
                                    // Draw a vertical line at the forecast boundary
                                    if (context.tick && context.tick.value === forecastStartIndex - 0.5) {
                                        return 'rgba(128, 128, 128, 0.5)';
                                    }
                                    return 'rgba(0, 0, 0, 0.1)';
                                }
                            },
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45,
                                autoSkip: true,
                                maxTicksLimit: getMaxTicksLimit(1800), // Default 30 minutes
                                callback: function(value, index, ticks) {
                                    // Only show non-empty labels
                                    if (index >= 0 && index < chartLabels.length) {
                                        return chartLabels[index] || '';
                                    }
                                    return '';
                                }
                            }
                        },
                        y: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Power (W)'
                            },
                            stacked: true,
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return value + ' W';
                                }
                            }
                        }
                    }
                }
            });
            
            // After chart is created, add class to forecast legend items for styling
            setTimeout(() => {
                const chartWrapper = document.querySelector('.chart-wrapper');
                if (chartWrapper) {
                    const legendContainer = chartWrapper.querySelector('canvas').parentElement;
                    if (legendContainer) {
                        const legendItems = legendContainer.querySelectorAll('ul li');
                        legendItems.forEach((item) => {
                            const text = item.textContent || '';
                            if (text.includes('(Forecast)')) {
                                item.classList.add('forecast-legend-item');
                            }
                        });
                    }
                }
            }, 100);
        }

    } catch (error) {
        console.error('Error loading timeseries data:', error);
    } finally {
        // Load cost data and price data immediately after timeseries data is loaded
        // Use requestAnimationFrame to ensure power chart is created first
        requestAnimationFrame(() => {
            loadCostData();
            loadPriceData();
            loadStandalonePriceChart();
        });
    }
}

// Load cost data and display cost chart
async function loadCostData() {
    try {
        // Use same timestamps as power chart
        if (!powerChartTimestamps || powerChartTimestamps.length === 0) {
            document.getElementById('cost-chart-section').style.display = 'none';
            return;
        }

        // Calculate cost from cached timeseries data
        const defaultInterval = 1800; // 30 minutes
        const priceResponse = await fetch(`/api/aemo/prices?interval=${defaultInterval}`);
        
        const priceData = await priceResponse.json();
        
        // Calculate costs from cached timeseries data
        const costs = calculateCostsFromCache(powerChartData, defaultInterval);

        // Check if we have any data
        if (!costs || costs.length === 0) {
            document.getElementById('cost-chart-section').style.display = 'none';
            return;
        }

        // Show cost chart section
        document.getElementById('cost-chart-section').style.display = 'block';

        // Create a map of 5-minute interval timestamps to cost data
        const costMap = {};
        costs.forEach(point => {
            const costTime = new Date(point.timestamp);
            // Round to nearest 5-minute mark for key
            const minutes = costTime.getMinutes();
            const roundedMinutes = Math.floor(minutes / 5) * 5;
            const roundedTime = new Date(costTime);
            roundedTime.setMinutes(roundedMinutes, 0, 0);
            const key = roundedTime.toISOString();
            costMap[key] = point;
        });

        // Create a map of 5-minute interval timestamps to price data
        const priceMap = {};
        if (priceData.success && priceData.prices) {
            priceData.prices.forEach(point => {
                const priceTime = new Date(point.timestamp);
                // Round to nearest 5-minute mark for key
                const minutes = priceTime.getMinutes();
                const roundedMinutes = Math.floor(minutes / 5) * 5;
                const roundedTime = new Date(priceTime);
                roundedTime.setMinutes(roundedMinutes, 0, 0);
                const key = roundedTime.toISOString();
                priceMap[key] = point.price;
            });
        }

        // Map cost data and price data to power chart timestamps (30-second intervals)
        // For each 30-second timestamp, find the corresponding 5-minute cost/price bucket
        const costValues = [];
        const priceValues = [];
        const forecastStartIndex = powerChartForecastStartIndex;

        // Calculate cost per 30-second interval based on actual power at that interval
        // This ensures cost follows the same shape as power usage
        const pricePerKwh = appSettings.defaultCostPerKwh || 0.15;
        
        powerChartTimestamps.forEach((ts, idx) => {
            const timestamp = new Date(ts);
            const minutes = timestamp.getMinutes();
            const roundedMinutes = Math.floor(minutes / 5) * 5;
            const roundedTime = new Date(timestamp);
            roundedTime.setMinutes(roundedMinutes, 0, 0);
            const key = roundedTime.toISOString();

            if (idx < forecastStartIndex) {
                // Historical: calculate cost based on actual power at this 30-second interval
                // Get total power from power chart data
                const totalPower = powerChartData ? powerChartData.totalPower[idx] : 0;
                
                // Calculate energy for this 30-second interval
                // Energy (kWh) = Power (W) × Time (hours) / 1000
                // 30 seconds = 0.5 minutes = 0.5/60 hours = 0.00833 hours
                // Energy (kWh) = Power (W) × 0.00833 / 1000 = Power × 0.00000833 kWh
                const energyKwh = (totalPower * 0.5) / (60.0 * 1000);
                
                // Calculate cost for this interval
                const cost = energyKwh * pricePerKwh;
                costValues.push(cost);
            } else {
                // Forecast: will be calculated below
                costValues.push(null);
            }

            // Retail Tariff should use the estimated cost per kWh from settings (flat line)
            // This maps the user's estimated cost setting to the Retail Tariff line
            priceValues.push(pricePerKwh);
        });

        // For forecast period, calculate cost based on actual forecast power at each 30-second interval
        // This ensures forecast cost follows the same shape as forecast power
        if (forecastStartIndex < powerChartTimestamps.length && powerChartData) {
            for (let i = forecastStartIndex; i < powerChartTimestamps.length; i++) {
                // Get total power at this timestamp from power chart data
                const totalPower = powerChartData.totalPower[i] || 0;
                
                // Calculate energy for this 30-second interval
                // Energy (kWh) = Power (W) × Time (hours) / 1000
                // 30 seconds = 0.5 minutes = 0.5/60 hours = 0.00833 hours
                // Energy (kWh) = Power (W) × 0.00833 / 1000 = Power × 0.00000833 kWh
                const energyKwh = (totalPower * 0.5) / (60.0 * 1000);
                
                // Calculate cost for this interval
                const cost = energyKwh * pricePerKwh;
                costValues[i] = cost;
            }
        }

        // Create or update chart
        if (costChart) {
            costChart.destroy();
        }

        // Split into historical and forecast datasets (like power chart)
        const historicalCostData = costValues.map((val, idx) =>
            idx < forecastStartIndex ? val : null
        );
        
        const forecastCostData = costValues.map((val, idx) =>
            idx >= forecastStartIndex ? val : null
        );

        // Split price data into historical and forecast
        const historicalPriceData = priceValues.map((val, idx) =>
            idx < forecastStartIndex ? val : null
        );
        
        const forecastPriceData = priceValues.map((val, idx) =>
            idx >= forecastStartIndex ? val : null
        );

        // Calculate daily total and savings
        const now = new Date();
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
        const noonStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12, 0, 0, 0);
        const threePmEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 15, 0, 0, 0);
        
        let dailyTotal = 0;
        let savingsAmount = 0;
        
        // Calculate totals from historical cost data only (not forecast)
        powerChartTimestamps.forEach((ts, idx) => {
            // Only process historical data (not forecast)
            if (idx >= forecastStartIndex) {
                return;
            }
            
            const timestamp = new Date(ts);
            const cost = costValues[idx];
            
            // Skip null or undefined costs
            if (cost === null || cost === undefined) {
                return;
            }
            
            // Check if timestamp is today
            if (timestamp >= todayStart && timestamp <= now) {
                dailyTotal += cost;
                
                // Check if timestamp is in 12pm-3pm window
                if (timestamp >= noonStart && timestamp < threePmEnd) {
                    savingsAmount += cost;
                }
            }
        });
        
        // Update display elements
        const dailyTotalElement = document.getElementById('daily-total-value');
        const savingsElement = document.getElementById('savings-value');
        
        if (dailyTotalElement) {
            dailyTotalElement.textContent = '$' + dailyTotal.toFixed(2);
        }
        
        if (savingsElement) {
            savingsElement.textContent = '$' + savingsAmount.toFixed(2);
        }

        const ctx = document.getElementById('costChart').getContext('2d');
        costChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: powerChartLabels, // Use same labels as power chart
                datasets: [
                    {
                        label: 'Estimated Cost',
                        data: historicalCostData,
                        backgroundColor: 'rgba(76, 175, 80, 0.2)',
                        borderColor: 'rgba(76, 175, 80, 1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.1,
                        order: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Estimated Cost (Forecast)',
                        data: forecastCostData,
                        backgroundColor: 'rgba(76, 175, 80, 0.1)',
                        borderColor: 'rgba(76, 175, 80, 0.7)',
                        borderWidth: 2,
                        borderDash: [8, 4],
                        fill: true,
                        tension: 0.1,
                        order: 2,
                        pointRadius: 0,
                        pointHoverRadius: 0,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Retail Tariff',
                        data: historicalPriceData,
                        backgroundColor: 'rgba(255, 152, 0, 0.1)',
                        borderColor: 'rgba(255, 152, 0, 1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.1,
                        order: 3,
                        yAxisID: 'y1'
                    },
                    {
                        label: 'Retail Tariff (Forecast)',
                        data: forecastPriceData,
                        backgroundColor: 'rgba(255, 152, 0, 0.05)',
                        borderColor: 'rgba(255, 152, 0, 0.7)',
                        borderWidth: 2,
                        borderDash: [8, 4],
                        fill: false,
                        tension: 0.1,
                        order: 4,
                        pointRadius: 0,
                        pointHoverRadius: 0,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const datasetLabel = context.dataset.label || '';
                                const value = context.parsed.y;
                                if (value === null || value === undefined) {
                                    return datasetLabel + ': N/A';
                                }
                                
                                if (datasetLabel.includes('Price')) {
                                    return datasetLabel + ': $' + value.toFixed(2) + '/kWh';
                                } else {
                                    return datasetLabel + ': $' + value.toFixed(4);
                                }
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Time (30-second intervals) - (F) = Forecast'
                        },
                        grid: {
                            display: true,
                            color: function(context) {
                                // Draw a vertical line at the forecast boundary
                                if (context.tick && context.tick.value === forecastStartIndex - 0.5) {
                                    return 'rgba(128, 128, 128, 0.5)';
                                }
                                return 'rgba(0, 0, 0, 0.1)';
                            }
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            autoSkip: true,
                            maxTicksLimit: getMaxTicksLimit(1800), // Default 30 minutes
                            callback: function(value, index, ticks) {
                                // Only show non-empty labels (use same labels as power chart)
                                if (index >= 0 && index < powerChartLabels.length) {
                                    return powerChartLabels[index] || '';
                                }
                                return '';
                            }
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Cost ($)'
                        },
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(4);
                            }
                        },
                        id: 'y'
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Price ($/kWh)'
                        },
                        beginAtZero: false,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        },
                        grid: {
                            drawOnChartArea: false // Only draw grid for left axis
                        },
                        id: 'y1'
                    }
                }
            }
        });

    } catch (error) {
        console.error('Error loading cost data:', error);
        document.getElementById('cost-chart-section').style.display = 'none';
    }
}

// Load power price data and display price chart
async function loadPriceData() {
    try {
        // Use same timestamps as power chart
        if (!powerChartTimestamps || powerChartTimestamps.length === 0) {
            document.getElementById('price-chart-section').style.display = 'none';
            return;
        }

        // Get region from settings (default to VIC1)
        const region = appSettings?.region || 'VIC1';

        // Calculate time range from power chart timestamps
        // Convert to AEST (UTC+10) - market time is always AEST regardless of DST
        // Chart time is in local time (AEDT UTC+11), market time is AEST (UTC+10)
        // Example: 4:30 PM AEDT = 5:30 AM UTC = 3:30 PM AEST
        // To convert: Get UTC time, add 10 hours to get AEST wall clock time, then format with +10:00
        // Round down to previous 5-minute interval (AEMO data is only every 5 minutes)
        // If first interval is at 36 minutes, get data for 35 minutes (lowest 5-minute boundary)
        const startTimeDate = new Date(powerChartTimestamps[0]);
        // Get UTC components
        const startYear = startTimeDate.getUTCFullYear();
        const startMonth = startTimeDate.getUTCMonth();
        const startDay = startTimeDate.getUTCDate();
        const startHour = startTimeDate.getUTCHours();
        const startMinutes = startTimeDate.getUTCMinutes();
        // Round down to the lowest 5-minute interval (e.g., 36 -> 35, 37 -> 35, 38 -> 35)
        const roundedStartMinutes = Math.floor(startMinutes / 5) * 5;
        
        // Create AEST time by adding 10 hours to UTC (to get AEST wall clock time)
        // Then format as ISO with +10:00 timezone
        const startTimeAEST = new Date(Date.UTC(startYear, startMonth, startDay, startHour + 10, roundedStartMinutes, 0));
        const startTime = startTimeAEST.toISOString().replace('Z', '+10:00');
        
        const endTimeDate = new Date(powerChartTimestamps[powerChartTimestamps.length - 1]);
        // Extend end time by 60 minutes to get additional export price data
        const extendedEndTimeUTC = new Date(endTimeDate.getTime() + (60 * 60 * 1000));
        // Get UTC components
        const endYear = extendedEndTimeUTC.getUTCFullYear();
        const endMonth = extendedEndTimeUTC.getUTCMonth();
        const endDay = extendedEndTimeUTC.getUTCDate();
        const endHour = extendedEndTimeUTC.getUTCHours();
        const endMinutes = extendedEndTimeUTC.getUTCMinutes();
        const roundedEndMinutes = Math.floor(endMinutes / 5) * 5;
        
        // Create AEST time by adding 10 hours to UTC (to get AEST wall clock time)
        // Then format as ISO with +10:00 timezone
        const endTimeAEST = new Date(Date.UTC(endYear, endMonth, endDay, endHour + 10, roundedEndMinutes, 0));
        const extendedEndTimeISO = endTimeAEST.toISOString().replace('Z', '+10:00');

        // Fetch Historical (Export_Price) and Forecast (Forecast_Price) data from MongoDB (extended by 60 minutes)
        let mongoData = null;
        try {
            const response = await fetch(
                `/api/mongodb/prices?region=${encodeURIComponent(region)}&start_time=${encodeURIComponent(startTime)}&end_time=${encodeURIComponent(extendedEndTimeISO)}`
            );
            if (response.ok) {
                mongoData = await response.json();
            } else {
                console.warn('MongoDB price endpoint returned error:', response.status);
            }
        } catch (error) {
            console.warn('Could not fetch MongoDB price data:', error);
        }

        // Build separate maps for historical and forecast prices
        const historicalPriceMap = new Map();
        const forecastPriceMap = new Map();
        const forecastStartIndex = powerChartForecastStartIndex;

        if (mongoData && mongoData.success) {
            // Process MongoDB Historical data (Export_Price)
            if (mongoData.historical && Array.isArray(mongoData.historical)) {
                mongoData.historical.forEach(point => {
                    if (point.x && point.y !== null && point.y !== undefined) {
                        // Round timestamp to nearest 5-minute mark
                        const timestamp = new Date(point.x);
                        const minutes = timestamp.getMinutes();
                        const roundedMinutes = Math.floor(minutes / 5) * 5;
                        const roundedTime = new Date(timestamp);
                        roundedTime.setMinutes(roundedMinutes, 0, 0);
                        const key = roundedTime.toISOString();

                        // Store Historical price value
                        historicalPriceMap.set(key, {
                            price: point.y,
                            source: 'mongodb_historical',
                            timestamp: roundedTime
                        });
                    }
                });
            }

            // Process MongoDB Forecast data (Forecast_Price)
            if (mongoData.forecast && Array.isArray(mongoData.forecast)) {
                mongoData.forecast.forEach(point => {
                    if (point.x && point.y !== null && point.y !== undefined) {
                        // Round timestamp to nearest 5-minute mark
                        const timestamp = new Date(point.x);
                        const minutes = timestamp.getMinutes();
                        const roundedMinutes = Math.floor(minutes / 5) * 5;
                        const roundedTime = new Date(timestamp);
                        roundedTime.setMinutes(roundedMinutes, 0, 0);
                        const key = roundedTime.toISOString();

                        // Store Forecast price value
                        forecastPriceMap.set(key, {
                            price: point.y,
                            source: 'mongodb_forecast',
                            timestamp: roundedTime
                        });
                    }
                });
            }
        }

        // Only use MongoDB data - no fallback to local cache or old endpoints
        if (historicalPriceMap.size === 0 && forecastPriceMap.size === 0) {
            console.warn('No MongoDB price data available for region:', region);
            document.getElementById('price-chart-section').style.display = 'none';
            return;
        }

        // Map prices to 30-second timestamps (create flat lines for each 5-minute interval)
        // Price (Actual) uses the same data source as "Historical Price" from the detailed chart
        // Price (Forecast) uses the same data source as "Forecast (Combined)" from the detailed chart
        const actualPriceData = [];
        const forecastPriceData = [];
        
        // Track the current 5-minute interval to create flat lines
        let currentIntervalKey = null;
        let currentHistoricalPrice = null;
        let currentForecastPrice = null;

        powerChartTimestamps.forEach((ts, idx) => {
            const timestamp = new Date(ts);
            const minutes = timestamp.getMinutes();
            const roundedMinutes = Math.floor(minutes / 5) * 5;
            const roundedTime = new Date(timestamp);
            roundedTime.setMinutes(roundedMinutes, 0, 0);
            const key = roundedTime.toISOString();

            // Check if we're in a new 5-minute interval
            if (key !== currentIntervalKey) {
                // New interval - get prices from MongoDB data (separate historical and forecast)
                const historicalEntry = historicalPriceMap.get(key);
                const forecastEntry = forecastPriceMap.get(key);
                // Price (Actual) uses only historical price (same as "Historical Price" in detailed chart)
                currentHistoricalPrice = historicalEntry ? historicalEntry.price : null;
                // Price (Forecast) uses forecast price (same as "Forecast (Combined)" in detailed chart)
                currentForecastPrice = forecastEntry ? forecastEntry.price : null;
                
                currentIntervalKey = key;
            }

            // Use the current interval prices (flat line for all 30-second points in this 5-minute interval)
            // Actual price: use only historical price (same data source as "Historical Price" in detailed chart)
            actualPriceData.push(currentHistoricalPrice);
            // Forecast price: use forecast price for all timestamps (same data source as "Forecast (Combined)" in detailed chart)
            // If actual price exists, set forecast to null (don't plot that point)
            forecastPriceData.push(currentHistoricalPrice !== null ? null : currentForecastPrice);
        });

        // Show chart section
        document.getElementById('price-chart-section').style.display = 'block';

        // Update chart title with region (region is already declared above)
        const regionNames = {
            'VIC1': 'Victoria',
            'NSW1': 'New South Wales',
            'QLD1': 'Queensland',
            'SA1': 'South Australia',
            'TAS1': 'Tasmania'
        };
        const regionName = regionNames[region] || region;
        const chartTitleElement = document.querySelector('#price-chart-section .chart-title');
        if (chartTitleElement) {
            chartTitleElement.textContent = `Power Price - ${regionName} (${region}) (5-minute intervals)`;
        }

        // Destroy existing chart if it exists
        if (priceChart) {
            priceChart.destroy();
        }

        // Create price chart
        const ctx = document.getElementById('priceChart').getContext('2d');
        priceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: powerChartLabels,
                datasets: [
                    {
                        label: 'Price (Actual)',
                        data: actualPriceData,
                        backgroundColor: 'rgba(46, 134, 171, 0.2)',
                        borderColor: 'rgba(46, 134, 171, 1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0, // Use straight lines (step function)
                        stepped: 'before', // Create flat lines
                        order: 1,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    },
                    {
                        label: 'Price (Forecast)',
                        data: forecastPriceData,
                        backgroundColor: 'rgba(241, 143, 1, 0.2)',
                        borderColor: 'rgba(241, 143, 1, 0.7)',
                        borderWidth: 2,
                        borderDash: [8, 4],
                        fill: false,
                        tension: 0, // Use straight lines (step function)
                        stepped: 'before', // Create flat lines
                        order: 2,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                const value = context.parsed.y;
                                if (value === null) return '';
                                return `${context.dataset.label}: $${value.toFixed(2)} AUD/MWh`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Price (AUD/MWh)'
                        },
                        beginAtZero: false,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });

    } catch (error) {
        console.error('Error loading price data:', error);
        document.getElementById('price-chart-section').style.display = 'none';
    }
}

// Load standalone price chart using exact same timestamps as power consumption chart
async function loadStandalonePriceChart() {
    try {
        // Check if standalone chart section exists - if not, skip silently
        const standaloneSection = document.getElementById('standalone-price-chart-section');
        if (!standaloneSection) {
            // Section doesn't exist, skip loading this chart
            return;
        }
        
        // Use the exact same timestamps as the power usage chart
        if (!powerChartTimestamps || powerChartTimestamps.length === 0) {
            console.warn('No power chart timestamps available for price chart');
            standaloneSection.style.display = 'none';
            return;
        }

        // Use the exact same timestamps as power chart (already normalized to 30-second intervals)
        const allTimestamps = powerChartTimestamps;

        // Fetch price data - try main server first, then power_price API
        let priceData = null;

        try {
            // Try main server endpoint first
            const response = await fetch('/api/nem/prices/latest');
            if (response.ok) {
                priceData = await response.json();
            } else {
                // Fallback to power_price API server on port 5000
                const fallbackResponse = await fetch('http://localhost:5000/api/prices/latest');
                if (fallbackResponse.ok) {
                    priceData = await fallbackResponse.json();
                }
            }
        } catch (error) {
            console.warn('Could not fetch price data:', error);
            standaloneSection.style.display = 'none';
            return;
        }

        if (!priceData || !priceData.series || priceData.series.length === 0) {
            console.warn('No price data available');
            standaloneSection.style.display = 'none';
            return;
        }

        // Build a map of 5-minute interval timestamps to prices for each data type
        const priceMapByType = {};
        const seriesPriority = ['dispatch', 'p5min', 'predispatch'];

        seriesPriority.forEach(seriesName => {
            const series = priceData.series.find(s => s.name === seriesName);
            if (series && series.data) {
                priceMapByType[seriesName] = new Map();

                series.data.forEach(point => {
                    if (point.x && point.y !== null && point.y !== undefined) {
                        // Round timestamp to nearest 5-minute mark
                        const timestamp = new Date(point.x);
                        const minutes = timestamp.getMinutes();
                        const roundedMinutes = Math.floor(minutes / 5) * 5;
                        const roundedTime = new Date(timestamp);
                        roundedTime.setMinutes(roundedMinutes, 0, 0);
                        const key = roundedTime.toISOString();

                        priceMapByType[seriesName].set(key, point.y);
                    }
                });
            }
        });

        // Map prices to timeseries timestamps
        const dataByType = {
            'dispatch': [],
            'p5min': [],
            'predispatch': []
        };

        // Map prices to timestamps using indices (to match power chart's category scale)
        allTimestamps.forEach((ts, idx) => {
            const timestamp = new Date(ts);
            const minutes = timestamp.getMinutes();
            const roundedMinutes = Math.floor(minutes / 5) * 5;
            const roundedTime = new Date(timestamp);
            roundedTime.setMinutes(roundedMinutes, 0, 0);
            const key = roundedTime.toISOString();

            // For each price type, get the price at this timestamp
            // Use index instead of timestamp for x value to match category scale
            seriesPriority.forEach(seriesName => {
                const priceMap = priceMapByType[seriesName];
                if (priceMap && priceMap.has(key)) {
                    dataByType[seriesName].push({
                        x: idx, // Use index to match category scale
                        y: priceMap.get(key)
                    });
                } else {
                    dataByType[seriesName].push({
                        x: idx, // Use index to match category scale
                        y: null
                    });
                }
            });
        });

        // Show chart section (already checked at start of function)
        standaloneSection.style.display = 'block';

        // Destroy existing chart if it exists
        if (standalonePriceChart) {
            standalonePriceChart.destroy();
        }

        // Prepare datasets for each price type
        const datasets = [];
        const colors = {
            'dispatch': { border: '#E63946', bg: 'rgba(230, 57, 70, 0.2)', label: 'Dispatch (Actual)' },
            'p5min': { border: '#F77F00', bg: 'rgba(247, 127, 0, 0.2)', label: 'P5MIN (5-min Forecast)' },
            'predispatch': { border: '#06D6A0', bg: 'rgba(6, 214, 160, 0.2)', label: 'Pre-dispatch (30min+ Forecast)' }
        };

        seriesPriority.forEach(seriesName => {
            // Always include the dataset even if some values are null
            // This ensures all timestamps are shown
            if (dataByType[seriesName] && dataByType[seriesName].length > 0) {
                const color = colors[seriesName] || { border: '#999', bg: 'rgba(150, 150, 150, 0.2)', label: seriesName };

                datasets.push({
                    label: color.label,
                    data: dataByType[seriesName],
                    backgroundColor: color.bg,
                    borderColor: color.border,
                    borderWidth: 2,
                    fill: false,
                    tension: 0.1,
                    spanGaps: false, // Don't span gaps - show breaks for null values
                    pointRadius: function(context) {
                        // Only show points when value is not null
                        return context.parsed.y !== null ? (seriesName === 'dispatch' ? 3 : 2) : 0;
                    },
                    pointHoverRadius: 6
                });
            }
        });

        if (datasets.length === 0) {
            console.warn('No price data overlaps with timeseries data');
            standaloneSection.style.display = 'none';
            return;
        }

        // Create chart - use same labels as power chart for exact x-axis alignment
        const ctx = document.getElementById('standalonePriceChart').getContext('2d');
        const chartLabels = powerChartLabels && powerChartLabels.length > 0 
            ? powerChartLabels 
            : allTimestamps.map(() => '');
        
        standalonePriceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartLabels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                const value = context.parsed.y;
                                if (value === null) return '';
                                return `${context.dataset.label}: $${value.toFixed(2)} AUD/MWh`;
                            },
                            title: function(context) {
                                // Use the label from the x-axis if available
                                const index = context[0].dataIndex;
                                if (chartLabels && chartLabels[index]) {
                                    return chartLabels[index];
                                }
                                // Fallback to formatted date
                                const date = new Date(context[0].parsed.x);
                                return date.toLocaleString('en-AU', {
                                    month: 'short',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit'
                                });
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Time (30-second intervals) - (F) = Forecast'
                        },
                        grid: {
                            display: true,
                            color: function(context) {
                                // Draw a vertical line at the forecast boundary if available
                                if (powerChartForecastStartIndex !== undefined && context.tick) {
                                    const forecastIndex = powerChartForecastStartIndex;
                                    if (context.tick && context.tick.value === forecastIndex - 0.5) {
                                        return 'rgba(128, 128, 128, 0.5)';
                                    }
                                }
                                return 'rgba(0, 0, 0, 0.1)';
                            }
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            autoSkip: true,
                            maxTicksLimit: getMaxTicksLimit(1800), // Default 30 minutes, same as power chart
                            callback: function(value, index, ticks) {
                                // Use same labels as power chart
                                if (chartLabels && index >= 0 && index < chartLabels.length) {
                                    return chartLabels[index] || '';
                                }
                                return '';
                            }
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Price ($/MWh)'
                        },
                        beginAtZero: false,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });

    } catch (error) {
        console.error('Error loading standalone price chart:', error);
        // standaloneSection is already checked at start of function
        if (typeof standaloneSection !== 'undefined' && standaloneSection) {
            standaloneSection.style.display = 'none';
        }
    }
}

