"""
Harvest Report API Routes
Handles harvest report generation, data cleanup, and retrieval.
"""
from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from app.services.application.harvest_service import PlantHarvestService
from app.enums import HealthLevel
import logging

from app.blueprints.api._common import (
    get_harvest_service as _harvest_service,
    get_growth_service as _growth_service,
    get_container,
)
from app.schemas import HarvestPlantRequest

logger = logging.getLogger(__name__)

harvest_bp = Blueprint('harvest', __name__)


@harvest_bp.route('/api/plants/<int:plant_id>/harvest', methods=['POST'])
def create_harvest_report(plant_id):
    """
    Generate harvest report and optionally cleanup plant data.
    
    Request body:
    {
        "harvest_weight_grams": 250.5,
        "quality_rating": 5,
        "notes": "Excellent harvest",
        "delete_plant_data": true
    }
    """
    try:
        raw = request.get_json()
        
        if not raw:
            response = jsonify({'ok': False, 'data': None, 'error': {'message': 'Request body is required'}})
            response.status_code = 400
            return response
        
        try:
            body = HarvestPlantRequest(**raw)
        except ValidationError as ve:
            response = jsonify({'ok': False, 'data': None, 'error': {'message': 'Invalid request', 'details': ve.errors()}})
            response.status_code = 400
            return response
        
        service = _harvest_service()
        
        result = service.harvest_and_cleanup(
            plant_id=plant_id,
            harvest_weight_grams=body.harvest_weight_grams,
            quality_rating=body.quality_rating,
            notes=body.notes,
            delete_plant_data=body.delete_plant_data
        )
        
        # Log activity
        from app.services.application.activity_logger import ActivityLogger
        container = get_container()
        if container and hasattr(container, 'activity_logger') and container.activity_logger:
            container.activity_logger.log_activity(
                activity_type=ActivityLogger.HARVEST_RECORDED,
                description=f"Recorded harvest for plant {plant_id} ({body.harvest_weight_grams}g, quality: {body.quality_rating}/5)",
                severity=ActivityLogger.INFO,
                entity_type="plant",
                entity_id=plant_id,
                metadata={
                    "harvest_weight_grams": body.harvest_weight_grams,
                    "quality_rating": body.quality_rating,
                    "cleanup_performed": result.get('cleanup_performed', False)
                }
            )
        
        response = jsonify({
            'ok': True,
            'data': {
                'harvest_report': result['harvest_report'],
                'cleanup_performed': result.get('cleanup_performed', False),
                'cleanup_summary': result.get('cleanup_summary', {})
            },
            'error': None
        })
        response.status_code = 200
        return response
        
    except ValueError as e:
        logger.error(f"Validation error creating harvest report: {e}")
        response = jsonify({'ok': False, 'data': None, 'error': {'message': str(e)}})
        response.status_code = 400
        return response
    except Exception as e:
        logger.error(f"Error creating harvest report for plant {plant_id}: {e}")
        response = jsonify({'ok': False, 'data': None, 'error': {'message': f'Failed to create harvest report: {str(e)}'}})
        response.status_code = 500
        return response


@harvest_bp.route('/api/harvests/<int:harvest_id>', methods=['GET'])
def get_harvest_report(harvest_id):
    """
    Get a specific harvest report by ID.
    """
    try:
        service = _harvest_service()
        report = service.get_harvest_by_id(harvest_id)
        
        if not report:
            response = jsonify({'ok': False, 'data': None, 'error': {'message': 'Harvest report not found'}})
            response.status_code = 404
            return response
        
        response = jsonify({'ok': True, 'data': report, 'error': None})
        response.status_code = 200
        return response
        
    except Exception as e:
        logger.error(f"Error retrieving harvest report {harvest_id}: {e}")
        response = jsonify({'ok': False, 'data': None, 'error': {'message': f'Failed to retrieve harvest report: {str(e)}'}})
        response.status_code = 500
        return response


