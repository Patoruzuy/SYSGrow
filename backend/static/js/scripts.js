function fetchSensorReading() {
    fetch('/reading_update')
        .then(response => response.json())
        .then(data => {
            console.log('Fetched data:', data);  // Debugging line to check fetched data

            const temperatureElement = document.getElementById('temperature');
            const humidityElement = document.getElementById('humidity');

            const temperatureThreshold = parseFloat(temperatureElement.getAttribute('data-threshold'));
            const humidityThreshold = parseFloat(humidityElement.getAttribute('data-threshold'));

            // Iterate over the sensor data to find the sensor with type 'temp_humidity_sensor'
            let sensorData = null;
            for (let key in data) {
                if (data[key].sensor_type === 'temp_humidity_sensor') {
                    sensorData = data[key];
                    break;
                }
            }

            if (!sensorData) {
                temperatureElement.innerText = 'Error';
                humidityElement.innerText = 'Error';
                console.error('Temp/humidity sensor data not found:', data);  // Debugging line to check data format
                return;
            }

            const temperature = sensorData.temperature;
            const humidity = sensorData.humidity;

            if (temperature !== null && temperature !== undefined) {
                temperatureElement.innerText = temperature + '°C';
                temperatureElement.style.color = temperature > temperatureThreshold ? 'red' : 'green';
            } else {
                temperatureElement.innerText = 'N/A';
            }

            if (humidity !== null && humidity !== undefined) {
                humidityElement.innerText = humidity + '%';
                humidityElement.style.color = humidity < humidityThreshold ? 'blue' : 'green';
            } else {
                humidityElement.innerText = 'N/A';
            }
        })
        .catch(error => {
            console.error('Error fetching sensor data:', error);
            document.getElementById('temperature').innerText = 'Error';
            document.getElementById('humidity').innerText = 'Error';
        });
}

// Fetch data every 5 seconds
setInterval(fetchSensorReading, 5000);

// Fetch data immediately when the page loads
window.onload = fetchSensorReading;

function adjustDays(action, plantID) {
    fetch(`/${plantID}/${action}_days`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            location.reload();
        } else {
            alert(data.message);
        }
    })
    .catch(error => console.error('Error adjusting days:', error));
}

