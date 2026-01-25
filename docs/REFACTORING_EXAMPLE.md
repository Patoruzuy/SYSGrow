# API Refactoring Example: Using Enums and Schemas

This document demonstrates how to refactor API endpoints to use the new enums and Pydantic schemas for type safety and validation.

## Before: Manual Validation

```python
@devices_api.route('/sensors', methods=['POST'])
def add_sensor():
    """Add a new sensor to a growth unit"""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()

        # Manual validation - prone to errors
        try:
            unit_id = int(data.get('unit_id', 1))
        except (TypeError, ValueError):
            return _fail('unit_id must be an integer', 400)

        sensor_name = (data.get('sensor_name') or '').strip()
        sensor_type = (data.get('sensor_type') or '').strip()
        sensor_model = (data.get('sensor_model') or '').strip()
        
        # Optional fields
        gpio_pin = data.get('sensor_pin') or data.get('gpio_pin')
        communication = data.get('communication', 'GPIO')

        # More manual validation...
        if not sensor_name:
            return _fail('Sensor name is required', 400)
        if not sensor_type:
            return _fail('Sensor type is required', 400)
        if not sensor_model:
            return _fail('Sensor model is required', 400)
        
        # Business logic mixed with validation
        device_service.create_sensor(...)
        return _success({"message": "Sensor added"})
    except Exception as e:
        return _fail(str(e), 500)
```

## After: Schema-Based Validation

```python
from pydantic import ValidationError
from app.schemas import CreateSensorRequest, SensorResponse, SuccessResponse, ErrorResponse
from app.enums import SensorType, SensorModel, CommunicationType

@devices_api.post('/sensors')
def add_sensor():
    """
    Add a new sensor to a growth unit
    
    Request Body:
        CreateSensorRequest
    
    Returns:
        SuccessResponse[SensorResponse]: Created sensor data
        ErrorResponse: Validation or creation error
    """
    try:
        # Automatic validation via Pydantic
        sensor_data = CreateSensorRequest(**request.get_json())
        
        # Validate growth unit exists
        if not _unit_exists(sensor_data.unit_id):
            return _fail(f'Growth unit {sensor_data.unit_id} not found', 404)
        
        # Create sensor - all types are already validated
        device_service = _device_service()
        sensor = device_service.create_sensor(
            name=sensor_data.name,
            sensor_type=sensor_data.type.value,  # Enum guarantees valid value
            sensor_model=sensor_data.model.value,
            unit_id=sensor_data.unit_id,
            gpio=sensor_data.gpio_pin,
            communication=sensor_data.communication_type.value,
            power_mode=sensor_data.power_mode.value,
            update_interval=60
        )
        
        # Return validated response
        response = SensorResponse(**sensor)
        return _success(response.model_dump())
        
    except ValidationError as e:
        # Pydantic provides detailed validation errors
        return _fail('Validation error', 400, details={"errors": e.errors()})
    except Exception as e:
        return _fail(str(e), 500)
```

## Benefits

### 1. Type Safety with Enums
```python
# Before: Magic strings (typos cause runtime errors)
sensor_type = "temprature"  # Typo! Will fail later
communication = "I2C"  # Is it "I2C" or "i2c"?

# After: IDE autocomplete + compile-time validation
from app.enums import SensorType, CommunicationType

sensor_type = SensorType.TEMPERATURE  # Autocomplete suggests all options
communication = CommunicationType.I2C  # Guaranteed valid
```

### 2. Automatic Validation
```python
# Before: Manual checks everywhere
if not sensor_name:
    return error
if len(sensor_name) > 100:
    return error
if gpio_pin and not (0 <= gpio_pin <= 40):
    return error

# After: Declarative schema
class CreateSensorRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    gpio_pin: Optional[int] = Field(default=None, ge=0, le=40)
```

### 3. Self-Documenting API
```python
# Schemas serve as documentation
class CreateSensorRequest(BaseModel):
    """Request model for creating a new sensor"""
    name: str = Field(..., description="Sensor name")
    type: SensorType = Field(..., description="Sensor type")
    # ... IDE shows all field descriptions
```

### 4. Consistent Error Messages
```python
# Before: Custom error messages everywhere
return _fail('sensor_name is required', 400)
return _fail('name cannot be empty', 400)
return _fail('Sensor name missing', 400)

# After: Pydantic provides consistent validation errors
{
  "ok": false,
  "error": {
    "message": "Validation error",
    "errors": [
      {
        "loc": ["name"],
        "msg": "field required",
        "type": "value_error.missing"
      }
    ]
  }
}
```

## Import Pattern

At the top of `devices.py`:

```python
from pydantic import ValidationError

# Import enums
from app.enums import (
    CommunicationType,
    SensorType,
    SensorModel,
    ActuatorType,
    ActuatorState,
    PowerMode
)

# Import schemas
from app.schemas import (
    CreateSensorRequest,
    UpdateSensorRequest,
    SensorResponse,
    CreateActuatorRequest,
    UpdateActuatorRequest,
    ActuatorResponse,
    ControlActuatorRequest,
    SuccessResponse,
    ErrorResponse
)
```

## Next Steps

1. **Install Pydantic**: Run `pip install pydantic>=2.0.0`
2. **Refactor one endpoint**: Start with `add_sensor()` as shown above
3. **Test validation**: Send invalid requests to verify error handling
4. **Repeat pattern**: Apply to all endpoints in devices.py
5. **Extend to other blueprints**: growth.py, sensors.py, settings.py, etc.

## Example Test Cases

```python
# Valid request - should succeed
{
  "name": "Temperature Sensor 1",
  "type": "temperature",
  "model": "DHT22",
  "communication_type": "GPIO",
  "gpio_pin": 4,
  "unit_id": 1,
  "power_mode": "normal"
}

# Invalid - missing required field
{
  "name": "Test",
  "type": "temperature"
  # Missing: model, communication_type, unit_id
}

# Invalid - wrong enum value
{
  "name": "Test",
  "type": "invalid_sensor_type",  # Not in SensorType enum
  "model": "DHT22",
  "communication_type": "GPIO",
  "unit_id": 1
}

# Invalid - gpio_pin out of range
{
  "name": "Test",
  "type": "temperature",
  "model": "DHT22",
  "communication_type": "GPIO",
  "gpio_pin": 99,  # Valid range: 0-40
  "unit_id": 1
}
```

## Migration Strategy

1. **Phase 1**: Add enums and schemas (✅ Done)
2. **Phase 2**: Refactor devices.py endpoints
3. **Phase 3**: Refactor growth.py endpoints  
4. **Phase 4**: Refactor remaining API blueprints
5. **Phase 5**: Update service layer to accept enum types
6. **Phase 6**: Update database layer to store enum values

This incremental approach allows testing at each step without breaking existing functionality.