@harvest_bp.route('/api/harvests', methods=['GET'])
def list_harvest_reports():
    """
    List all harvest reports with optional filtering.
    
    Query parameters:
    - unit_id: Filter by growth unit ID
    - limit: Maximum number of results (default: 50)
    - offset: Number of results to skip (default: 0)
    """
    try:
        unit_id = request.args.get('unit_id', type=int)
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Validate parameters
        if limit < 1 or limit > 100:
            response = jsonify({'ok': False, 'data': None, 'error': {'message': 'limit must be between 1 and 100'}})
            response.status_code = 400
            return response
        
        if offset < 0:
            response = jsonify({'ok': False, 'data': None, 'error': {'message': 'offset must be non-negative'}})
            response.status_code = 400
            return response
        
        service = _harvest_service()
        harvests = service.get_harvest_reports(unit_id)
        
        # Apply pagination
        total = len(harvests)
        paginated = harvests[offset:offset + limit]
        
        response = jsonify({
            'ok': True,
            'data': {
                'total': total,
                'limit': limit,
                'offset': offset,
                'harvests': paginated
            },
            'error': None
        })
        response.status_code = 200
        return response
        
    except Exception as e:
        logger.error(f"Error listing harvest reports: {e}")
        response = jsonify({'ok': False, 'data': None, 'error': {'message': f'Failed to list harvest reports: {str(e)}'}})
        response.status_code = 500
        return response


@harvest_bp.route('/api/units/<int:unit_id>/plants', methods=['GET'])
def get_plants_for_unit(unit_id):
    """
    Get all plants for a specific growth unit.
    
    Query parameters:
    - stage: Filter by growth stage (optional)
    - ready_to_harvest: Filter plants ready to harvest (optional)
    """
    try:
        stage = request.args.get('stage')
        ready_to_harvest = request.args.get('ready_to_harvest', '').lower() == 'true'
        
        service = _growth_service()
        unit = service.get_unit_runtime(unit_id)
        if not unit:
            response = jsonify({'ok': False, 'data': None, 'error': {'message': 'Growth unit not found'}})
            response.status_code = 404
            return response
        plants = unit.get_all_plants()
        
        # Apply filters
        if stage:
            plants = [p for p in plants if p.get('current_stage') == stage]
        
        if ready_to_harvest:
            # Consider plants in ripening/harvest stage as ready
            harvest_stages = ['ripening', 'harvest', 'flowering']
            plants = [p for p in plants if p.get('current_stage') in harvest_stages]
        
        response = jsonify({'ok': True, 'data': plants, 'error': None})
        response.status_code = 200
        return response
        
    except Exception as e:
        logger.error(f"Error getting plants for unit {unit_id}: {e}")
        response = jsonify({'ok': False, 'data': None, 'error': {'message': f'Failed to get plants: {str(e)}'}})
        response.status_code = 500
        return response


@harvest_bp.route('/api/plants/<int:plant_id>', methods=['DELETE'])
def delete_plant(plant_id):
    """
    Delete plant data (typically after harvest).
    
    Query parameters:
    - harvested: Set to 'true' to indicate this is a post-harvest deletion
    """
    try:
        harvested = request.args.get('harvested', 'false').lower() == 'true'
        
        service = _harvest_service()
        
        if not harvested:
            response = jsonify({
                'ok': False,
                'data': None,
                'error': {'message': 'This endpoint only supports post-harvest deletion. Use harvested=true parameter.'}
            })
            response.status_code = 400
            return response
        
        result = service.cleanup_after_harvest(
            plant_id=plant_id,
            delete_plant_data=True
        )
        
        response = jsonify({
            'ok': True,
            'data': {
                'message': 'Plant data deleted successfully',
                'deleted_records': result.get('deleted', {}),
                'preserved_records': result.get('preserved', {})
            },
            'error': None
        })
        response.status_code = 200
        return response
        
    except Exception as e:
        logger.error(f"Error deleting plant {plant_id}: {e}")
        response = jsonify({'ok': False, 'data': None, 'error': {'message': f'Failed to delete plant: {str(e)}'}})
        response.status_code = 500
        return response


@harvest_bp.route('/api/units/<int:unit_id>/harvest-stats', methods=['GET'])
def get_unit_harvest_stats(unit_id):
    """
    Get harvest statistics and trends for a specific unit.
    """
    try:
        limit = request.args.get('limit', 10, type=int)
        
        service = _harvest_service()
        stats = service.compare_harvests(unit_id, limit)
        
        response = jsonify({
            'ok': True,
            'data': {
                'unit_id': unit_id,
                'harvest_count': len(stats),
                'statistics': stats
            },
            'error': None
        })
        response.status_code = 200
        return response
        
    except Exception as e:
        logger.error(f"Error getting harvest stats for unit {unit_id}: {e}")
        response = jsonify({'ok': False, 'data': None, 'error': {'message': f'Failed to get harvest statistics: {str(e)}'}})
        response.status_code = 500
        return response


