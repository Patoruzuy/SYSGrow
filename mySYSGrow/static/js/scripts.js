function fetchSensorReading() {
    fetch('/reading_update')
        .then(response => response.json())
        .then(data => {
            console.log('Fetched data:', data);  // Debugging line to check fetched data

            const temperatureElement = document.getElementById('temperature');
            const humidityElement = document.getElementById('humidity');

            const temperatureThreshold = parseFloat(temperatureElement.getAttribute('data-threshold'));
            const humidityThreshold = parseFloat(humidityElement.getAttribute('data-threshold'));

            if (!data || !data.DHT) {
                temperatureElement.innerText = 'Error';
                humidityElement.innerText = 'Error';
                console.error('Invalid data format:', data);  // Debugging line to check data format
                return;
            }

            const temperature = data.DHT.temperature;
            const humidity = data.DHT.humidity;

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


function adjustDays(plantName, action) {
    fetch(`/${action}_days/${plantName}`, {
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