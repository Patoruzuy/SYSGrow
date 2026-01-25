/**
 * Debug Test Script for Refactored JavaScript
 * Run this in browser console to verify all modules load correctly
 */

console.log('=== JavaScript Refactoring Debug Test ===\n');

// Test 1: Check if utilities are loaded
console.log('1️⃣ Testing Utilities...');
console.log('   CacheService:', typeof CacheService !== 'undefined' ? '✅' : '❌');
console.log('   Modal:', typeof Modal !== 'undefined' ? '✅' : '❌');
console.log('   BaseManager:', typeof BaseManager !== 'undefined' ? '✅' : '❌');

// Test 2: Check if API is loaded
console.log('\n2️⃣ Testing API...');
console.log('   window.API:', typeof window.API !== 'undefined' ? '✅' : '❌');
if (window.API) {
    console.log('   API.Plant:', typeof window.API.Plant !== 'undefined' ? '✅' : '❌');
    console.log('   API.Device:', typeof window.API.Device !== 'undefined' ? '✅' : '❌');
    console.log('   API.Health:', typeof window.API.Health !== 'undefined' ? '✅' : '❌');
    console.log('   API.Growth:', typeof window.API.Growth !== 'undefined' ? '✅' : '❌');
    console.log('   API.System:', typeof window.API.System !== 'undefined' ? '✅' : '❌');
    console.log('   API.Dashboard:', typeof window.API.Dashboard !== 'undefined' ? '✅' : '❌');
    console.log('   API.Settings:', typeof window.API.Settings !== 'undefined' ? '✅' : '❌');
    console.log('   API.ESP32:', typeof window.API.ESP32 !== 'undefined' ? '✅' : '❌');
}

// Test 3: Check specific API methods
console.log('\n3️⃣ Testing API Methods...');
if (window.API) {
    console.log('   Plant.getPlantHealth:', typeof window.API.Plant.getPlantHealth === 'function' ? '✅' : '❌');
    console.log('   Plant.getPlantsGuide:', typeof window.API.Plant.getPlantsGuide === 'function' ? '✅' : '❌');
    console.log('   Health.getSystemHealth:', typeof window.API.Health.getSystemHealth === 'function' ? '✅' : '❌');
    console.log('   Health.getDevicesHealth:', typeof window.API.Health.getDevicesHealth === 'function' ? '✅' : '❌');
    console.log('   Device.addSensor:', typeof window.API.Device.addSensor === 'function' ? '✅' : '❌');
    console.log('   Device.deleteSensor:', typeof window.API.Device.deleteSensor === 'function' ? '✅' : '❌');
    console.log('   System.getActivities:', typeof window.API.System.getActivities === 'function' ? '✅' : '❌');
    console.log('   System.getAlerts:', typeof window.API.System.getAlerts === 'function' ? '✅' : '❌');
}

// Test 4: Check Socket Manager
console.log('\n4️⃣ Testing Socket Manager...');
console.log('   socketManager:', typeof window.socketManager !== 'undefined' ? '✅' : '❌');
console.log('   SocketManager class:', typeof window.SocketManager !== 'undefined' ? '✅' : '❌');

// Test 5: Check page-specific modules
console.log('\n5️⃣ Testing Page Modules...');

// Dashboard
if (typeof DashboardDataService !== 'undefined') {
    console.log('   DashboardDataService:', '✅');
} else {
    console.log('   DashboardDataService:', '❌ NOT LOADED');
}

if (typeof DashboardUIManager !== 'undefined') {
    console.log('   DashboardUIManager:', '✅');
} else {
    console.log('   DashboardUIManager:', '❌ NOT LOADED');
}

if (window.Dashboard) {
    console.log('   window.Dashboard:', '✅');
    console.log('     - dataService:', window.Dashboard.dataService ? '✅' : '❌');
    console.log('     - uiManager:', window.Dashboard.uiManager ? '✅' : '❌');
} else {
    console.log('   window.Dashboard:', '❌ NOT INITIALIZED');
}

// Devices
if (typeof DevicesDataService !== 'undefined') {
    console.log('   DevicesDataService:', '✅');
} else {
    console.log('   DevicesDataService:', '❌ NOT LOADED');
}

if (typeof DevicesUIManager !== 'undefined') {
    console.log('   DevicesUIManager:', '✅');
} else {
    console.log('   DevicesUIManager:', '❌ NOT LOADED');
}

if (window.devicesHub) {
    console.log('   window.devicesHub:', '✅');
    console.log('     - dataService:', window.devicesHub.dataService ? '✅' : '❌');
    console.log('     - uiManager:', window.devicesHub.uiManager ? '✅' : '❌');
} else {
    console.log('   window.devicesHub:', '❌ NOT INITIALIZED');
}

// Plants
if (typeof PlantsDataService !== 'undefined') {
    console.log('   PlantsDataService:', '✅');
} else {
    console.log('   PlantsDataService:', '❌ NOT LOADED');
}

if (typeof PlantsUIManager !== 'undefined') {
    console.log('   PlantsUIManager:', '✅');
} else {
    console.log('   PlantsUIManager:', '❌ NOT LOADED');
}

if (window.plantsHub) {
    console.log('   window.plantsHub:', '✅');
    console.log('     - dataService:', window.plantsHub.dataService ? '✅' : '❌');
    console.log('     - uiManager:', window.plantsHub.uiManager ? '✅' : '❌');
} else {
    console.log('   window.plantsHub:', '❌ NOT INITIALIZED');
}

console.log('\n=== Test Complete ===');
console.log('If any items show ❌, check the browser console for errors during page load.');
