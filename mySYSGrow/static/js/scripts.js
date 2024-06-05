function fetchSensorData() {
    fetch('/reading_update')
        .then(response => response.json())
        .then(data => {
            const temperatureElement = document.getElementById('temperature');
            const humidityElement = document.getElementById('humidity');

            const temperatureThreshold = parseFloat(temperatureElement.getAttribute('data-threshold'));
            const humidityThreshold = parseFloat(humidityElement.getAttribute('data-threshold'));

            if (data.error) {
                temperatureElement.innerText = data.error;
                humidityElement.innerText = data.error;
            } else {
                const temperature = data.temperature;
                const humidity = data.humidity;

                temperatureElement.innerText = temperature + '°C';
                humidityElement.innerText = humidity + '%';

                // Change font color based on temperature threshold
                if (temperature > temperatureThreshold) {
                    temperatureElement.style.color = 'red';
                } else {
                    temperatureElement.style.color = 'green';
                }

                // Change font color based on humidity threshold
                if (humidity < humidityThreshold) {
                    humidityElement.style.color = 'blue';
                } else {
                    humidityElement.style.color = 'green';
                }
            }
        })
        .catch(error => console.error('Error fetching sensor data:', error));
}

// Fetch data every 5 seconds
setInterval(fetchSensorData, 5000);

// Fetch data immediately when the page loads
window.onload = fetchSensorData;

let deviceCount = parseInt(document.getElementById('device_count').value, 10);

function addDevice() {
    deviceCount++;
    document.getElementById('device_count').value = deviceCount;
    const container = document.getElementById('devices-container');
    const deviceDiv = document.createElement('div');
    deviceDiv.className = 'device';
    deviceDiv.innerHTML = `
        <label for="device_name_${deviceCount}">Device Name:</label>
        <input type="text" id="device_name_${deviceCount}" name="device_name_${deviceCount}">
        <label for="device_gpio_${deviceCount}">GPIO:</label>
        <input type="text" id="device_gpio_${deviceCount}" name="device_gpio_${deviceCount}">
        <label for="device_ip_${deviceCount}">IP Address:</label>
        <input type="text" id="device_ip_${deviceCount}" name="device_ip_${deviceCount}">
        <label for="device_functionality_${deviceCount}">Functionality:</label>
        <select id="device_functionality_${deviceCount}" name="device_functionality_${deviceCount}">
            <option value="light">Light</option>
            <option value="temperature_control">Temperature Control</option>
            <option value="humidity_control">Humidity Control</option>
        </select>
        <button type="button" onclick="testDevice('new_device')">Test Device</button>
        <span id="test_result_${deviceCount}"></span>
    `;
    container.appendChild(deviceDiv);
}

function testDevice(deviceName) {
    fetch(`/test_device?device=${deviceName}`)
        .then(response => response.json())
        .then(data => {
            const resultElement = document.querySelector(`#test_result_${deviceName}`);
            if (data.success) {
                resultElement.innerText = "Test successful!";
                resultElement.style.color = "green";
            } else {
                resultElement.innerText = "Test failed.";
                resultElement.style.color = "red";
            }
        })
        .catch(error => {
            console.error('Error testing device:', error);
            const resultElement = document.querySelector(`#test_result_${deviceName}`);
            resultElement.innerText = "Error testing device.";
            resultElement.style.color = "red";
        });
}
