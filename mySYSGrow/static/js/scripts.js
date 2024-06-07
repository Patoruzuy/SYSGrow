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

function testEntity(functionality) {
    const xhr = new XMLHttpRequest();
    xhr.open("GET", `/test_device?functionality=${functionality}`);
    xhr.onload = function() {
        if (xhr.status == 200) {
            const response = JSON.parse(xhr.responseText);
            document.getElementById('test_result').textContent = response.success ? "Device test successful" : "Device test failed";
        } else {
            document.getElementById('test_result').textContent = "Error testing device";
        }
    };
    xhr.onerror = function() {
        document.getElementById('test_result').textContent = "Network error";
    };
    xhr.send();
}
