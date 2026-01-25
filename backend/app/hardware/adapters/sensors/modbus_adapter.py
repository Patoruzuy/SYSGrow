"""
Modbus Sensor Adapter
=====================
Adapter for sensors using Modbus/RS485 protocol.
"""
import logging
from typing import Dict, Any, Optional
from .base_adapter import ISensorAdapter, AdapterError

logger = logging.getLogger(__name__)


class ModbusAdapter(ISensorAdapter):
    """
    Adapter for Modbus/RS485 sensors.
    
    Supports industrial sensors using Modbus RTU or Modbus TCP protocols.
    Common use cases:
    - Soil moisture/EC/pH sensors (RS485)
    - Weather stations
    - Industrial temperature/humidity sensors
    """
    
    def __init__(self,
                 sensor_id: int,
                 modbus_client,
                 slave_id: int,
                 register_address: int,
                 register_count: int = 1,
                 data_type: str = "uint16",
                 scale_factor: float = 1.0,
                 offset: float = 0.0,
                 **kwargs):
        """
        Initialize Modbus adapter.
        
        Args:
            sensor_id: Unique sensor ID
            modbus_client: Modbus client instance (pymodbus)
            slave_id: Modbus slave/unit ID
            register_address: Starting register address
            register_count: Number of registers to read
            data_type: Data type (uint16, int16, uint32, int32, float32)
            scale_factor: Multiplier for raw value
            offset: Offset to add after scaling
            **kwargs: Catch extra parameters leaked from factory
        """
        self.sensor_id = sensor_id
        self.modbus_client = modbus_client
        self.slave_id = slave_id
        self.register_address = register_address
        self.register_count = register_count
        self.data_type = data_type
        self.scale_factor = scale_factor
        self.offset = offset
        
        self._available = False
        
        # Test connection
        if self.modbus_client:
            try:
                # Try to read one register to test connection
                self._test_connection()
                self._available = True
                logger.info(f"Modbus adapter initialized for slave {slave_id}")
            except Exception as e:
                logger.error(f"Failed to initialize Modbus connection: {e}")
                self._available = False
    
    def _test_connection(self):
        """Test Modbus connection"""
        try:
            # Try reading from configured register
            result = self.modbus_client.read_holding_registers(
                self.register_address,
                count=1,
                unit=self.slave_id
            )
            if result.isError():
                raise AdapterError(f"Modbus test read failed: {result}")
        except Exception as e:
            raise AdapterError(f"Modbus connection test failed: {e}")
    
    def read(self) -> Dict[str, Any]:
        """
        Read data from Modbus sensor.
        
        Returns:
            Dict with sensor readings
            
        Raises:
            AdapterError: If read fails
        """
        if not self.modbus_client:
            raise AdapterError("Modbus client not available")
        
        try:
            # Read holding registers
            result = self.modbus_client.read_holding_registers(
                self.register_address,
                count=self.register_count,
                unit=self.slave_id
            )
            
            if result.isError():
                raise AdapterError(f"Modbus read error: {result}")
            
            # Convert registers to value based on data type
            raw_value = self._convert_registers(result.registers)
            
            # Apply scaling and offset
            scaled_value = (raw_value * self.scale_factor) + self.offset
            
            return {
                'value': scaled_value,
                'raw_value': raw_value,
                'slave_id': self.slave_id,
                'register_address': self.register_address
            }
            
        except Exception as e:
            logger.error(f"Modbus adapter read error: {e}")
            raise AdapterError(f"Failed to read Modbus sensor: {e}")
    
    def _convert_registers(self, registers: list) -> float:
        """
        Convert Modbus registers to value based on data type.
        
        Args:
            registers: List of register values
            
        Returns:
            Converted value
        """
        if self.data_type == "uint16":
            return float(registers[0])
        
        elif self.data_type == "int16":
            # Convert unsigned to signed
            value = registers[0]
            if value > 32767:
                value -= 65536
            return float(value)
        
        elif self.data_type == "uint32":
            if len(registers) < 2:
                raise ValueError("uint32 requires 2 registers")
            return float((registers[0] << 16) | registers[1])
        
        elif self.data_type == "int32":
            if len(registers) < 2:
                raise ValueError("int32 requires 2 registers")
            value = (registers[0] << 16) | registers[1]
            if value > 2147483647:
                value -= 4294967296
            return float(value)
        
        elif self.data_type == "float32":
            if len(registers) < 2:
                raise ValueError("float32 requires 2 registers")
            import struct
            # Combine two 16-bit registers into 32-bit float
            bytes_data = struct.pack('>HH', registers[0], registers[1])
            return struct.unpack('>f', bytes_data)[0]
        
        else:
            raise ValueError(f"Unsupported data type: {self.data_type}")
    
    def configure(self, config: Dict[str, Any]) -> None:
        """
        Reconfigure Modbus adapter.
        
        Args:
            config: Configuration dictionary
        """
        if 'slave_id' in config:
            self.slave_id = config['slave_id']
        
        if 'register_address' in config:
            self.register_address = config['register_address']
        
        if 'register_count' in config:
            self.register_count = config['register_count']
        
        if 'data_type' in config:
            self.data_type = config['data_type']
        
        if 'scale_factor' in config:
            self.scale_factor = config['scale_factor']
        
        if 'offset' in config:
            self.offset = config['offset']
        
        # Test new configuration
        try:
            self._test_connection()
            self._available = True
        except Exception as e:
            logger.error(f"Failed to apply Modbus configuration: {e}")
            self._available = False
            raise AdapterError(f"Configuration failed: {e}")
    
    def is_available(self) -> bool:
        """
        Check if Modbus sensor is available.
        
        Returns:
            True if Modbus client is connected
        """
        return self._available and self.modbus_client is not None
    
    def get_protocol_name(self) -> str:
        """Get protocol name"""
        return "Modbus"
    
    def cleanup(self) -> None:
        """Cleanup Modbus resources"""
        # Modbus client cleanup is typically handled by the client itself
        pass