@harvest_bp.route('/api/units/<int:unit_id>/growth-cycles/compare', methods=['GET'])
def compare_growth_cycles(unit_id):
    """
    Compare multiple growth cycles (harvests) for a unit.

    Provides side-by-side comparison of yields, durations, energy consumption,
    and environmental conditions across different harvests.

    Query parameters:
    - limit: Number of harvests to compare (default: 10, max: 50)
    """
    try:
        limit = min(request.args.get('limit', 10, type=int), 50)

        container = get_container()
        analytics_repo = getattr(container, 'analytics_repo', None)

        if not analytics_repo:
            return jsonify({
                'ok': False,
                'data': None,
                'error': {'message': 'Analytics repository not available'}
            }), 503

        comparison = analytics_repo.compare_growth_cycles(
            unit_id=unit_id,
            limit=limit,
        )

        if comparison.get('error'):
            return jsonify({
                'ok': False,
                'data': None,
                'error': {'message': comparison['error']}
            }), 500

        return jsonify({
            'ok': True,
            'data': comparison,
            'error': None
        }), 200

    except Exception as e:
        logger.error(f"Error comparing growth cycles for unit {unit_id}: {e}")
        return jsonify({
            'ok': False,
            'data': None,
            'error': {'message': f'Failed to compare growth cycles: {str(e)}'}
        }), 500


@harvest_bp.route('/api/harvests/compare', methods=['GET'])
def compare_specific_harvests():
    """
    Compare environmental conditions between specific harvests.

    Query parameters:
    - ids: Comma-separated list of harvest IDs to compare (required)

    Example: /api/harvests/compare?ids=1,2,3
    """
    try:
        ids_param = request.args.get('ids', '')
        if not ids_param:
            return jsonify({
                'ok': False,
                'data': None,
                'error': {'message': 'ids parameter is required (comma-separated harvest IDs)'}
            }), 400

        try:
            harvest_ids = [int(x.strip()) for x in ids_param.split(',') if x.strip()]
        except ValueError:
            return jsonify({
                'ok': False,
                'data': None,
                'error': {'message': 'Invalid harvest IDs format'}
            }), 400

        if len(harvest_ids) < 2:
            return jsonify({
                'ok': False,
                'data': None,
                'error': {'message': 'At least 2 harvest IDs are required for comparison'}
            }), 400

        if len(harvest_ids) > 10:
            return jsonify({
                'ok': False,
                'data': None,
                'error': {'message': 'Maximum 10 harvests can be compared at once'}
            }), 400

        container = get_container()
        analytics_repo = getattr(container, 'analytics_repo', None)

        if not analytics_repo:
            return jsonify({
                'ok': False,
                'data': None,
                'error': {'message': 'Analytics repository not available'}
            }), 503

        comparison = analytics_repo.get_cycle_environmental_comparison(harvest_ids)

        if comparison.get('error'):
            return jsonify({
                'ok': False,
                'data': None,
                'error': {'message': comparison['error']}
            }), 500

        return jsonify({
            'ok': True,
            'data': comparison,
            'error': None
        }), 200

    except Exception as e:
        logger.error(f"Error comparing harvests: {e}")
        return jsonify({
            'ok': False,
            'data': None,
            'error': {'message': f'Failed to compare harvests: {str(e)}'}
        }), 500


@harvest_bp.route('/api/plants/types/<plant_type>/performance', methods=['GET'])
def get_plant_type_performance(plant_type):
    """
    Get performance statistics for a specific plant type across all units.

    Shows how a plant type has performed historically, including optimal
    conditions derived from the best harvests.

    Query parameters:
    - limit: Max harvests to analyze (default: 20, max: 100)
    """
    try:
        limit = min(request.args.get('limit', 20, type=int), 100)

        container = get_container()
        analytics_repo = getattr(container, 'analytics_repo', None)

        if not analytics_repo:
            return jsonify({
                'ok': False,
                'data': None,
                'error': {'message': 'Analytics repository not available'}
            }), 503

        performance = analytics_repo.get_plant_type_performance(
            plant_type=plant_type,
            limit=limit,
        )

        if performance.get('error'):
            return jsonify({
                'ok': False,
                'data': None,
                'error': {'message': performance['error']}
            }), 500

        return jsonify({
            'ok': True,
            'data': performance,
            'error': None
        }), 200

    except Exception as e:
        logger.error(f"Error getting plant type performance for {plant_type}: {e}")
        return jsonify({
            'ok': False,
            'data': None,
            'error': {'message': f'Failed to get plant type performance: {str(e)}'}
        }), 500


