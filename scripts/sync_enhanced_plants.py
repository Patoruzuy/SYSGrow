#!/usr/bin/env python3
"""
Enhanced Plants Database Integration
==================================

This script synchronizes the enhanced plants_info.json data with the 
SYSGrow SQLite database, creating proper database entries with all
the smart agriculture features.

It extends the existing Plants table and creates additional tables
for the enhanced plant data including automation settings, sensor
requirements, yield data, nutritional info, and common issues.
"""

import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class EnhancedPlantsDBIntegrator:
    """Integrates enhanced plants data with SYSGrow database"""
    
    def __init__(self, db_path: str, json_path: str = "plants_info.json"):
        self.db_path = db_path
        self.json_path = Path(json_path)
        
    def create_enhanced_plant_tables(self):
        """Create additional tables to store enhanced plant data"""
        
        with sqlite3.connect(self.db_path) as conn:
            # Enhanced Plants Information Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS EnhancedPlants (
                    enhanced_plant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plant_id INTEGER UNIQUE,
                    species TEXT,
                    common_name TEXT NOT NULL,
                    variety TEXT,
                    pH_range TEXT,
                    water_requirements TEXT,
                    difficulty_level TEXT,
                    market_value_per_kg REAL,
                    harvest_frequency TEXT,
                    storage_life_days INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
                )
            """)
            
            # Sensor Requirements Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS PlantSensorRequirements (
                    req_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enhanced_plant_id INTEGER,
                    soil_moisture_min REAL,
                    soil_moisture_max REAL,
                    soil_temp_min REAL,
                    soil_temp_max REAL,
                    air_quality_sensitivity TEXT,
                    co2_min REAL,
                    co2_max REAL,
                    vpd_min REAL,
                    vpd_max REAL,
                    light_blue_percent REAL,
                    light_red_percent REAL,
                    light_green_percent REAL,
                    light_far_red_percent REAL,
                    FOREIGN KEY (enhanced_plant_id) REFERENCES EnhancedPlants(enhanced_plant_id)
                )
            """)
            
            # Yield Data Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS PlantYieldData (
                    yield_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enhanced_plant_id INTEGER,
                    min_yield_grams REAL,
                    max_yield_grams REAL,
                    harvest_period_weeks INTEGER,
                    space_width_cm REAL,
                    space_depth_cm REAL,
                    space_height_cm REAL,
                    FOREIGN KEY (enhanced_plant_id) REFERENCES EnhancedPlants(enhanced_plant_id)
                )
            """)
            
            # Automation Settings Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS PlantAutomation (
                    automation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enhanced_plant_id INTEGER,
                    watering_frequency_hours INTEGER,
                    watering_amount_ml INTEGER,
                    soil_moisture_trigger REAL,
                    early_morning_boost BOOLEAN DEFAULT 0,
                    temperature_min REAL,
                    temperature_max REAL,
                    humidity_min REAL,
                    humidity_max REAL,
                    soil_moisture_critical REAL,
                    ventilation_trigger_temp REAL,
                    heating_trigger_temp REAL,
                    dehumidify_trigger REAL,
                    co2_enrichment BOOLEAN DEFAULT 0,
                    FOREIGN KEY (enhanced_plant_id) REFERENCES EnhancedPlants(enhanced_plant_id)
                )
            """)
            
            # Lighting Schedule Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS PlantLightingSchedule (
                    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enhanced_plant_id INTEGER,
                    growth_stage TEXT,
                    hours_per_day REAL,
                    intensity_percent REAL,
                    FOREIGN KEY (enhanced_plant_id) REFERENCES EnhancedPlants(enhanced_plant_id)
                )
            """)
            
            # Nutritional Information Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS PlantNutrition (
                    nutrition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enhanced_plant_id INTEGER,
                    calories_per_100g REAL,
                    protein_g REAL,
                    vitamin_c_mg REAL,
                    key_nutrients TEXT, -- JSON array
                    health_benefits TEXT, -- JSON array
                    special_compounds TEXT, -- JSON for things like THC, CBD, etc.
                    FOREIGN KEY (enhanced_plant_id) REFERENCES EnhancedPlants(enhanced_plant_id)
                )
            """)
            
            # Common Issues Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS PlantCommonIssues (
                    issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enhanced_plant_id INTEGER,
                    problem_name TEXT NOT NULL,
                    symptoms TEXT, -- JSON array
                    causes TEXT, -- JSON array
                    solutions TEXT, -- JSON array
                    prevention TEXT,
                    sensor_indicators TEXT, -- JSON object
                    FOREIGN KEY (enhanced_plant_id) REFERENCES EnhancedPlants(enhanced_plant_id)
                )
            """)
            
            # Growth Stages Table (enhanced with sensor targets)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS PlantGrowthStages (
                    stage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enhanced_plant_id INTEGER,
                    stage_name TEXT NOT NULL,
                    min_days INTEGER,
                    max_days INTEGER,
                    temperature_min REAL,
                    temperature_max REAL,
                    humidity_min REAL,
                    humidity_max REAL,
                    light_hours REAL,
                    soil_moisture_target REAL,
                    soil_temp_target REAL,
                    vpd_target REAL,
                    care_instructions TEXT, -- JSON array
                    FOREIGN KEY (enhanced_plant_id) REFERENCES EnhancedPlants(enhanced_plant_id)
                )
            """)
            
            # Companion Plants Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS PlantCompanions (
                    companion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enhanced_plant_id INTEGER,
                    companion_type TEXT, -- 'beneficial' or 'avoid'
                    companion_plants TEXT, -- JSON array of plant names
                    reasoning TEXT,
                    FOREIGN KEY (enhanced_plant_id) REFERENCES EnhancedPlants(enhanced_plant_id)
                )
            """)
            
            # Harvest Guide Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS PlantHarvestGuide (
                    harvest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enhanced_plant_id INTEGER,
                    indicators TEXT, -- JSON array
                    storage_tips TEXT, -- JSON array
                    processing_options TEXT, -- JSON array
                    FOREIGN KEY (enhanced_plant_id) REFERENCES EnhancedPlants(enhanced_plant_id)
                )
            """)
            
            # Create indexes for better performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_plants_common_name ON EnhancedPlants(common_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_plants_species ON EnhancedPlants(species)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_plants_difficulty ON EnhancedPlants(difficulty_level)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_plant_lighting_stage ON PlantLightingSchedule(growth_stage)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_plant_growth_stage ON PlantGrowthStages(stage_name)")
            
            logger.info("Enhanced plant tables created successfully")

    def sync_enhanced_plants_data(self):
        """Sync plants_info.json data with the database"""
        
        if not self.json_path.exists():
            logger.error(f"Plants JSON file not found: {self.json_path}")
            return False
            
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                plants_data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading plants JSON: {e}")
            return False
        
        plants_info = plants_data.get('plants_info', [])
        if not plants_info:
            logger.warning("No plants_info found in JSON file")
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("BEGIN TRANSACTION")
            
            try:
                # Clear existing enhanced data
                self._clear_enhanced_data(conn)
                
                for plant_data in plants_info:
                    self._insert_enhanced_plant(conn, plant_data)
                
                conn.execute("COMMIT")
                logger.info(f"Successfully synced {len(plants_info)} enhanced plants")
                return True
                
            except Exception as e:
                conn.execute("ROLLBACK")
                logger.error(f"Error syncing plants data: {e}")
                return False

    def _clear_enhanced_data(self, conn):
        """Clear existing enhanced plant data"""
        tables = [
            'PlantHarvestGuide', 'PlantCompanions', 'PlantGrowthStages',
            'PlantCommonIssues', 'PlantNutrition', 'PlantLightingSchedule',
            'PlantAutomation', 'PlantYieldData', 'PlantSensorRequirements',
            'EnhancedPlants'
        ]
        
        for table in tables:
            conn.execute(f"DELETE FROM {table}")

    def _insert_enhanced_plant(self, conn, plant_data):
        """Insert a single enhanced plant and all its related data"""
        
        plant_id = plant_data.get('id')
        if not plant_id:
            logger.warning("Plant missing ID, skipping")
            return
        
        # Insert main enhanced plant data
        enhanced_plant_cursor = conn.execute("""
            INSERT INTO EnhancedPlants (
                plant_id, species, common_name, variety, pH_range, 
                water_requirements, difficulty_level, market_value_per_kg,
                harvest_frequency, storage_life_days, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plant_id,
            plant_data.get('species'),
            plant_data.get('common_name'),
            plant_data.get('variety'),
            plant_data.get('pH_range'),
            plant_data.get('water_requirements'),
            plant_data.get('yield_data', {}).get('difficulty_level'),
            plant_data.get('yield_data', {}).get('market_value_per_kg'),
            plant_data.get('yield_data', {}).get('harvest_frequency'),
            plant_data.get('yield_data', {}).get('storage_life_days'),
            datetime.now()
        ))
        
        enhanced_plant_id = enhanced_plant_cursor.lastrowid
        
        # Insert sensor requirements
        sensor_reqs = plant_data.get('sensor_requirements', {})
        if sensor_reqs:
            soil_moisture = sensor_reqs.get('soil_moisture_range', {})
            soil_temp = sensor_reqs.get('soil_temperature_C', {})
            co2_reqs = sensor_reqs.get('co2_requirements', {})
            vpd_range = sensor_reqs.get('vpd_range', {})
            light_spectrum = sensor_reqs.get('light_spectrum', {})
            
            conn.execute("""
                INSERT INTO PlantSensorRequirements (
                    enhanced_plant_id, soil_moisture_min, soil_moisture_max,
                    soil_temp_min, soil_temp_max, air_quality_sensitivity,
                    co2_min, co2_max, vpd_min, vpd_max,
                    light_blue_percent, light_red_percent, light_green_percent, light_far_red_percent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                enhanced_plant_id,
                soil_moisture.get('min'), soil_moisture.get('max'),
                soil_temp.get('min'), soil_temp.get('max'),
                sensor_reqs.get('air_quality_sensitivity'),
                co2_reqs.get('min'), co2_reqs.get('max'),
                vpd_range.get('min'), vpd_range.get('max'),
                light_spectrum.get('blue_percent'), light_spectrum.get('red_percent'),
                light_spectrum.get('green_percent'), light_spectrum.get('far_red_percent')
            ))
        
        # Insert yield data
        yield_data = plant_data.get('yield_data', {})
        if yield_data:
            yield_range = yield_data.get('expected_yield_per_plant', {})
            space_req = yield_data.get('space_requirement_cm', {})
            
            conn.execute("""
                INSERT INTO PlantYieldData (
                    enhanced_plant_id, min_yield_grams, max_yield_grams,
                    harvest_period_weeks, space_width_cm, space_depth_cm, space_height_cm
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                enhanced_plant_id,
                yield_range.get('min'), yield_range.get('max'),
                yield_data.get('harvest_period_weeks'),
                space_req.get('width'), space_req.get('depth'), space_req.get('height')
            ))
        
        # Insert automation settings
        automation = plant_data.get('automation', {})
        if automation:
            watering = automation.get('watering_schedule', {})
            alerts = automation.get('alert_thresholds', {})
            env_controls = automation.get('environmental_controls', {})
            
            conn.execute("""
                INSERT INTO PlantAutomation (
                    enhanced_plant_id, watering_frequency_hours, watering_amount_ml,
                    soil_moisture_trigger, early_morning_boost, temperature_min, temperature_max,
                    humidity_min, humidity_max, soil_moisture_critical,
                    ventilation_trigger_temp, heating_trigger_temp, dehumidify_trigger, co2_enrichment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                enhanced_plant_id,
                watering.get('frequency_hours'), watering.get('amount_ml_per_plant'),
                watering.get('soil_moisture_trigger'), watering.get('early_morning_boost', False),
                alerts.get('temperature_min'), alerts.get('temperature_max'),
                alerts.get('humidity_min'), alerts.get('humidity_max'),
                alerts.get('soil_moisture_critical'),
                env_controls.get('ventilation_trigger_temp'), env_controls.get('heating_trigger_temp'),
                env_controls.get('dehumidify_trigger'), env_controls.get('co2_enrichment', False)
            ))
        
        # Insert lighting schedules
        lighting = automation.get('lighting_schedule', {}) if automation else {}
        if lighting:
            for stage, schedule in lighting.items():
                if isinstance(schedule, dict):
                    conn.execute("""
                        INSERT INTO PlantLightingSchedule (
                            enhanced_plant_id, growth_stage, hours_per_day, intensity_percent
                        ) VALUES (?, ?, ?, ?)
                    """, (
                        enhanced_plant_id, stage,
                        schedule.get('hours'), schedule.get('intensity')
                    ))
        
        # Insert nutritional information
        nutrition = plant_data.get('nutritional_info', {})
        if nutrition:
            # Handle special compounds (THC, CBD, etc.)
            special_compounds = {}
            for key in ['thc_percent', 'cbd_percent', 'terpenes', 'key_compounds', 'medicinal_benefits']:
                if key in nutrition:
                    special_compounds[key] = nutrition[key]
            
            conn.execute("""
                INSERT INTO PlantNutrition (
                    enhanced_plant_id, calories_per_100g, protein_g, vitamin_c_mg,
                    key_nutrients, health_benefits, special_compounds
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                enhanced_plant_id,
                nutrition.get('calories_per_100g'), nutrition.get('protein_g'),
                nutrition.get('vitamin_c_mg'),
                json.dumps(nutrition.get('key_nutrients', [])),
                json.dumps(nutrition.get('health_benefits', [])),
                json.dumps(special_compounds) if special_compounds else None
            ))
        
        # Insert common issues
        common_issues = plant_data.get('common_issues', [])
        for issue in common_issues:
            conn.execute("""
                INSERT INTO PlantCommonIssues (
                    enhanced_plant_id, problem_name, symptoms, causes,
                    solutions, prevention, sensor_indicators
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                enhanced_plant_id,
                issue.get('problem'),
                json.dumps(issue.get('symptoms', [])),
                json.dumps(issue.get('causes', [])),
                json.dumps(issue.get('solutions', [])),
                issue.get('prevention'),
                json.dumps(issue.get('sensor_indicators', {}))
            ))
        
        # Insert growth stages
        growth_stages = plant_data.get('growth_stages', [])
        for stage in growth_stages:
            conditions = stage.get('conditions', {})
            duration = stage.get('duration', {})
            sensor_targets = stage.get('sensor_targets', {})
            
            conn.execute("""
                INSERT INTO PlantGrowthStages (
                    enhanced_plant_id, stage_name, min_days, max_days,
                    temperature_min, temperature_max, humidity_min, humidity_max,
                    light_hours, soil_moisture_target, soil_temp_target, vpd_target,
                    care_instructions
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                enhanced_plant_id,
                stage.get('stage'),
                duration.get('min_days'), duration.get('max_days'),
                conditions.get('temperature_C', {}).get('min'),
                conditions.get('temperature_C', {}).get('max'),
                conditions.get('humidity_percent', {}).get('min'),
                conditions.get('humidity_percent', {}).get('max'),
                conditions.get('hours_per_day'),
                sensor_targets.get('soil_moisture'),
                sensor_targets.get('soil_temp'),
                sensor_targets.get('vpd'),
                json.dumps(stage.get('care_instructions', []))
            ))
        
        # Insert companion plants
        companions = plant_data.get('companion_plants', {})
        if companions:
            for companion_type in ['beneficial', 'avoid']:
                plants_list = companions.get(companion_type, [])
                if plants_list:
                    conn.execute("""
                        INSERT INTO PlantCompanions (
                            enhanced_plant_id, companion_type, companion_plants, reasoning
                        ) VALUES (?, ?, ?, ?)
                    """, (
                        enhanced_plant_id, companion_type,
                        json.dumps(plants_list), companions.get('reasoning')
                    ))
        
        # Insert harvest guide
        harvest_guide = plant_data.get('harvest_guide', {})
        if harvest_guide:
            conn.execute("""
                INSERT INTO PlantHarvestGuide (
                    enhanced_plant_id, indicators, storage_tips, processing_options
                ) VALUES (?, ?, ?, ?)
            """, (
                enhanced_plant_id,
                json.dumps(harvest_guide.get('indicators', [])),
                json.dumps(harvest_guide.get('storage_tips', [])),
                json.dumps(harvest_guide.get('processing_options', []))
            ))
        
        logger.info(f"Inserted enhanced plant: {plant_data.get('common_name')}")

    def get_enhanced_plants_for_web(self):
        """Get enhanced plants data formatted for web display"""
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute("""
                SELECT 
                    ep.*,
                    psr.soil_moisture_min, psr.soil_moisture_max,
                    psr.soil_temp_min, psr.soil_temp_max,
                    pyd.min_yield_grams, pyd.max_yield_grams,
                    pa.watering_frequency_hours, pa.watering_amount_ml
                FROM EnhancedPlants ep
                LEFT JOIN PlantSensorRequirements psr ON ep.enhanced_plant_id = psr.enhanced_plant_id
                LEFT JOIN PlantYieldData pyd ON ep.enhanced_plant_id = pyd.enhanced_plant_id
                LEFT JOIN PlantAutomation pa ON ep.enhanced_plant_id = pa.enhanced_plant_id
                ORDER BY ep.common_name
            """)
            
            plants = []
            for row in cursor.fetchall():
                plant = dict(row)
                
                # Get additional data
                plant['growth_stages'] = self._get_growth_stages(conn, plant['enhanced_plant_id'])
                plant['common_issues'] = self._get_common_issues(conn, plant['enhanced_plant_id'])
                plant['lighting_schedule'] = self._get_lighting_schedule(conn, plant['enhanced_plant_id'])
                plant['nutrition'] = self._get_nutrition(conn, plant['enhanced_plant_id'])
                
                plants.append(plant)
            
            return plants

    def _get_growth_stages(self, conn, enhanced_plant_id):
        """Get growth stages for a plant"""
        cursor = conn.execute("""
            SELECT * FROM PlantGrowthStages WHERE enhanced_plant_id = ? ORDER BY stage_name
        """, (enhanced_plant_id,))
        
        stages = []
        for row in cursor.fetchall():
            stage = dict(row)
            if stage['care_instructions']:
                stage['care_instructions'] = json.loads(stage['care_instructions'])
            stages.append(stage)
        
        return stages

    def _get_common_issues(self, conn, enhanced_plant_id):
        """Get common issues for a plant"""
        cursor = conn.execute("""
            SELECT * FROM PlantCommonIssues WHERE enhanced_plant_id = ?
        """, (enhanced_plant_id,))
        
        issues = []
        for row in cursor.fetchall():
            issue = dict(row)
            for json_field in ['symptoms', 'causes', 'solutions']:
                if issue[json_field]:
                    issue[json_field] = json.loads(issue[json_field])
            if issue['sensor_indicators']:
                issue['sensor_indicators'] = json.loads(issue['sensor_indicators'])
            issues.append(issue)
        
        return issues

    def _get_lighting_schedule(self, conn, enhanced_plant_id):
        """Get lighting schedule for a plant"""
        cursor = conn.execute("""
            SELECT * FROM PlantLightingSchedule WHERE enhanced_plant_id = ?
        """, (enhanced_plant_id,))
        
        schedule = {}
        for row in cursor.fetchall():
            stage = row['growth_stage']
            schedule[stage] = {
                'hours': row['hours_per_day'],
                'intensity': row['intensity_percent']
            }
        
        return schedule

    def _get_nutrition(self, conn, enhanced_plant_id):
        """Get nutrition data for a plant"""
        cursor = conn.execute("""
            SELECT * FROM PlantNutrition WHERE enhanced_plant_id = ?
        """, (enhanced_plant_id,))
        
        row = cursor.fetchone()
        if row:
            nutrition = dict(row)
            if nutrition['key_nutrients']:
                nutrition['key_nutrients'] = json.loads(nutrition['key_nutrients'])
            if nutrition['health_benefits']:
                nutrition['health_benefits'] = json.loads(nutrition['health_benefits'])
            if nutrition['special_compounds']:
                nutrition['special_compounds'] = json.loads(nutrition['special_compounds'])
            return nutrition
        
        return {}


def main():
    """Main function to run the database integration"""
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Paths
    db_path = "sysgrow_dev.db"  # Your development database
    json_path = "plants_info.json"  # Enhanced plants JSON
    
    print("🌱 SYSGrow Enhanced Plants Database Integration")
    print("=" * 55)
    
    integrator = EnhancedPlantsDBIntegrator(db_path, json_path)
    
    print("📊 Creating enhanced plant tables...")
    integrator.create_enhanced_plant_tables()
    
    print("🔄 Syncing enhanced plants data...")
    success = integrator.sync_enhanced_plants_data()
    
    if success:
        print("✅ Enhanced plants data successfully integrated!")
        
        # Test the integration
        print("\n📋 Testing integration...")
        plants = integrator.get_enhanced_plants_for_web()
        print(f"✅ Found {len(plants)} enhanced plants in database")
        
        # Show sample plants
        print("\n🌿 Sample Enhanced Plants:")
        for i, plant in enumerate(plants[:5]):
            print(f"  {i+1}. {plant['common_name']} ({plant['species']})")
            print(f"     💰 Market Value: ${plant.get('market_value_per_kg', 0)}/kg")
            print(f"     🎯 Difficulty: {plant.get('difficulty_level', 'Unknown')}")
            if plant.get('watering_amount_ml'):
                print(f"     💧 Watering: {plant['watering_amount_ml']}ml every {plant.get('watering_frequency_hours', 24)}hrs")
            print()
        
        print("🎉 Integration completed successfully!")
        print("🔗 Your plants guide should now display enhanced data!")
        
    else:
        print("❌ Failed to integrate enhanced plants data")
        print("   Check the logs for details")

if __name__ == "__main__":
    main()