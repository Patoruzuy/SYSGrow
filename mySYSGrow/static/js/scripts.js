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

function addDeviceAndSubmit() {
    const deviceCount = document.getElementById('device_count');
    let count = parseInt(deviceCount.value);

    count += 1;
    deviceCount.value = count;

    const newDeviceContainer = document.getElementById('new-device-container');
    const newDeviceDiv = document.createElement('div');
    newDeviceDiv.classList.add('device');
    newDeviceDiv.id = `device_${count}`;

    newDeviceDiv.innerHTML = `
        <label for="device_name_${count}">Device Name:</label>
        <input type="text" id="device_name_${count}" name="device_name_${count}">
        <label for="device_gpio_${count}">GPIO:</label>
        <input type="text" id="device_gpio_${count}" name="device_gpio_${count}">
        <label for="device_ip_${count}">IP Address:</label>
        <input type="text" id="device_ip_${count}" name="device_ip_${count}">
        <label for="device_functionality_${count}">Functionality:</label>
        <select id="device_functionality_${count}" name="device_functionality_${count}">
            <option value="light">Light</option>
            <option value="temperature">Temperature Control</option>
            <option value="humidity">Humidity Control</option>
            <option value="soil_moisture">Soil Moisture</option>
        </select>
        <button type="button" onclick="testDevice('device_name_${count}', 'device_gpio_${count}', 'device_ip_${count}', 'device_functionality_${count}', ${count})">Test Device</button>
        <span id="test_result_${count}"></span>
    `;

    newDeviceContainer.appendChild(newDeviceDiv);
    document.getElementById('settings-form').submit();
}


function testDevice(functionality, index) {
    const functionality = document.getElementById(functionality).value;
    fetch(`/test_device?functionality=${functionality}`)
        .then(response => response.json())
        .then(data => {
            const resultElement = document.getElementById(`test_result_${index}`);
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
            const resultElement = document.getElementById(`test_result_${index}`);
            resultElement.innerText = "Error testing device.";
            resultElement.style.color = "red";
        });
}