@harvest_bp.route('/api/units/<int:unit_id>/sensor-summaries', methods=['GET'])
def get_unit_sensor_summaries(unit_id):
    """
    Get aggregated sensor summaries for a unit (for harvest reports).

    These summaries contain daily min/max/avg values preserved from raw sensor
    readings before they are pruned. Essential for generating comprehensive
    harvest reports showing environmental conditions throughout the grow cycle.

    Query parameters:
    - start_date: Start date filter (ISO format: YYYY-MM-DD)
    - end_date: End date filter (ISO format: YYYY-MM-DD)
    - sensor_type: Filter by sensor type (e.g., 'temperature', 'humidity')
    - limit: Maximum number of results (default: 500)
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        sensor_type = request.args.get('sensor_type')
        limit = request.args.get('limit', 500, type=int)

        # Validate limit
        if limit < 1 or limit > 2000:
            response = jsonify({
                'ok': False,
                'data': None,
                'error': {'message': 'limit must be between 1 and 2000'}
            })
            response.status_code = 400
            return response

        container = get_container()
        device_repo = getattr(container, 'device_repo', None)

        if not device_repo:
            response = jsonify({
                'ok': False,
                'data': None,
                'error': {'message': 'Device repository not available'}
            })
            response.status_code = 503
            return response

        summaries = device_repo.get_sensor_summaries_for_unit(
            unit_id=unit_id,
            start_date=start_date,
            end_date=end_date,
            sensor_type=sensor_type,
            limit=limit,
        )

        response = jsonify({
            'ok': True,
            'data': {
                'unit_id': unit_id,
                'count': len(summaries),
                'summaries': summaries,
            },
            'error': None
        })
        response.status_code = 200
        return response

    except Exception as e:
        logger.error(f"Error getting sensor summaries for unit {unit_id}: {e}")
        response = jsonify({
            'ok': False,
            'data': None,
            'error': {'message': f'Failed to get sensor summaries: {str(e)}'}
        })
        response.status_code = 500
        return response


@harvest_bp.route('/api/units/<int:unit_id>/harvest-environment', methods=['GET'])
def get_harvest_environment_stats(unit_id):
    """
    Get environmental statistics for a harvest report.

    Provides aggregated sensor stats (min, max, avg) grouped by sensor type
    for the specified period. Useful for harvest reports to show overall
    environmental conditions during the grow cycle.

    Query parameters:
    - start_date: Start date of grow cycle (ISO format: YYYY-MM-DD) [required]
    - end_date: End date of grow cycle (ISO format: YYYY-MM-DD) [required]
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not start_date or not end_date:
            response = jsonify({
                'ok': False,
                'data': None,
                'error': {'message': 'start_date and end_date are required'}
            })
            response.status_code = 400
            return response

        container = get_container()
        device_repo = getattr(container, 'device_repo', None)

        if not device_repo:
            response = jsonify({
                'ok': False,
                'data': None,
                'error': {'message': 'Device repository not available'}
            })
            response.status_code = 503
            return response

        stats = device_repo.get_sensor_summary_stats_for_harvest(
            unit_id=unit_id,
            start_date=start_date,
            end_date=end_date,
        )

        response = jsonify({
            'ok': True,
            'data': {
                'unit_id': unit_id,
                'start_date': start_date,
                'end_date': end_date,
                'environment_stats': stats,
            },
            'error': None
        })
        response.status_code = 200
        return response

    except Exception as e:
        logger.error(f"Error getting harvest environment stats for unit {unit_id}: {e}")
        response = jsonify({
            'ok': False,
            'data': None,
            'error': {'message': f'Failed to get environment statistics: {str(e)}'}
        })
        response.status_code = 500
        return response


@harvest_bp.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for harvest service"""
    try:
        service = _harvest_service()
        response = jsonify({
            'ok': True,
            'data': {
                'status': HealthLevel.HEALTHY.value,
                'service': 'harvest',
                'version': '1.0.0'
            },
            'error': None
        })
        response.status_code = 200
        return response
    except Exception as e:
        response = jsonify({
            'ok': False,
            'data': None,
            'error': {'message': str(e), 'status': HealthLevel.CRITICAL.value}
        })
        response.status_code = 503
        return response
